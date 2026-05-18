"""Command-line interface for Orbital Carousel."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from .core import (
    DEFAULT_FORMATS,
    DEFAULT_FRAME,
    DEFAULT_FRAME_BODY,
    DEFAULT_PLANETS,
    DEFAULT_START,
    DEFAULT_STEP,
    PlotRequest,
    plot_orbit,
)


class HelpFormatter(argparse.ArgumentDefaultsHelpFormatter, argparse.RawDescriptionHelpFormatter):
    """Show concrete defaults while preserving the examples block."""


def build_parser() -> argparse.ArgumentParser:
    """Build the `corotating-carousel` argument parser."""

    parser = argparse.ArgumentParser(
        prog="corotating-carousel",
        description="Plot a minor-body orbit in heliocentric or planet co-rotating coordinates.",
        epilog="""Examples:
  corotating-carousel "2015 DD349"
  corotating-carousel "C/2014 OG392" --planets auto --format png
  corotating-carousel "2000 OG44" --frame heliocentric --planets Venus,Earth,Mars,Jupiter
  corotating-carousel "2010 RJ226" --frame-body Saturn --figsize 8 8 --output-dir plots
""",
        formatter_class=HelpFormatter,
    )
    parser.add_argument("object_name", help="Target object name or designation for JPL Horizons.")
    parser.add_argument("--start", default=DEFAULT_START, help="Start date passed to Horizons vector queries.")
    parser.add_argument(
        "--stop",
        default=argparse.SUPPRESS,
        help="Stop date passed to Horizons vector queries. Defaults to today's UTC date.",
    )
    parser.add_argument("--step", default=DEFAULT_STEP, help="Horizons vector-query step size.")
    parser.add_argument(
        "--frame",
        choices=("heliocentric", "corotating"),
        default=DEFAULT_FRAME,
        help="Reference frame for the plot.",
    )
    parser.add_argument(
        "--frame-body",
        choices=DEFAULT_PLANETS,
        default=DEFAULT_FRAME_BODY,
        help="Planet used as the fixed +x direction for co-rotating plots.",
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
        start=args.start,
        stop=getattr(args, "stop", None),
        step=args.step,
        frame=args.frame,
        frame_body=args.frame_body,
        planets=args.planets,
        formats=tuple(getattr(args, "formats", DEFAULT_FORMATS)),
        output_dir=getattr(args, "output_dir", None),
        figsize=figsize,
        show=args.show,
        include_planets=tuple(getattr(args, "include_planet", ())),
        exclude_planets=tuple(getattr(args, "exclude_planet", ())),
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
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI."""

    parser = build_parser()
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
