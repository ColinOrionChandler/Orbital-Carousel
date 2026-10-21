"""Command-line interface for Orbital Carousel."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

if __package__ in {None, ""}:
    # Direct file execution starts on src/orbital_carousel; add src/ so the
    # package import below resolves the same way it does after installation.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from orbital_carousel.core import (
        DEFAULT_AUTO_EPOCHS,
        DEFAULT_EPHEMERIS,
        DEFAULT_FORMATS,
        DEFAULT_FRAME,
        DEFAULT_FRAME_BODY,
        DEFAULT_ORBITS,
        DEFAULT_PLANETS,
        DEFAULT_SAMPLES_PER_ORBIT,
        DEFAULT_START,
        DEFAULT_STEP,
        DEFAULT_STOP,
        PlotRequest,
        plot_orbit,
    )
else:
    from .core import (
        DEFAULT_AUTO_EPOCHS,
        DEFAULT_EPHEMERIS,
        DEFAULT_FORMATS,
        DEFAULT_FRAME,
        DEFAULT_FRAME_BODY,
        DEFAULT_ORBITS,
        DEFAULT_PLANETS,
        DEFAULT_SAMPLES_PER_ORBIT,
        DEFAULT_START,
        DEFAULT_STEP,
        DEFAULT_STOP,
        PlotRequest,
        plot_orbit,
    )


class HelpFormatter(argparse.ArgumentDefaultsHelpFormatter, argparse.RawDescriptionHelpFormatter):
    """Show concrete defaults while preserving the examples block."""


def build_parser(prog: str = "orbital-carousel") -> argparse.ArgumentParser:
    """Build the command-line argument parser."""

    parser = argparse.ArgumentParser(
        prog=prog,
        description="Plot a minor-body orbit in heliocentric or planet co-rotating coordinates.",
        epilog=f"""Examples:
  {prog} "2015 DD349"
  {prog} "2019 OE31" --planets auto --format png
  {prog} "C/2014 OG392" --planets auto --format png
  {prog} "2000 OG44" --frame heliocentric --planets Venus,Earth,Mars,Jupiter
  {prog} "2010 RJ226" --frame-body Saturn --figsize 8 8 --output-dir plots
  {prog} "2015 DD349" --frame-body Jupiter --frame-body Saturn --format png
  {prog} "2025 NN80" --ephemeris assist --format png
""",
        formatter_class=HelpFormatter,
    )
    parser.add_argument("object_name", help="Target object name or designation for JPL Horizons.")
    parser.add_argument(
        "--start",
        default=argparse.SUPPRESS,
        help=(
            "Start date as YYYY-MM-DD, a signed astronomical year date, or "
            "JD<number>. Auto-derived when omitted."
        ),
    )
    parser.add_argument(
        "--stop",
        default=argparse.SUPPRESS,
        help=(
            "Stop date as YYYY-MM-DD, a signed astronomical year date, or "
            "JD<number>. Auto-derived when omitted."
        ),
    )
    parser.add_argument(
        "--step",
        default=argparse.SUPPRESS,
        help="Ephemeris output step size. Auto-derived when omitted.",
    )
    parser.add_argument(
        "--ephemeris",
        choices=("horizons", "assist"),
        default=DEFAULT_EPHEMERIS,
        help="Trajectory backend. ASSIST requires local extended DE441 data.",
    )
    parser.add_argument(
        "--assist-data-dir",
        type=Path,
        default=argparse.SUPPRESS,
        help=("Directory containing extended DE441 and sb441-n16.bsp. Defaults to ASSIST_DIR."),
    )
    parser.add_argument(
        "--integration-epoch",
        default=argparse.SUPPRESS,
        help=(
            "Horizons seed-state epoch for ASSIST as YYYY-MM-DD, a signed "
            "astronomical year date, or JD<number>. Defaults to today's date."
        ),
    )
    epoch_group = parser.add_mutually_exclusive_group()
    epoch_group.add_argument(
        "--auto-epochs",
        dest="auto_epochs",
        action="store_true",
        default=argparse.SUPPRESS,
        help="Scale missing start, stop, and step values from the target orbital period. Enabled by default.",
    )
    epoch_group.add_argument(
        "--no-auto-epochs",
        dest="auto_epochs",
        action="store_false",
        default=argparse.SUPPRESS,
        help=f"Use fixed missing-epoch defaults: {DEFAULT_START} to {DEFAULT_STOP} at {DEFAULT_STEP}.",
    )
    parser.add_argument(
        "--orbits",
        type=float,
        default=DEFAULT_ORBITS,
        help="Target orbit count for auto-derived date spans.",
    )
    parser.add_argument(
        "--samples-per-orbit",
        type=float,
        default=DEFAULT_SAMPLES_PER_ORBIT,
        help="Sampling density for auto-derived step sizes.",
    )
    parser.add_argument(
        "--frame",
        choices=("heliocentric", "corotating"),
        default=DEFAULT_FRAME,
        help="Reference frame for the plot.",
    )
    parser.add_argument(
        "--frame-body",
        action="append",
        default=argparse.SUPPRESS,
        help=(
            "Planet used as the fixed +x direction for co-rotating plots. "
            "May be repeated or comma-separated. Defaults to "
            f"{DEFAULT_FRAME_BODY}. Choices: {', '.join(DEFAULT_PLANETS)}."
        ),
    )
    parser.add_argument(
        "--planets",
        default="all",
        help="Planets to plot: all, auto, none, or a comma-separated planet list.",
    )
    parser.add_argument(
        "--include-planet",
        action="append",
        default=argparse.SUPPRESS,
        help="Planet to add after --planets selection. May be repeated or comma-separated.",
    )
    parser.add_argument(
        "--exclude-planet",
        action="append",
        default=argparse.SUPPRESS,
        help="Planet to remove after --planets selection. May be repeated or comma-separated.",
    )
    parser.add_argument(
        "--format",
        dest="formats",
        action="append",
        choices=("pdf", "png"),
        default=argparse.SUPPRESS,
        help=f"Output figure format. Repeat to write both. Defaults to {', '.join(DEFAULT_FORMATS)}.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=argparse.SUPPRESS,
        help="Directory for plot files. Defaults to ./<safe object name>/.",
    )
    parser.add_argument(
        "--figsize",
        type=float,
        nargs=2,
        metavar=("WIDTH", "HEIGHT"),
        default=argparse.SUPPRESS,
        help="Matplotlib figure size in inches. Defaults to Matplotlib's configured size.",
    )
    parser.add_argument("--show", action="store_true", help="Display the plot interactively after saving.")
    return parser


def request_from_args(args: argparse.Namespace) -> PlotRequest:
    """Convert parsed CLI arguments to a library request object."""

    figsize = tuple(args.figsize) if hasattr(args, "figsize") else None
    return PlotRequest(
        object_name=args.object_name,
        start=getattr(args, "start", None),
        stop=getattr(args, "stop", None),
        step=getattr(args, "step", None),
        frame=args.frame,
        frame_body=tuple(args.frame_body) if hasattr(args, "frame_body") else DEFAULT_FRAME_BODY,
        planets=args.planets,
        formats=tuple(getattr(args, "formats", DEFAULT_FORMATS)),
        output_dir=getattr(args, "output_dir", None),
        figsize=figsize,
        show=args.show,
        include_planets=tuple(getattr(args, "include_planet", ())),
        exclude_planets=tuple(getattr(args, "exclude_planet", ())),
        auto_epochs=getattr(args, "auto_epochs", DEFAULT_AUTO_EPOCHS),
        orbits=args.orbits,
        samples_per_orbit=args.samples_per_orbit,
        ephemeris=args.ephemeris,
        assist_data_dir=getattr(args, "assist_data_dir", None),
        integration_epoch=getattr(args, "integration_epoch", None),
    )


def run(request: PlotRequest) -> list[Path]:
    """Run the plot request and return written paths."""

    return plot_orbit(
        request.object_name,
        start=request.start,
        stop=request.stop,
        step=request.step,
        frame=request.frame,
        frame_body=request.frame_body,
        planets=request.planets,
        formats=request.formats,
        output_dir=request.output_dir,
        figsize=request.figsize,
        show=request.show,
        include_planets=request.include_planets,
        exclude_planets=request.exclude_planets,
        auto_epochs=request.auto_epochs,
        orbits=request.orbits,
        samples_per_orbit=request.samples_per_orbit,
        ephemeris=request.ephemeris,
        assist_data_dir=request.assist_data_dir,
        integration_epoch=request.integration_epoch,
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI."""

    parser = build_parser(prog=Path(sys.argv[0]).name if argv is None else "orbital-carousel")
    args = parser.parse_args(argv)
    try:
        output_paths = run(request_from_args(args))
    except ValueError as exc:
        parser.error(str(exc))
    for path in output_paths:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
