"""Core plotting and orbit-frame utilities for Orbital Carousel."""

from __future__ import annotations

from dataclasses import dataclass
import datetime as dt
import math
import os
from pathlib import Path
import re
import time
from typing import Iterable, Mapping, Sequence
import warnings

import numpy as np
from astropy.time import Time, TimeDelta
from astroquery.jplhorizons import Horizons
from requests import HTTPError

PLANET_IDS: Mapping[str, str] = {
    "Mercury": "199",
    "Venus": "299",
    "Earth": "399",
    "Mars": "499",
    "Jupiter": "599",
    "Saturn": "699",
    "Uranus": "799",
    "Neptune": "899",
}

PLANET_COLORS: Mapping[str, str] = {
    "Mercury": "gray",
    "Venus": "yellowgreen",
    "Earth": "green",
    "Mars": "red",
    "Jupiter": "orange",
    "Saturn": "gold",
    "Uranus": "cyan",
    "Neptune": "purple",
}

# These nominal semimajor axes are only used to choose a readable automatic
# plot extent: include planets through the first one outside the target's
# maximum heliocentric distance.
PLANET_NOMINAL_R_AU: Mapping[str, float] = {
    "Mercury": 0.387,
    "Venus": 0.723,
    "Earth": 1.0,
    "Mars": 1.524,
    "Jupiter": 5.203,
    "Saturn": 9.537,
    "Uranus": 19.191,
    "Neptune": 30.07,
}

DEFAULT_PLANETS = tuple(PLANET_IDS)
DEFAULT_FORMATS = ("pdf", "png")
DEFAULT_FRAME = "corotating"
DEFAULT_FRAME_BODY = "Jupiter"
DEFAULT_EPHEMERIS = "horizons"
DEFAULT_START = "2000-01-01"
DEFAULT_STOP = "2030-01-01"
DEFAULT_STEP = "30d"
DEFAULT_LOCATIONS = "@sun"
DEFAULT_HORIZONS_MAX_ATTEMPTS = 6
DEFAULT_AUTO_EPOCHS = True
DEFAULT_ORBITS = 20
DEFAULT_SAMPLES_PER_ORBIT = 120
_RETRYABLE_HORIZONS_STATUSES = {429, 502, 503, 504}
_PERIOD_COLUMNS = ("P", "period", "per")
_ASSIST_PLANET_FILENAMES = ("de441.bsp", "linux_m13000p17000.441")
_ASSIST_ASTEROID_FILENAME = "sb441-n16.bsp"
_ASSIST_PLANET_URL = (
    "https://ssd.jpl.nasa.gov/ftp/eph/planets/Linux/de441/"
    "linux_m13000p17000.441"
)
_ASSIST_ASTEROID_URL = (
    "https://ssd.jpl.nasa.gov/ftp/eph/small_bodies/asteroids_de441/"
    "sb441-n16.bsp"
)
_J2000_OBLIQUITY_RAD = math.radians(23.43929111111111)
_JD_PATTERN = re.compile(r"^JD\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+))$", re.IGNORECASE)
_CALENDAR_PATTERN = re.compile(r"^([+-]?\d{4,})-(\d{2})-(\d{2})$")
_FIXED_STEP_PATTERN = re.compile(
    r"^(\d+)\s*(d|day|days|h|hour|hours|m|min|minute|minutes)$",
    re.IGNORECASE,
)
_CALENDAR_STEP_PATTERN = re.compile(
    r"^(\d+)\s*(y|yr|year|years|mo|month|months)$",
    re.IGNORECASE,
)
_UNITLESS_STEP_PATTERN = re.compile(r"^(\d+)$")


@dataclass(frozen=True)
class PlotRequest:
    """Resolved plot settings used by the CLI and the library entry point."""

    object_name: str
    start: str | None = None
    stop: str | None = None
    step: str | None = None
    frame: str = DEFAULT_FRAME
    frame_body: str | Sequence[str] = DEFAULT_FRAME_BODY
    planets: str | Sequence[str] = "all"
    formats: Sequence[str] = DEFAULT_FORMATS
    output_dir: Path | str | None = None
    figsize: tuple[float, float] | None = None
    show: bool = False
    include_planets: Sequence[str] = ()
    exclude_planets: Sequence[str] = ()
    auto_epochs: bool = DEFAULT_AUTO_EPOCHS
    orbits: float = DEFAULT_ORBITS
    samples_per_orbit: float = DEFAULT_SAMPLES_PER_ORBIT
    ephemeris: str = DEFAULT_EPHEMERIS
    assist_data_dir: Path | str | None = None
    integration_epoch: str | None = None


@dataclass(frozen=True)
class EpochGrid:
    """TDB Julian dates corresponding to a resolved epoch mapping."""

    jds: np.ndarray
    start: str
    stop: str
    step: str


def current_utc_date() -> str:
    """Return today's UTC date as a Horizons-friendly ISO date."""

    return str(dt.datetime.now(dt.timezone.utc).date())


def _is_gregorian_leap_year(year: int) -> bool:
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)


def _validate_calendar_date(year: int, month: int, day: int, field_name: str, value: str) -> None:
    month_lengths = (
        31,
        29 if _is_gregorian_leap_year(year) else 28,
        31,
        30,
        31,
        30,
        31,
        31,
        30,
        31,
        30,
        31,
    )
    if not 1 <= month <= 12 or not 1 <= day <= month_lengths[month - 1]:
        raise ValueError(f"{field_name} is not a valid calendar date; got {value!r}")


def _proleptic_gregorian_jd(year: int, month: int, day: int) -> float:
    adjusted_year = year
    adjusted_month = month
    if adjusted_month <= 2:
        adjusted_year -= 1
        adjusted_month += 12
    century = math.floor(adjusted_year / 100)
    correction = 2 - century + math.floor(century / 4)
    return float(
        math.floor(365.25 * (adjusted_year + 4716))
        + math.floor(30.6001 * (adjusted_month + 1))
        + day
        + correction
        - 1524.5
    )


def _proleptic_gregorian_components(jd: float) -> tuple[int, int, int]:
    shifted = jd + 0.5
    integer_day = math.floor(shifted)
    alpha = math.floor((integer_day - 1867216.25) / 36524.25)
    adjusted_day = integer_day + 1 + alpha - math.floor(alpha / 4)
    intermediate = adjusted_day + 1524
    year_term = math.floor((intermediate - 122.1) / 365.25)
    year_days = math.floor(365.25 * year_term)
    month_term = math.floor((intermediate - year_days) / 30.6001)
    day = int(intermediate - year_days - math.floor(30.6001 * month_term))
    month = int(month_term - 1 if month_term < 14 else month_term - 13)
    year = int(year_term - 4716 if month > 2 else year_term - 4715)
    return year, month, day


def parse_epoch_jd(value: str, field_name: str = "epoch") -> float:
    """Parse an ISO-like astronomical date or ``JD<number>`` as TDB."""

    text = str(value).strip()
    jd_match = _JD_PATTERN.fullmatch(text)
    if jd_match:
        jd = float(jd_match.group(1))
        if math.isfinite(jd):
            return jd
        raise ValueError(f"{field_name} Julian Date must be finite; got {value!r}")

    calendar_match = _CALENDAR_PATTERN.fullmatch(text)
    if not calendar_match:
        raise ValueError(
            f"{field_name} must be YYYY-MM-DD, a signed astronomical year date, "
            f"or JD<number>; got {value!r}"
        )

    year, month, day = (int(part) for part in calendar_match.groups())
    _validate_calendar_date(year, month, day, field_name, value)
    try:
        epoch = Time(
            {"year": year, "month": month, "day": day},
            format="ymdhms",
            scale="tdb",
        )
    except (TypeError, ValueError):
        return _proleptic_gregorian_jd(year, month, day)
    return float(epoch.jd)


def format_epoch_date(jd: float) -> str:
    """Format a TDB Julian Date with an astronomical signed year."""

    try:
        year, month, day, *_ = Time(jd, format="jd", scale="tdb").ymdhms
        year, month, day = int(year), int(month), int(day)
    except (TypeError, ValueError):
        year, month, day = _proleptic_gregorian_components(jd)
    year_text = f"{year:04d}" if year >= 0 else f"-{abs(year):04d}"
    return f"{year_text}-{month:02d}-{day:02d}"


def safe_object_name(object_name: str) -> str:
    """Return the filesystem-safe object token used for output directories."""

    return object_name.strip().replace(" ", "_").replace("/", "+")


def canonical_planet_name(name: str) -> str:
    """Return a supported planet name using case-insensitive matching."""

    normalized = name.strip().lower()
    for planet in DEFAULT_PLANETS:
        if planet.lower() == normalized:
            return planet
    allowed = ", ".join(DEFAULT_PLANETS)
    raise ValueError(f"Unknown planet {name!r}; expected one of: {allowed}")


def _should_retry_horizons_http_error(exc: HTTPError, attempt: int) -> bool:
    status_code = exc.response.status_code if exc.response is not None else None
    return status_code in _RETRYABLE_HORIZONS_STATUSES and attempt < DEFAULT_HORIZONS_MAX_ATTEMPTS


def get_positions(object_name: str, epochs: Mapping[str, str], locations: str = DEFAULT_LOCATIONS):
    """Return JPL Horizons heliocentric vectors for an object over epochs."""

    for attempt in range(1, DEFAULT_HORIZONS_MAX_ATTEMPTS + 1):
        query = Horizons(id=object_name, location=locations, epochs=dict(epochs))
        try:
            return query.vectors(cache=False)
        except HTTPError as exc:
            if not _should_retry_horizons_http_error(exc, attempt):
                raise
            time.sleep(2 ** attempt)
    raise RuntimeError("unreachable Horizons retry state")


def get_barycentric_state(object_name: str, epoch_jd: float):
    """Return one geometric barycentric ICRF state from JPL Horizons."""

    for attempt in range(1, DEFAULT_HORIZONS_MAX_ATTEMPTS + 1):
        query = Horizons(id=object_name, location="@0", epochs=epoch_jd)
        try:
            return query.vectors(refplane="earth", aberrations="geometric", cache=False)
        except HTTPError as exc:
            if not _should_retry_horizons_http_error(exc, attempt):
                raise
            time.sleep(2 ** attempt)
    raise RuntimeError("unreachable Horizons retry state")


def _fixed_step_days(step: str) -> float | None:
    match = _FIXED_STEP_PATTERN.fullmatch(step.strip())
    if not match:
        return None
    count = int(match.group(1))
    if count <= 0:
        raise ValueError("step must be a positive interval")
    unit = match.group(2).lower()
    if unit.startswith("d"):
        return float(count)
    if unit.startswith("h"):
        return count / 24.0
    return count / 1440.0


def _calendar_components(jd: float) -> tuple[int, int, int]:
    formatted = format_epoch_date(jd)
    match = _CALENDAR_PATTERN.fullmatch(formatted)
    assert match is not None
    return tuple(int(part) for part in match.groups())


def _calendar_step_jds(start_jd: float, stop_jd: float, count: int, unit: str) -> np.ndarray:
    start_year, start_month, start_day = _calendar_components(start_jd)
    values = [start_jd]
    offset = count
    while True:
        if unit.startswith("y"):
            year = start_year + offset
            month = start_month
        else:
            month_index = start_year * 12 + (start_month - 1) + offset
            year, month_zero = divmod(month_index, 12)
            month = month_zero + 1

        try:
            _validate_calendar_date(year, month, start_day, "step date", "calendar step")
            candidate_jd = _proleptic_gregorian_jd(year, month, start_day)
        except ValueError:
            candidate_jd = math.nan

        if math.isfinite(candidate_jd):
            if candidate_jd > stop_jd:
                break
            values.append(candidate_jd)
        else:
            stop_year, stop_month, _ = _calendar_components(stop_jd)
            if (year, month) > (stop_year, stop_month):
                break
        offset += count

    if not math.isclose(values[-1], stop_jd, abs_tol=1e-10):
        values.append(stop_jd)
    return np.asarray(values, dtype=float)


def build_epoch_grid(epochs: Mapping[str, str]) -> EpochGrid:
    """Expand a resolved epoch mapping into inclusive TDB Julian dates."""

    start = str(epochs["start"])
    stop = str(epochs["stop"])
    step = str(epochs["step"]).strip()
    start_jd = parse_epoch_jd(start, "start")
    stop_jd = parse_epoch_jd(stop, "stop")
    if stop_jd < start_jd:
        raise ValueError("stop must not be earlier than start")

    unitless_match = _UNITLESS_STEP_PATTERN.fullmatch(step)
    if unitless_match:
        interval_count = int(unitless_match.group(1))
        if interval_count <= 0:
            raise ValueError("unitless step must be a positive interval count")
        jds = np.linspace(start_jd, stop_jd, interval_count + 1)
        return EpochGrid(jds=jds, start=start, stop=stop, step=step)

    fixed_days = _fixed_step_days(step)
    if fixed_days is not None:
        if math.isclose(start_jd, stop_jd, abs_tol=1e-10):
            jds = np.asarray([start_jd], dtype=float)
        else:
            interval_count = int(math.floor((stop_jd - start_jd) / fixed_days))
            jds = start_jd + np.arange(interval_count + 1, dtype=float) * fixed_days
            if not math.isclose(float(jds[-1]), stop_jd, abs_tol=1e-10):
                jds = np.append(jds, stop_jd)
        return EpochGrid(jds=jds, start=start, stop=stop, step=step)

    calendar_match = _CALENDAR_STEP_PATTERN.fullmatch(step)
    if calendar_match:
        count = int(calendar_match.group(1))
        if count <= 0:
            raise ValueError("step must be a positive interval")
        jds = _calendar_step_jds(start_jd, stop_jd, count, calendar_match.group(2).lower())
        return EpochGrid(jds=jds, start=start, stop=stop, step=step)

    raise ValueError(
        "ASSIST step must be a fixed d/h/m interval, a calendar mo/y interval, "
        "or a positive unitless interval count"
    )


def get_elements(object_name: str, locations: str = DEFAULT_LOCATIONS):
    """Return JPL Horizons orbital elements for an object at the current UTC date."""

    epoch = parse_epoch_jd(current_utc_date(), "current UTC date")
    for attempt in range(1, DEFAULT_HORIZONS_MAX_ATTEMPTS + 1):
        query = Horizons(id=object_name, location=locations, epochs=epoch)
        try:
            return query.elements(cache=False)
        except HTTPError as exc:
            if not _should_retry_horizons_http_error(exc, attempt):
                raise
            time.sleep(2 ** attempt)
    raise RuntimeError("unreachable Horizons retry state")


def _first_column_value(values):
    if isinstance(values, (str, bytes)):
        return values
    try:
        if len(values) == 0:
            return None
    except TypeError:
        return values
    try:
        return values[0]
    except (IndexError, KeyError, TypeError):
        return values


def _finite_positive_float(value, name: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = math.nan
    if not math.isfinite(number) or number <= 0:
        raise ValueError(f"{name} must be a finite positive number")
    return number


def _extract_orbital_period_days(elements, object_name: str) -> float:
    for column in _PERIOD_COLUMNS:
        try:
            values = elements[column]
        except (KeyError, TypeError, ValueError):
            continue
        value = _first_column_value(values)
        try:
            period_days = float(value)
        except (TypeError, ValueError):
            continue
        if math.isfinite(period_days) and period_days > 0:
            return period_days
    raise ValueError(
        f"Could not resolve a finite orbital period for {object_name!r}; "
        "supply explicit start, stop, and step values or rerun with --no-auto-epochs."
    )


def get_orbital_period_days(object_name: str, locations: str = DEFAULT_LOCATIONS) -> float:
    """Return the target's finite sidereal orbital period in Earth days."""

    return _extract_orbital_period_days(get_elements(object_name, locations), object_name)


def resolve_epochs(
    object_name: str,
    *,
    start: str | None = None,
    stop: str | None = None,
    step: str | None = None,
    auto_epochs: bool = DEFAULT_AUTO_EPOCHS,
    orbits: float = DEFAULT_ORBITS,
    samples_per_orbit: float = DEFAULT_SAMPLES_PER_ORBIT,
) -> dict[str, str]:
    """Resolve manual and orbit-scaled epoch settings into a provider epoch map."""

    if not auto_epochs:
        return {
            "start": start or DEFAULT_START,
            "stop": stop or DEFAULT_STOP,
            "step": step or DEFAULT_STEP,
        }

    if start is not None and stop is not None and step is not None:
        return {"start": start, "stop": stop, "step": step}

    orbit_count = _finite_positive_float(orbits, "orbits")
    sample_count = _finite_positive_float(samples_per_orbit, "samples_per_orbit")
    period_days = _finite_positive_float(get_orbital_period_days(object_name), "orbital period")

    if step is None:
        step_days = max(1, math.ceil(period_days / sample_count))
        step = f"{step_days}d"

    if start is None or stop is None:
        span_days = math.ceil(period_days * orbit_count)
        if start is None and stop is None:
            stop_jd = parse_epoch_jd(current_utc_date(), "current UTC date")
            start_jd = float(
                (Time(stop_jd, format="jd", scale="tdb") - TimeDelta(span_days, format="jd")).jd
            )
        elif start is None:
            stop_jd = parse_epoch_jd(stop, "stop")
            start_jd = float(
                (Time(stop_jd, format="jd", scale="tdb") - TimeDelta(span_days, format="jd")).jd
            )
        else:
            start_jd = parse_epoch_jd(start, "start")
            stop_jd = float(
                (Time(start_jd, format="jd", scale="tdb") + TimeDelta(span_days, format="jd")).jd
            )
        start = format_epoch_date(start_jd)
        stop = format_epoch_date(stop_jd)

    return {"start": start, "stop": stop, "step": step}


def _column_array(vectors, column: str) -> np.ndarray:
    """Extract a numeric vector column from an Astropy table or mapping."""

    return np.asarray(vectors[column], dtype=float)


def max_heliocentric_distance(vectors) -> float:
    """Return the greatest heliocentric distance in au across vector rows."""

    x = _column_array(vectors, "x")
    y = _column_array(vectors, "y")
    z = _column_array(vectors, "z")
    return float(np.max(np.sqrt(x * x + y * y + z * z)))


def transform_to_corotating_frame(
    obj_x: np.ndarray,
    obj_y: np.ndarray,
    frame_x: np.ndarray,
    frame_y: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Rotate coordinates so the selected frame body stays on +x."""

    theta = np.arctan2(frame_y, frame_x)
    x_rot = obj_x * np.cos(-theta) - obj_y * np.sin(-theta)
    y_rot = obj_x * np.sin(-theta) + obj_y * np.cos(-theta)
    return x_rot, y_rot


def _split_planet_values(values: Iterable[str] | None) -> list[str]:
    if not values:
        return []
    planets: list[str] = []
    for value in values:
        planets.extend(part.strip() for part in value.split(",") if part.strip())
    return planets


def resolve_frame_bodies(frame_body: str | Sequence[str] | None) -> list[str]:
    """Return canonical co-rotating frame bodies in user-requested order."""

    if frame_body is None:
        values = []
    elif isinstance(frame_body, str):
        values = _split_planet_values([frame_body])
    else:
        values = _split_planet_values(frame_body)
    if not values:
        values = [DEFAULT_FRAME_BODY]

    frame_bodies: list[str] = []
    for value in values:
        planet = canonical_planet_name(value)
        if planet not in frame_bodies:
            frame_bodies.append(planet)
    return frame_bodies


def _unique_planets(planets: Iterable[str]) -> list[str]:
    selected = {canonical_planet_name(planet) for planet in planets}
    return [planet for planet in DEFAULT_PLANETS if planet in selected]


def _auto_planets(target_vectors) -> list[str]:
    max_rh = max_heliocentric_distance(target_vectors)
    for index, planet in enumerate(DEFAULT_PLANETS):
        if max_rh <= PLANET_NOMINAL_R_AU[planet]:
            return list(DEFAULT_PLANETS[: index + 1])
    return list(DEFAULT_PLANETS)


def resolve_planets(
    planets: str | Sequence[str],
    *,
    target_vectors=None,
    include_planets: Sequence[str] | None = None,
    exclude_planets: Sequence[str] | None = None,
) -> list[str]:
    """Resolve all planet-selection controls into an ordered planet list."""

    if isinstance(planets, str):
        mode = planets.strip().lower()
        if mode == "all":
            selected = list(DEFAULT_PLANETS)
        elif mode == "none":
            selected = []
        elif mode == "auto":
            if target_vectors is None:
                raise ValueError("target vectors are required for --planets auto")
            selected = _auto_planets(target_vectors)
        else:
            selected = _unique_planets(_split_planet_values([planets]))
    else:
        selected = _unique_planets(planets)

    selected_set = set(selected)
    selected_set.update(_unique_planets(_split_planet_values(include_planets)))
    selected_set.difference_update(_unique_planets(_split_planet_values(exclude_planets)))
    return [planet for planet in DEFAULT_PLANETS if planet in selected_set]


def resolve_assist_data_paths(
    assist_data_dir: Path | str | None = None,
) -> tuple[Path, Path]:
    """Resolve and validate the extended DE441 and n16 ASSIST data files."""

    configured_dir = assist_data_dir
    if configured_dir is None:
        configured_dir = os.environ.get("ASSIST_DIR")
    if not configured_dir:
        raise ValueError(
            "ASSIST data directory is not configured. Pass --assist-data-dir or set "
            "ASSIST_DIR to a directory containing linux_m13000p17000.441 (or "
            "de441.bsp) and sb441-n16.bsp."
        )

    data_dir = Path(configured_dir).expanduser()
    planet_path = next(
        (data_dir / filename for filename in _ASSIST_PLANET_FILENAMES if (data_dir / filename).is_file()),
        None,
    )
    asteroid_path = data_dir / _ASSIST_ASTEROID_FILENAME
    missing = []
    if planet_path is None:
        missing.append("linux_m13000p17000.441 or de441.bsp")
    if not asteroid_path.is_file():
        missing.append(_ASSIST_ASTEROID_FILENAME)
    if missing:
        raise ValueError(
            f"ASSIST data directory {data_dir} is missing {', '.join(missing)}. "
            f"Planet ephemeris: {_ASSIST_PLANET_URL} ; asteroid ephemeris: "
            f"{_ASSIST_ASTEROID_URL}"
        )
    return planet_path, asteroid_path


def _icrf_to_ecliptic(vectors: np.ndarray) -> np.ndarray:
    """Rotate barycentric ICRF Cartesian rows into the J2000 ecliptic frame."""

    result = np.asarray(vectors, dtype=float).copy()
    cos_eps = math.cos(_J2000_OBLIQUITY_RAD)
    sin_eps = math.sin(_J2000_OBLIQUITY_RAD)
    y = result[:, 1].copy()
    z = result[:, 2].copy()
    result[:, 1] = cos_eps * y + sin_eps * z
    result[:, 2] = -sin_eps * y + cos_eps * z
    return result


def _vector_mapping(rows: np.ndarray) -> Mapping[str, np.ndarray]:
    return {"x": rows[:, 0], "y": rows[:, 1], "z": rows[:, 2]}


class HorizonsEphemerisProvider:
    """Current remote JPL Horizons vector provider."""

    provenance = None

    def __init__(self, epochs: Mapping[str, str]):
        self.epochs = epochs

    def target_vectors(self, object_name: str):
        return get_positions(object_name, self.epochs)

    def planet_vectors(self, planets: Iterable[str]) -> Mapping[str, Mapping[str, np.ndarray]]:
        selected = set(planets)
        return {
            planet: get_positions(PLANET_IDS[planet], self.epochs)
            for planet in DEFAULT_PLANETS
            if planet in selected
        }


class AssistEphemerisProvider:
    """Local ASSIST propagation driven by extended JPL DE441 ephemerides."""

    def __init__(
        self,
        epochs: Mapping[str, str],
        *,
        assist_data_dir: Path | str | None = None,
        integration_epoch: str | None = None,
    ):
        try:
            import assist
            import rebound
        except ImportError as exc:
            raise ValueError(
                "ASSIST integration requires the optional dependencies; install "
                'orbital-carousel with `python -m pip install -e ".[integrator]"`.'
            ) from exc

        planet_path, asteroid_path = resolve_assist_data_paths(assist_data_dir)
        self.grid = build_epoch_grid(epochs)
        self._assist = assist
        self._rebound = rebound
        try:
            self.ephem = assist.Ephem(str(planet_path), str(asteroid_path))
        except RuntimeError as exc:
            raise ValueError(f"Could not load ASSIST ephemerides: {exc}") from exc
        self.seed_jd = parse_epoch_jd(
            integration_epoch or current_utc_date(),
            "integration epoch",
        )
        self.provenance = (
            "ASSIST nominal integration; DE441/n16; "
            f"seed {format_epoch_date(self.seed_jd)} TDB (JD {self.seed_jd:.6f})"
        )
        self._sun_ecliptic = self._sample_ephemeris_body("Sun")
        self._validate_seed_coverage()

    def _relative_time(self, jd: float) -> float:
        return float(jd - self.ephem.jd_ref)

    def _ephemeris_particle(self, body: str, jd: float):
        try:
            return self.ephem.get_particle(body, self._relative_time(jd))
        except RuntimeError as exc:
            raise ValueError(
                f"Requested ASSIST epoch {format_epoch_date(jd)} (JD {jd:.6f}) is "
                "outside the loaded ephemeris coverage. Use the extended DE441 "
                "planet file, whose nominal range is approximately 13000 BCE "
                "through 17000 CE."
            ) from exc

    def _validate_seed_coverage(self) -> None:
        self._ephemeris_particle("Sun", self.seed_jd)

    def _sample_ephemeris_body(self, body: str) -> np.ndarray:
        barycentric = np.asarray(
            [self._ephemeris_particle(body, jd).xyz for jd in self.grid.jds],
            dtype=float,
        )
        return _icrf_to_ecliptic(barycentric)

    def _load_seed_state(self, object_name: str) -> np.ndarray:
        state = get_barycentric_state(object_name, self.seed_jd)
        return np.asarray(
            [
                float(_column_array(state, column)[0])
                for column in ("x", "y", "z", "vx", "vy", "vz")
            ],
            dtype=float,
        )

    def _new_simulation(self, state: np.ndarray):
        simulation = self._rebound.Simulation()
        simulation.add(
            x=state[0],
            y=state[1],
            z=state[2],
            vx=state[3],
            vy=state[4],
            vz=state[5],
        )
        simulation.t = self._relative_time(self.seed_jd)
        extras = self._assist.Extras(simulation, self.ephem)
        return simulation, extras

    def _integrated_barycentric_rows(self, object_name: str) -> np.ndarray:
        state = self._load_seed_state(object_name)
        rows = np.empty((len(self.grid.jds), 3), dtype=float)
        exact_seed = np.isclose(self.grid.jds, self.seed_jd, rtol=0.0, atol=1e-10)
        rows[exact_seed] = state[:3]

        past_indices = np.flatnonzero(self.grid.jds < self.seed_jd)[::-1]
        future_indices = np.flatnonzero(self.grid.jds > self.seed_jd)
        for indices in (past_indices, future_indices):
            if len(indices) == 0:
                continue
            simulation, extras = self._new_simulation(state)
            for index in indices:
                jd = float(self.grid.jds[index])
                try:
                    extras.integrate_or_interpolate(self._relative_time(jd))
                except RuntimeError as exc:
                    raise ValueError(
                        f"ASSIST could not integrate {object_name!r} to "
                        f"{format_epoch_date(jd)} (JD {jd:.6f}): {exc}"
                    ) from exc
                rows[index] = simulation.particles[0].xyz
        return rows

    def target_vectors(self, object_name: str) -> Mapping[str, np.ndarray]:
        target_barycentric = self._integrated_barycentric_rows(object_name)
        target_ecliptic = _icrf_to_ecliptic(target_barycentric)
        return _vector_mapping(target_ecliptic - self._sun_ecliptic)

    def planet_vectors(self, planets: Iterable[str]) -> Mapping[str, Mapping[str, np.ndarray]]:
        selected = set(planets)
        result = {}
        for planet in DEFAULT_PLANETS:
            if planet in selected:
                result[planet] = _vector_mapping(
                    self._sample_ephemeris_body(planet) - self._sun_ecliptic
                )
        return result


def normalize_formats(formats: Sequence[str] | None) -> tuple[str, ...]:
    """Return unique lower-case output formats in the user's order."""

    requested = formats or DEFAULT_FORMATS
    normalized: list[str] = []
    for value in requested:
        fmt = value.lower().lstrip(".")
        if fmt not in {"pdf", "png"}:
            raise ValueError(f"Unknown output format {value!r}; expected pdf or png")
        if fmt not in normalized:
            normalized.append(fmt)
    return tuple(normalized)


def build_output_paths(
    object_name: str,
    epochs: Mapping[str, str],
    frame: str,
    frame_body: str,
    formats: Sequence[str] | None = None,
    output_dir: Path | str | None = None,
    ephemeris: str = DEFAULT_EPHEMERIS,
) -> list[Path]:
    """Build destination paths without creating directories or files."""

    safe_name = safe_object_name(object_name)
    directory = Path(output_dir) if output_dir is not None else Path(safe_name)
    frame_token = "heliocentric" if frame == "heliocentric" else f"corotating_{frame_body}"
    ephemeris_token = "" if ephemeris == "horizons" else f"_{safe_object_name(ephemeris)}"
    stem = (
        f"{safe_name}_{epochs['start']}_to_{epochs['stop']}_"
        f"{epochs['step']}_step{ephemeris_token}_{safe_object_name(frame_token)}"
    )
    return [directory / f"{stem}.{fmt}" for fmt in normalize_formats(formats)]


def _plot_limit(target_x, target_y, planet_positions: Mapping[str, tuple[np.ndarray, np.ndarray]]) -> float:
    """Return a symmetric plot limit that covers every drawn trajectory."""

    extents = [
        abs(float(np.min(target_x))),
        abs(float(np.max(target_x))),
        abs(float(np.min(target_y))),
        abs(float(np.max(target_y))),
    ]
    for planet_x, planet_y in planet_positions.values():
        extents.extend(
            [
                abs(float(np.min(planet_x))),
                abs(float(np.max(planet_x))),
                abs(float(np.min(planet_y))),
                abs(float(np.max(planet_y))),
            ]
        )
    lim = max(extents) if extents else 1.0
    return max(lim * 1.05, 1.0)


def _write_plot(
    object_name: str,
    epochs: Mapping[str, str],
    frame: str,
    frame_body: str,
    target_x: np.ndarray,
    target_y: np.ndarray,
    planet_positions: Mapping[str, tuple[np.ndarray, np.ndarray]],
    selected_planets: Sequence[str],
    formats: Sequence[str],
    output_dir: Path | str | None,
    figsize: tuple[float, float] | None,
    show: bool,
    ephemeris: str,
    provenance: str | None,
) -> list[Path]:
    from matplotlib import pyplot as plt

    fig, ax = plt.subplots(figsize=figsize)
    ax.plot(target_x, target_y, label=object_name, color="blue", linewidth=0.75)
    ax.scatter(
        target_x[-1],
        target_y[-1],
        color="blue",
        edgecolor="black",
        zorder=5,
        label=f"{epochs['stop']} position",
    )

    for planet, (planet_x, planet_y) in planet_positions.items():
        ax.plot(planet_x, planet_y, label=planet, color=PLANET_COLORS[planet], linewidth=1.5, alpha=0.7)
        ax.scatter(planet_x[-1], planet_y[-1], color=PLANET_COLORS[planet], edgecolor="black", zorder=5)

    sun_size = 10 if "Mercury" in selected_planets else 50
    ax.scatter(0, 0, color="yellow", marker="o", label="Sun", s=sun_size, edgecolor="orange")

    frame_label = "Heliocentric" if frame == "heliocentric" else f"{frame_body} Co-rotating"
    ax.set_xlabel(f"{frame_label} Reference Frame x (au)")
    ax.set_ylabel(f"{frame_label} Reference Frame y (au)")
    ax.grid(True, alpha=0.35)
    ax.set_aspect("equal", adjustable="box")
    lim = _plot_limit(target_x, target_y, planet_positions)
    ax.set_xlim(-lim, lim)
    ax.set_ylim(-lim, lim)
    ax.legend(loc="upper left", bbox_to_anchor=(1, 1))
    if provenance:
        fig.suptitle(f"{object_name}\n{provenance}", fontsize="small")
        fig.tight_layout(rect=(0, 0, 1, 0.94))
    else:
        fig.tight_layout()

    output_paths = build_output_paths(
        object_name,
        epochs,
        frame,
        frame_body,
        formats,
        output_dir,
        ephemeris,
    )
    for path in output_paths:
        path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(path, bbox_inches="tight")

    if show:
        plt.show()
    plt.close(fig)
    return output_paths


def plot_orbit(
    object_name: str,
    start: str | None = None,
    stop: str | None = None,
    step: str | None = None,
    frame: str = DEFAULT_FRAME,
    frame_body: str | Sequence[str] = DEFAULT_FRAME_BODY,
    planets: str | Sequence[str] = "all",
    formats: Sequence[str] = DEFAULT_FORMATS,
    output_dir: Path | str | None = None,
    figsize: tuple[float, float] | None = None,
    show: bool = False,
    include_planets: Sequence[str] = (),
    exclude_planets: Sequence[str] = (),
    auto_epochs: bool = DEFAULT_AUTO_EPOCHS,
    orbits: float = DEFAULT_ORBITS,
    samples_per_orbit: float = DEFAULT_SAMPLES_PER_ORBIT,
    ephemeris: str = DEFAULT_EPHEMERIS,
    assist_data_dir: Path | str | None = None,
    integration_epoch: str | None = None,
) -> list[Path]:
    """Plot a minor-body orbit and return the written figure paths."""

    frame = frame.lower()
    if frame not in {"heliocentric", "corotating"}:
        raise ValueError("frame must be 'heliocentric' or 'corotating'")
    ephemeris = ephemeris.lower()
    if ephemeris not in {"horizons", "assist"}:
        raise ValueError("ephemeris must be 'horizons' or 'assist'")
    frame_bodies = resolve_frame_bodies(frame_body)
    if frame == "heliocentric" and len(frame_bodies) > 1:
        raise ValueError("multiple frame bodies can only be used with the 'corotating' frame")

    epochs = resolve_epochs(
        object_name,
        start=start,
        stop=stop,
        step=step,
        auto_epochs=auto_epochs,
        orbits=orbits,
        samples_per_orbit=samples_per_orbit,
    )
    if ephemeris == "assist":
        provider = AssistEphemerisProvider(
            epochs,
            assist_data_dir=assist_data_dir,
            integration_epoch=integration_epoch,
        )
        warnings.warn(
            "ASSIST outputs are nominal integrations seeded from one Horizons "
            "state. Orbit-fit uncertainty and cometary non-gravitational "
            "parameters are not propagated.",
            UserWarning,
            stacklevel=2,
        )
    else:
        provider = HorizonsEphemerisProvider(epochs)

    target_vectors = provider.target_vectors(object_name)
    selected_planets = resolve_planets(
        planets,
        target_vectors=target_vectors,
        include_planets=include_planets,
        exclude_planets=exclude_planets,
    )

    planets_to_query = set(selected_planets)
    if frame == "corotating":
        # The frame body is needed for the rotation even when the user excludes
        # that planet from the visible plot.
        planets_to_query.update(frame_bodies)

    planet_vectors = provider.planet_vectors(planets_to_query)

    base_target_x = _column_array(target_vectors, "x")
    base_target_y = _column_array(target_vectors, "y")
    base_planet_positions = {
        planet: (_column_array(planet_vectors[planet], "x"), _column_array(planet_vectors[planet], "y"))
        for planet in selected_planets
    }

    output_paths: list[Path] = []
    for active_frame_body in frame_bodies:
        target_x = base_target_x
        target_y = base_target_y
        planet_positions = base_planet_positions
        if frame == "corotating":
            frame_x = _column_array(planet_vectors[active_frame_body], "x")
            frame_y = _column_array(planet_vectors[active_frame_body], "y")
            # Rotate every trajectory by the frame body's instantaneous longitude
            # so the selected planet remains fixed on the positive x-axis.
            target_x, target_y = transform_to_corotating_frame(base_target_x, base_target_y, frame_x, frame_y)
            planet_positions = {
                planet: transform_to_corotating_frame(planet_x, planet_y, frame_x, frame_y)
                for planet, (planet_x, planet_y) in base_planet_positions.items()
            }
        output_paths.extend(
            _write_plot(
                object_name,
                epochs,
                frame,
                active_frame_body,
                target_x,
                target_y,
                planet_positions,
                selected_planets,
                formats,
                output_dir,
                figsize,
                show,
                ephemeris,
                provider.provenance,
            )
        )
    return output_paths
