"""Core plotting and orbit-frame utilities for Orbital Carousel."""

from __future__ import annotations

from dataclasses import dataclass
import datetime as dt
import math
from pathlib import Path
import time
from typing import Iterable, Mapping, Sequence

import numpy as np
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


@dataclass(frozen=True)
class PlotRequest:
    """Resolved plot settings used by the CLI and the library entry point."""

    object_name: str
    start: str | None = None
    stop: str | None = None
    step: str | None = None
    frame: str = DEFAULT_FRAME
    frame_body: str = DEFAULT_FRAME_BODY
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


def current_utc_date() -> str:
    """Return today's UTC date as a Horizons-friendly ISO date."""

    return str(dt.datetime.now(dt.timezone.utc).date())


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


def _julian_day_for_date(date: dt.date) -> float:
    """Return the Julian Date at 00:00 UTC for a Gregorian calendar date."""

    month = date.month
    year = date.year
    adjustment = (14 - month) // 12
    adjusted_year = year + 4800 - adjustment
    adjusted_month = month + 12 * adjustment - 3
    julian_day_number = (
        date.day
        + ((153 * adjusted_month + 2) // 5)
        + 365 * adjusted_year
        + adjusted_year // 4
        - adjusted_year // 100
        + adjusted_year // 400
        - 32045
    )
    return julian_day_number - 0.5


def _parse_iso_date(value: str, field_name: str) -> dt.date:
    try:
        return dt.date.fromisoformat(value)
    except ValueError:
        raise ValueError(
            f"{field_name} must be an ISO date (YYYY-MM-DD) when auto epochs derive a date; got {value!r}"
        ) from None


def get_elements(object_name: str, locations: str = DEFAULT_LOCATIONS):
    """Return JPL Horizons orbital elements for an object at the current UTC date."""

    epoch = _julian_day_for_date(_parse_iso_date(current_utc_date(), "current UTC date"))
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
    """Resolve manual and orbit-scaled epoch settings into a Horizons epoch map."""

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
            stop_date = _parse_iso_date(current_utc_date(), "current UTC date")
            start_date = stop_date - dt.timedelta(days=span_days)
        elif start is None:
            stop_date = _parse_iso_date(stop, "stop")
            start_date = stop_date - dt.timedelta(days=span_days)
        else:
            start_date = _parse_iso_date(start, "start")
            stop_date = start_date + dt.timedelta(days=span_days)
        start = start_date.isoformat()
        stop = stop_date.isoformat()

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
) -> list[Path]:
    """Build destination paths without creating directories or files."""

    safe_name = safe_object_name(object_name)
    directory = Path(output_dir) if output_dir is not None else Path(safe_name)
    frame_token = "heliocentric" if frame == "heliocentric" else f"corotating_{frame_body}"
    stem = (
        f"{safe_name}_{epochs['start']}_to_{epochs['stop']}_"
        f"{epochs['step']}_step_{safe_object_name(frame_token)}"
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


def plot_orbit(
    object_name: str,
    start: str | None = None,
    stop: str | None = None,
    step: str | None = None,
    frame: str = DEFAULT_FRAME,
    frame_body: str = DEFAULT_FRAME_BODY,
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
) -> list[Path]:
    """Plot a minor-body orbit and return the written figure paths."""

    frame = frame.lower()
    if frame not in {"heliocentric", "corotating"}:
        raise ValueError("frame must be 'heliocentric' or 'corotating'")
    frame_body = canonical_planet_name(frame_body)

    epochs = resolve_epochs(
        object_name,
        start=start,
        stop=stop,
        step=step,
        auto_epochs=auto_epochs,
        orbits=orbits,
        samples_per_orbit=samples_per_orbit,
    )
    target_vectors = get_positions(object_name, epochs)
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
        planets_to_query.add(frame_body)

    planet_vectors = {
        planet: get_positions(PLANET_IDS[planet], epochs)
        for planet in DEFAULT_PLANETS
        if planet in planets_to_query
    }

    target_x = _column_array(target_vectors, "x")
    target_y = _column_array(target_vectors, "y")
    planet_positions = {
        planet: (_column_array(planet_vectors[planet], "x"), _column_array(planet_vectors[planet], "y"))
        for planet in selected_planets
    }

    if frame == "corotating":
        frame_x = _column_array(planet_vectors[frame_body], "x")
        frame_y = _column_array(planet_vectors[frame_body], "y")
        # Rotate every trajectory by the frame body's instantaneous longitude
        # so the selected planet remains fixed on the positive x-axis.
        target_x, target_y = transform_to_corotating_frame(target_x, target_y, frame_x, frame_y)
        planet_positions = {
            planet: transform_to_corotating_frame(planet_x, planet_y, frame_x, frame_y)
            for planet, (planet_x, planet_y) in planet_positions.items()
        }

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
    fig.tight_layout()

    output_paths = build_output_paths(object_name, epochs, frame, frame_body, formats, output_dir)
    for path in output_paths:
        path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(path, bbox_inches="tight")

    if show:
        plt.show()
    plt.close(fig)
    return output_paths
