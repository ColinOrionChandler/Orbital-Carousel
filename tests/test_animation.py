from contextlib import contextmanager
from types import SimpleNamespace

import matplotlib
import numpy as np
import pytest
from matplotlib.animation import FFMpegWriter

from orbital_carousel import core

matplotlib.use("Agg")


def test_frame_selection_uses_elapsed_time_and_preserves_endpoints():
    jds = np.array([0.0, 1, 2, 3, 6, 9])
    np.testing.assert_array_equal(core._movie_indices(jds, 2, 2), [0, 3, 4, 5])
    np.testing.assert_array_equal(core._movie_indices(jds, 24, 30), np.arange(len(jds)))
    np.testing.assert_array_equal(core._movie_indices(jds[:1], 24, 30), [0])
    with pytest.raises(ValueError, match="first and last"):
        core._movie_indices(jds, 1, 1)


@pytest.mark.parametrize(("fps", "duration"), [(0, 30), (1.5, 30), (24, float("nan")), (24, 0.01)])
def test_invalid_playback_fails_before_fetch(fps, duration):
    with pytest.raises(ValueError, match="duration|fps"):
        core.plot_orbit("Test", formats=("mp4",), fps=fps, duration=duration)


def test_missing_encoder_fails_before_fetch(monkeypatch):
    monkeypatch.setattr(
        core.subprocess, "run", lambda *a, **kw: SimpleNamespace(stdout=" V..... libx264rgb ")
    )
    with pytest.raises(ValueError, match="libx264 encoder"):
        core.plot_orbit("Test", formats=("mp4",))


@pytest.mark.parametrize(("ephemeris", "frame"), [("horizons", "heliocentric"), ("assist", "corotating")])
def test_movie_and_still_share_vectors_and_show_full_tracks(tmp_path, monkeypatch, ephemeris, frame):
    dates = 2451544.5 + np.array([0, 0.25, 1, 3, 4])
    target = {"datetime_jd": dates, "x": np.arange(5.0), "y": np.zeros(5)}
    planet = {"datetime_jd": dates, "x": np.zeros(5), "y": np.arange(1.0, 6.0)}
    calls = []

    def positions(name, epochs):
        calls.append(name)
        return target if name == "Test" else planet

    monkeypatch.setattr(core, "get_positions", positions)
    monkeypatch.setattr(core.AssistEphemerisProvider, "__init__", lambda self, *a, **kw: None)
    monkeypatch.setattr(
        core.AssistEphemerisProvider, "provenance", "ASSIST nominal integration; seed test", raising=False
    )
    monkeypatch.setattr(
        core.AssistEphemerisProvider, "target_vectors", lambda self, name: positions(name, None)
    )
    monkeypatch.setattr(
        core.AssistEphemerisProvider,
        "planet_vectors",
        lambda self, planets: {p: positions(core.PLANET_IDS[p], None) for p in planets},
    )
    monkeypatch.setattr(core, "_check_movie_settings", lambda *a: None)
    frames = []

    @contextmanager
    def saving(self, fig, path, dpi):
        self.fig = fig
        yield
        path.write_bytes(b"finished movie")

    def grab_frame(self):
        ax = self.fig.axes[0]
        frames.append(
            (
                ax.get_title(),
                ax.get_xlim(),
                ax.get_ylim(),
                ax.get_aspect(),
                np.array(ax.lines[0].get_xydata()),
                np.array(ax.collections[0].get_offsets()),
                np.array(ax.collections[1].get_offsets()),
            )
        )

    monkeypatch.setattr(FFMpegWriter, "saving", saving)
    monkeypatch.setattr(FFMpegWriter, "grab_frame", grab_frame)
    paths = core.plot_orbit(
        "Test",
        start="JD2451544.5",
        stop="JD2451550.5",
        step="1d",
        ephemeris=ephemeris,
        frame=frame,
        planets="Jupiter",
        formats=(".MP4", "png", "mp4"),
        output_dir=tmp_path,
        fps=1,
        duration=3,
    )
    assert calls == ["Test", "599"]
    assert [p.suffix for p in paths] == [".mp4", ".png"]
    assert paths[0].read_bytes() == b"finished movie"
    assert paths[1].read_bytes().startswith(b"\x89PNG")
    assert len(frames) == 3
    for (title, xlim, ylim, aspect, track, marker, jupiter), index in zip(frames, [0, 2, 4], strict=True):
        assert title.endswith(f"(JD {dates[index]:.6f})")
        assert xlim == ylim == frames[0][1]
        assert aspect == 1
        assert len(track) == index + 1
        np.testing.assert_allclose(marker[0], track[-1])
        expected = np.column_stack((target["x"][: index + 1], target["y"][: index + 1]))
        if frame == "corotating":
            expected = np.column_stack((expected[:, 1], -expected[:, 0]))
        np.testing.assert_allclose(track, expected, atol=1e-12)
        expected_planet = [index + 1, 0] if frame == "corotating" else [0, index + 1]
        np.testing.assert_allclose(jupiter[0], expected_planet, atol=1e-12)


def test_encoding_failure_preserves_previous_movie(tmp_path, monkeypatch):
    from matplotlib import pyplot as plt

    movie = tmp_path / "orbit.mp4"
    movie.write_bytes(b"previous movie")

    @contextmanager
    def failing_save(self, fig, path, dpi):
        path.write_bytes(b"partial")
        yield
        raise OSError("encoder failed")

    monkeypatch.setattr(FFMpegWriter, "saving", failing_save)
    monkeypatch.setattr(FFMpegWriter, "grab_frame", lambda self: None)
    fig, ax = plt.subplots()
    try:
        with pytest.raises(OSError, match="encoder failed"):
            core._write_movie(fig, ax, movie, [], np.array([1.0]), [0], 24)
    finally:
        plt.close(fig)
    assert movie.read_bytes() == b"previous movie"
    assert list(tmp_path.iterdir()) == [movie]
