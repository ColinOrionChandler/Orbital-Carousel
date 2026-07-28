import subprocess
import sys
from pathlib import Path

from orbital_carousel.cli import build_parser, request_from_args


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_parser_defaults_are_jupiter_corotating_all_planets():
    parser = build_parser()
    args = parser.parse_args(["2015 DD349"])
    request = request_from_args(args)

    assert request.frame == "corotating"
    assert request.frame_body == "Jupiter"
    assert request.planets == "all"
    assert request.ephemeris == "horizons"
    assert request.assist_data_dir is None
    assert request.integration_epoch is None
    assert request.start is None
    assert request.stop is None
    assert request.step is None
    assert request.auto_epochs is True
    assert request.orbits == 20
    assert request.samples_per_orbit == 120
    assert request.formats == ("pdf", "png")
    assert request.output_dir is None
    assert request.figsize is None


def test_parser_accepts_repeated_formats_and_planet_overrides():
    parser = build_parser()
    args = parser.parse_args(
        [
            "C/2014 OG392",
            "--planets",
            "auto",
            "--include-planet",
            "Neptune",
            "--exclude-planet",
            "Mercury,Venus",
            "--format",
            "png",
            "--figsize",
            "8",
            "6",
        ]
    )
    request = request_from_args(args)

    assert request.planets == "auto"
    assert request.include_planets == ("Neptune",)
    assert request.exclude_planets == ("Mercury,Venus",)
    assert request.formats == ("png",)
    assert request.figsize == (8.0, 6.0)


def test_parser_accepts_multiple_frame_bodies():
    parser = build_parser()
    args = parser.parse_args(
        [
            "2015 DD349",
            "--frame-body",
            "Jupiter,Saturn",
            "--frame-body",
            "Mars",
        ]
    )
    request = request_from_args(args)

    assert request.frame_body == ("Jupiter,Saturn", "Mars")


def test_parser_accepts_assist_backend_settings(tmp_path):
    parser = build_parser()
    args = parser.parse_args(
        [
            "2025 NN80",
            "--ephemeris",
            "assist",
            "--assist-data-dir",
            str(tmp_path),
            "--integration-epoch",
            "JD2451545.0",
        ]
    )
    request = request_from_args(args)

    assert request.ephemeris == "assist"
    assert request.assist_data_dir == tmp_path
    assert request.integration_epoch == "JD2451545.0"


def test_parser_accepts_manual_epoch_compatibility_mode():
    parser = build_parser()
    args = parser.parse_args(
        [
            "2019 OE31",
            "--no-auto-epochs",
            "--start",
            "2000-01-01",
            "--stop",
            "2030-01-01",
            "--step",
            "30d",
        ]
    )
    request = request_from_args(args)

    assert request.auto_epochs is False
    assert request.start == "2000-01-01"
    assert request.stop == "2030-01-01"
    assert request.step == "30d"


def test_help_does_not_leak_derived_none_defaults():
    help_text = build_parser().format_help()
    normalized_help = " ".join(help_text.split())

    assert "default: None" not in help_text
    assert "Defaults to ./<safe object" in help_text
    assert "name>/." in help_text
    assert "Auto-derived when omitted." in normalized_help
    assert "May be repeated or comma-separated." in normalized_help
    assert "--ephemeris {horizons,assist}" in help_text
    assert "--assist-data-dir" in help_text
    assert "--integration-epoch" in help_text
    assert "2019 OE31" in help_text


def test_help_uses_requested_program_name():
    help_text = build_parser(prog="corotating-carousel").format_help()

    assert "usage: corotating-carousel" in help_text
    assert 'corotating-carousel "2015 DD349"' in help_text
    assert 'corotating-carousel "2019 OE31" --planets auto --format png' in help_text
    assert 'corotating-carousel "2015 DD349" --frame-body Jupiter --frame-body Saturn --format png' in help_text
    assert 'corotating-carousel "2025 NN80" --ephemeris assist --format png' in help_text


def test_pyproject_installs_primary_and_legacy_commands():
    pyproject = (REPO_ROOT / "pyproject.toml").read_text()

    assert 'orbital-carousel = "orbital_carousel.cli:main"' in pyproject
    assert 'corotating-carousel = "orbital_carousel.cli:main"' in pyproject


def test_cli_file_can_show_help_from_source_tree():
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "src" / "orbital_carousel" / "cli.py"), "-h"],
        cwd=REPO_ROOT,
        capture_output=True,
        check=True,
        text=True,
    )

    assert "Plot a minor-body orbit" in result.stdout
