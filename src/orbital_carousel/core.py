"""Core plotting and orbit-frame utilities for Orbital Carousel."""

from __future__ import annotations

from dataclasses import dataclass
import datetime as dt
from pathlib import Path
from typing import Iterable, Mapping, Sequence

import numpy as np
from astroquery.jplhorizons import Horizons

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
DEFAULT_LOCATIONS = "X05,705"


@dataclass(frozen=True)
class PlotRequest:
    """Resolved plot settings used by the CLI and the library entry point."""

    object_name: str
    start: str = DEFAULT_START
    stop: str = DEFAULT_STOP
    step: str = DEFAULT_STEP
    frame: str = DEFAULT_FRAME
    frame_body: str = DEFAULT_FRAME_BODY
    planets: str | Sequence[str] = "all"
    formats: Sequence[str] = DEFAULT_FORMATS
    output_dir: Path | str | None = None
    figsize: tuple[float, float] | None = None
    show: bool = False
    include_planets: Sequence[str] = ()
    exclude_planets: Sequence[str] = ()


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


def get_positions(object_name: str, epochs: Mapping[str, str], locations: str = DEFAULT_LOCATIONS):
    """Return JPL Horizons heliocentric vectors for an object over epochs."""

    query = Horizons(id=object_name, location=locations, epochs=dict(epochs))
    return query.vectors(cache=False)


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
    start: str = DEFAULT_START,
    stop: str = DEFAULT_STOP,
    step: str = DEFAULT_STEP,
    frame: str = DEFAULT_FRAME,
    frame_body: str = DEFAULT_FRAME_BODY,
    planets: str | Sequence[str] = "all",
    formats: Sequence[str] = DEFAULT_FORMATS,
    output_dir: Path | str | None = None,
    figsize: tuple[float, float] | None = None,
    show: bool = False,
    include_planets: Sequence[str] = (),
    exclude_planets: Sequence[str] = (),
) -> list[Path]:
    """Plot a minor-body orbit and return the written figure paths."""

    frame = frame.lower()
    if frame not in {"heliocentric", "corotating"}:
        raise ValueError("frame must be 'heliocentric' or 'corotating'")
    frame_body = canonical_planet_name(frame_body)

    epochs = {"start": start, "stop": stop, "step": step}
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
