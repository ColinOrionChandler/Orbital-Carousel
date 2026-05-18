from orbital_carousel.cli import build_parser, request_from_args


def test_parser_defaults_are_jupiter_corotating_all_planets():
    parser = build_parser()
    args = parser.parse_args(["2015 DD349"])
    request = request_from_args(args)

    assert request.frame == "corotating"
    assert request.frame_body == "Jupiter"
    assert request.planets == "all"
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


def test_help_does_not_leak_derived_none_defaults():
    help_text = build_parser().format_help()

    assert "default: None" not in help_text
    assert "Defaults to ./<safe object" in help_text
    assert "name>/." in help_text
    assert "today's UTC date." in help_text
