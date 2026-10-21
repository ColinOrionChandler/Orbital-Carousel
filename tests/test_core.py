import sys
from types import SimpleNamespace

import numpy as np
import pytest

import orbital_carousel.core as core
from orbital_carousel.core import (
    DEFAULT_LOCATIONS,
    DEFAULT_PLANETS,
    DEFAULT_START,
    DEFAULT_STOP,
    AssistEphemerisProvider,
    build_epoch_grid,
    build_output_paths,
    format_epoch_date,
    max_heliocentric_distance,
    normalize_formats,
    parse_epoch_jd,
    resolve_assist_data_paths,
    resolve_epochs,
    resolve_frame_bodies,
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


def test_build_output_paths_marks_assist_without_changing_horizons_names():
    epochs = {"start": "-1266-01-27", "stop": "2026-07-24", "step": "502d"}
    paths = build_output_paths(
        "2025 NN80",
        epochs,
        "corotating",
        "Jupiter",
        ("png",),
        ephemeris="assist",
    )

    assert paths[0].name == ("2025_NN80_-1266-01-27_to_2026-07-24_502d_step_assist_corotating_Jupiter.png")


def test_normalize_formats_deduplicates_user_formats():
    assert normalize_formats(("png", "pdf", "png")) == ("png", "pdf")


def test_transform_rotates_frame_body_onto_positive_x_axis():
    frame_x = np.array([0.0, -1.0])
    frame_y = np.array([2.0, 0.0])

    x_rot, y_rot = transform_to_corotating_frame(frame_x, frame_y, frame_x, frame_y)

    np.testing.assert_allclose(y_rot, np.array([0.0, 0.0]), atol=1e-12)
    np.testing.assert_allclose(x_rot, np.array([2.0, 1.0]), atol=1e-12)


def test_icrf_rotation_matches_j2000_ecliptic_axes():
    icrf = np.array([[19.24839131579069, -18.30022606924521, -9.968942038602028]])

    rotated = core._icrf_to_ecliptic(icrf)

    np.testing.assert_allclose(
        rotated,
        [[19.24839131579069, -20.7555465621085, -1.866913619489317]],
        atol=1e-12,
    )


def test_resolve_frame_bodies_accepts_repeated_and_comma_separated_values():
    assert resolve_frame_bodies(("Saturn,Jupiter", "Saturn")) == ["Saturn", "Jupiter"]


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
    assert np.isclose(
        max_heliocentric_distance(vectors([0.0, 3.0], [4.0, 0.0], [0.0, 12.0])), 12.36931687685298
    )


def test_resolve_epochs_defaults_to_twenty_orbits_ending_today(monkeypatch):
    monkeypatch.setattr(core, "current_utc_date", lambda: "2026-06-03")
    monkeypatch.setattr(core, "get_orbital_period_days", lambda object_name: 3348.287200520034)

    epochs = resolve_epochs("2019 OE31")

    assert epochs == {"start": "1843-01-28", "stop": "2026-06-03", "step": "28d"}


def test_resolve_epochs_derives_stop_from_explicit_start(monkeypatch):
    monkeypatch.setattr(core, "get_orbital_period_days", lambda object_name: 10.0)

    epochs = resolve_epochs("Test Object", start="2020-01-01", orbits=2, samples_per_orbit=5)

    assert epochs == {"start": "2020-01-01", "stop": "2020-01-21", "step": "2d"}


def test_resolve_epochs_derives_start_from_explicit_stop_and_preserves_step(monkeypatch):
    monkeypatch.setattr(core, "get_orbital_period_days", lambda object_name: 10.0)

    epochs = resolve_epochs("Test Object", stop="2020-01-21", step="5d", orbits=2)

    assert epochs == {"start": "2020-01-01", "stop": "2020-01-21", "step": "5d"}


def test_resolve_epochs_keeps_all_explicit_epoch_fields_without_period_lookup(monkeypatch):
    def fail_period_lookup(object_name):
        raise AssertionError("period lookup should not be needed")

    monkeypatch.setattr(core, "get_orbital_period_days", fail_period_lookup)

    epochs = resolve_epochs("Open Orbit", start="2020-01-01", stop="2020-02-01", step="7d")

    assert epochs == {"start": "2020-01-01", "stop": "2020-02-01", "step": "7d"}


def test_resolve_epochs_no_auto_uses_fixed_defaults():
    epochs = resolve_epochs("Open Orbit", auto_epochs=False)

    assert epochs == {"start": DEFAULT_START, "stop": DEFAULT_STOP, "step": "30d"}


def test_resolve_epochs_rejects_non_finite_period_when_fields_are_missing(monkeypatch):
    monkeypatch.setattr(core, "get_orbital_period_days", lambda object_name: float("nan"))

    with pytest.raises(ValueError, match="orbital period"):
        resolve_epochs("Open Orbit")


def test_resolve_epochs_supports_2025_nn80_bce_default(monkeypatch):
    monkeypatch.setattr(core, "current_utc_date", lambda: "2026-07-24")
    monkeypatch.setattr(core, "get_orbital_period_days", lambda object_name: 60127.81984559081)

    assert resolve_epochs("2025 NN80") == {
        "start": "-1266-01-27",
        "stop": "2026-07-24",
        "step": "502d",
    }


@pytest.mark.parametrize(
    "value",
    ["-13000-01-01", "-1266-01-27", "0000-01-01", "12000-01-01", "17000-01-01"],
)
def test_epoch_parser_round_trips_extended_calendar_years(value):
    assert format_epoch_date(parse_epoch_jd(value)) == value


def test_epoch_parser_accepts_julian_dates():
    assert parse_epoch_jd("JD2451545.0") == 2451545.0
    assert format_epoch_date(2451545.0) == "2000-01-01"


def test_epoch_grid_includes_stop_for_fixed_and_unitless_steps():
    fixed = build_epoch_grid({"start": "2020-01-01", "stop": "2020-01-03", "step": "36h"})
    unitless = build_epoch_grid({"start": "2020-01-01", "stop": "2020-01-02", "step": "4"})

    assert [format_epoch_date(jd) for jd in fixed.jds] == [
        "2020-01-01",
        "2020-01-02",
        "2020-01-03",
    ]
    assert len(unitless.jds) == 5
    assert unitless.jds[0] == parse_epoch_jd("2020-01-01")
    assert unitless.jds[-1] == parse_epoch_jd("2020-01-02")


def test_epoch_grid_calendar_months_skip_invalid_dates_and_include_stop():
    grid = build_epoch_grid({"start": "2020-01-31", "stop": "2020-05-31", "step": "1mo"})

    assert [format_epoch_date(jd) for jd in grid.jds] == [
        "2020-01-31",
        "2020-03-31",
        "2020-05-31",
    ]


def test_epoch_grid_rejects_non_time_assist_step():
    with pytest.raises(ValueError, match="ASSIST step"):
        build_epoch_grid({"start": "2020-01-01", "stop": "2020-01-02", "step": "VAR 600"})


def test_get_orbital_period_days_accepts_period_column_aliases(monkeypatch):
    monkeypatch.setattr(
        core, "get_elements", lambda object_name, locations=DEFAULT_LOCATIONS: {"period": [12.5]}
    )

    assert core.get_orbital_period_days("2019 OE31") == 12.5


def test_get_orbital_period_days_rejects_missing_period(monkeypatch):
    monkeypatch.setattr(core, "get_elements", lambda object_name, locations=DEFAULT_LOCATIONS: {"e": [1.1]})

    with pytest.raises(ValueError, match="finite orbital period"):
        core.get_orbital_period_days("Open Orbit")


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


def test_plot_orbit_writes_one_output_per_corotating_frame_body(tmp_path, monkeypatch):
    import matplotlib

    matplotlib.use("Agg", force=True)
    requests = []

    def fake_get_positions(object_name, epochs):
        requests.append(object_name)
        if object_name == "599":
            return vectors([5.0, 0.0], [0.0, 5.0])
        if object_name == "699":
            return vectors([9.0, 0.0], [0.0, 9.0])
        return vectors([2.0, 3.0], [0.0, 1.0])

    monkeypatch.setattr(core, "get_positions", fake_get_positions)

    paths = core.plot_orbit(
        "2015 DD349",
        start="2026-01-01",
        stop="2026-02-01",
        step="15d",
        frame_body=("Jupiter,Saturn",),
        planets="none",
        formats=("png",),
        output_dir=tmp_path,
        figsize=(4.0, 4.0),
    )

    assert [path.name for path in paths] == [
        "2015_DD349_2026-01-01_to_2026-02-01_15d_step_corotating_Jupiter.png",
        "2015_DD349_2026-01-01_to_2026-02-01_15d_step_corotating_Saturn.png",
    ]
    assert requests == ["2015 DD349", "599", "699"]
    assert all(path.exists() and path.stat().st_size > 0 for path in paths)


def test_assist_data_path_explicit_directory_precedes_environment(tmp_path, monkeypatch):
    explicit = tmp_path / "explicit"
    environment = tmp_path / "environment"
    explicit.mkdir()
    environment.mkdir()
    for directory in (explicit, environment):
        (directory / "linux_m13000p17000.441").touch()
        (directory / "sb441-n16.bsp").touch()
    monkeypatch.setenv("ASSIST_DIR", str(environment))

    assert resolve_assist_data_paths(explicit) == (
        explicit / "linux_m13000p17000.441",
        explicit / "sb441-n16.bsp",
    )


def test_assist_data_path_error_lists_required_files(tmp_path):
    with pytest.raises(ValueError, match=r"linux_m13000p17000\.441.*sb441-n16\.bsp"):
        resolve_assist_data_paths(tmp_path)


def test_assist_provider_reports_out_of_de441_coverage(tmp_path, monkeypatch):
    (tmp_path / "linux_m13000p17000.441").touch()
    (tmp_path / "sb441-n16.bsp").touch()

    class OutOfRangeEphem:
        jd_ref = 2451545.0

        def __init__(self, planets_path, asteroids_path):
            pass

        def get_particle(self, body, relative_time):
            raise RuntimeError("Date is outside the ephemeris range")

    monkeypatch.setitem(sys.modules, "assist", SimpleNamespace(Ephem=OutOfRangeEphem))
    monkeypatch.setitem(sys.modules, "rebound", SimpleNamespace())

    with pytest.raises(ValueError, match="outside the loaded ephemeris coverage"):
        AssistEphemerisProvider(
            {"start": "-14000-01-01", "stop": "-13999-01-01", "step": "30d"},
            assist_data_dir=tmp_path,
            integration_epoch="2026-01-01",
        )


def test_assist_provider_uses_independent_backward_and_forward_integrations(tmp_path, monkeypatch):
    (tmp_path / "linux_m13000p17000.441").touch()
    (tmp_path / "sb441-n16.bsp").touch()
    integrations = []
    seed_queries = []

    class FakeParticle:
        def __init__(self, xyz, velocity=(0.0, 0.0, 0.0)):
            self.xyz = list(xyz)
            self.velocity = np.asarray(velocity, dtype=float)

    class FakeEphem:
        jd_ref = 2451545.0

        def __init__(self, planets_path, asteroids_path):
            self.planets_path = planets_path
            self.asteroids_path = asteroids_path

        def get_particle(self, body, relative_time):
            if body == "Sun":
                return FakeParticle((0.0, 0.0, 0.0))
            return FakeParticle((float(relative_time), 0.0, 0.0))

    class FakeSimulation:
        def __init__(self):
            self.particles = []
            self.t = 0.0

        def add(self, **state):
            self.particles.append(
                FakeParticle(
                    (state["x"], state["y"], state["z"]),
                    (state["vx"], state["vy"], state["vz"]),
                )
            )

    class FakeExtras:
        def __init__(self, simulation, ephem):
            self.simulation = simulation
            self.seed_time = simulation.t
            self.calls = []
            integrations.append(self.calls)

        def integrate_or_interpolate(self, relative_time):
            self.calls.append(float(relative_time))
            particle = self.simulation.particles[0]
            elapsed = relative_time - self.seed_time
            particle.xyz = list(np.asarray((10.0, 0.0, 0.0)) + particle.velocity * elapsed)

    monkeypatch.setitem(sys.modules, "assist", SimpleNamespace(Ephem=FakeEphem, Extras=FakeExtras))
    monkeypatch.setitem(sys.modules, "rebound", SimpleNamespace(Simulation=FakeSimulation))

    def fake_seed(object_name, epoch_jd):
        seed_queries.append((object_name, epoch_jd))
        return {
            "x": [10.0],
            "y": [0.0],
            "z": [0.0],
            "vx": [1.0],
            "vy": [0.0],
            "vz": [0.0],
        }

    monkeypatch.setattr(core, "get_barycentric_state", fake_seed)
    provider = AssistEphemerisProvider(
        {"start": "JD2451544", "stop": "JD2451546", "step": "1d"},
        assist_data_dir=tmp_path,
        integration_epoch="JD2451545",
    )
    target = provider.target_vectors("2025 NN80")

    np.testing.assert_allclose(target["x"], [9.0, 10.0, 11.0])
    assert integrations == [[-1.0], [1.0]]
    assert seed_queries == [("2025 NN80", 2451545.0)]
    assert "seed 2000-01-01 TDB" in provider.provenance


def test_plot_orbit_dispatches_to_assist_and_marks_output(tmp_path, monkeypatch):
    import matplotlib

    matplotlib.use("Agg", force=True)

    class FakeAssistProvider:
        provenance = "ASSIST nominal integration; test seed"

        def __init__(self, epochs, **kwargs):
            self.epochs = epochs

        def target_vectors(self, object_name):
            return vectors([2.0, 3.0], [0.0, 1.0])

        def planet_vectors(self, planets):
            return {"Jupiter": vectors([5.0, 0.0], [0.0, 5.0])}

    monkeypatch.setattr(core, "AssistEphemerisProvider", FakeAssistProvider)
    with pytest.warns(UserWarning, match="nominal integrations"):
        paths = core.plot_orbit(
            "2025 NN80",
            start="2026-01-01",
            stop="2026-02-01",
            step="15d",
            planets="Jupiter",
            ephemeris="assist",
            formats=("png",),
            output_dir=tmp_path,
            figsize=(4.0, 4.0),
        )

    assert paths[0].name.endswith("_step_assist_corotating_Jupiter.png")
    assert paths[0].exists() and paths[0].stat().st_size > 0


def test_plot_orbit_defaults_include_updated_dates_and_locations(tmp_path, monkeypatch):
    import matplotlib

    matplotlib.use("Agg", force=True)
    requests = []

    def fake_get_positions(object_name, epochs, locations=DEFAULT_LOCATIONS):
        requests.append((object_name, locations, epochs["start"], epochs["stop"], epochs["step"]))
        return vectors([2.0, 3.0], [0.0, 1.0])

    monkeypatch.setattr(core, "get_positions", fake_get_positions)
    monkeypatch.setattr(core, "current_utc_date", lambda: "2026-06-03")
    monkeypatch.setattr(core, "get_orbital_period_days", lambda object_name: 3348.287200520034)

    paths = core.plot_orbit(
        "2019 OE31",
        planets="Jupiter",
        formats=("png",),
        output_dir=tmp_path,
    )

    assert paths
    object_requests = [call for call in requests if call[0] == "2019 OE31"]
    assert len(object_requests) == 1
    assert object_requests[0][1] == DEFAULT_LOCATIONS
    assert object_requests[0][2] == "1843-01-28"
    assert object_requests[0][3] == "2026-06-03"
    assert object_requests[0][4] == "28d"
