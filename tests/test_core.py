import numpy as np

import orbital_carousel.core as core
from orbital_carousel.core import (
    DEFAULT_LOCATIONS,
    DEFAULT_START,
    DEFAULT_STOP,
    DEFAULT_PLANETS,
    build_output_paths,
    max_heliocentric_distance,
    normalize_formats,
    resolve_planets,
    safe_object_name,
    transform_to_corotating_frame,
)


def vectors(x, y=None, z=None):
    x = np.asarray(x, dtype=float)
    y = np.zeros_like(x) if y is None else np.asarray(y, dtype=float)
    z = np.zeros_like(x) if z is None else np.asarray(z, dtype=float)
    return {"x": x, "y": y, "z": z}


def test_safe_object_name_replaces_spaces_and_slashes():
    assert safe_object_name("C/2014 OG392") == "C+2014_OG392"


def test_build_output_paths_uses_safe_default_directory_and_frame_token():
    epochs = {"start": "1800-01-01", "stop": "2026-05-18", "step": "30d"}
    paths = build_output_paths("C/2014 OG392", epochs, "corotating", "Jupiter")

    assert [str(path) for path in paths] == [
        "C+2014_OG392/C+2014_OG392_1800-01-01_to_2026-05-18_30d_step_corotating_Jupiter.pdf",
        "C+2014_OG392/C+2014_OG392_1800-01-01_to_2026-05-18_30d_step_corotating_Jupiter.png",
    ]


def test_build_output_paths_honors_output_dir_and_format_order():
    epochs = {"start": "2020-01-01", "stop": "2021-01-01", "step": "10d"}
    paths = build_output_paths("2015 DD349", epochs, "heliocentric", "Jupiter", ("png",), "plots")

    assert [str(path) for path in paths] == [
        "plots/2015_DD349_2020-01-01_to_2021-01-01_10d_step_heliocentric.png"
    ]


def test_normalize_formats_deduplicates_user_formats():
    assert normalize_formats(("png", "pdf", "png")) == ("png", "pdf")


def test_transform_rotates_frame_body_onto_positive_x_axis():
    frame_x = np.array([0.0, -1.0])
    frame_y = np.array([2.0, 0.0])

    x_rot, y_rot = transform_to_corotating_frame(frame_x, frame_y, frame_x, frame_y)

    np.testing.assert_allclose(y_rot, np.array([0.0, 0.0]), atol=1e-12)
    np.testing.assert_allclose(x_rot, np.array([2.0, 1.0]), atol=1e-12)


def test_auto_planets_stop_at_next_outer_planet():
    selected = resolve_planets("auto", target_vectors=vectors([1.0, 3.0]))

    assert selected == ["Mercury", "Venus", "Earth", "Mars", "Jupiter"]


def test_auto_planets_include_all_for_beyond_neptune():
    selected = resolve_planets("auto", target_vectors=vectors([35.0]))

    assert selected == list(DEFAULT_PLANETS)


def test_planet_selection_include_and_exclude_controls():
    selected = resolve_planets("none", include_planets=("Mars,Jupiter",), exclude_planets=("Mars",))

    assert selected == ["Jupiter"]


def test_max_heliocentric_distance_uses_xyz():
    assert np.isclose(max_heliocentric_distance(vectors([0.0, 3.0], [4.0, 0.0], [0.0, 12.0])), 12.36931687685298)


def test_plot_orbit_uses_mocked_horizons_and_writes_requested_format(tmp_path, monkeypatch):
    import matplotlib

    matplotlib.use("Agg", force=True)

    def fake_get_positions(object_name, epochs):
        if object_name == "599":
            return vectors([5.0, 0.0], [0.0, 5.0])
        return vectors([2.0, 3.0], [0.0, 1.0])

    monkeypatch.setattr(core, "get_positions", fake_get_positions)

    paths = core.plot_orbit(
        "2015 DD349",
        start="2026-01-01",
        stop="2026-02-01",
        step="15d",
        planets="Jupiter",
        formats=("png",),
        output_dir=tmp_path,
        figsize=(4.0, 4.0),
    )

    assert len(paths) == 1
    assert paths[0].suffix == ".png"
    assert paths[0].exists()
    assert paths[0].stat().st_size > 0


def test_plot_orbit_defaults_include_updated_dates_and_locations(tmp_path, monkeypatch):
    import matplotlib

    matplotlib.use("Agg", force=True)
    requests = []

    def fake_get_positions(object_name, epochs, locations=DEFAULT_LOCATIONS):
        requests.append((object_name, locations, epochs["start"], epochs["stop"]))
        return vectors([2.0, 3.0], [0.0, 1.0])

    monkeypatch.setattr(core, "get_positions", fake_get_positions)

    paths = core.plot_orbit(
        "2015 DD349",
        planets="Jupiter",
        formats=("png",),
        output_dir=tmp_path,
    )

    assert paths
    object_requests = [call for call in requests if call[0] == "2015 DD349"]
    assert len(object_requests) == 1
    assert object_requests[0][1] == DEFAULT_LOCATIONS
    assert object_requests[0][2] == DEFAULT_START
    assert object_requests[0][3] == DEFAULT_STOP
