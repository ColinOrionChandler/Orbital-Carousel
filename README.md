# Orbital Carousel

Orbital Carousel plots small-body orbits in heliocentric or planet co-rotating
reference frames. It is a standalone version of the old `coc_tools`
`corotating.py` plotting script, with an installable command-line interface and
configurable output products.

## Install

From this checkout:

```bash
python -m pip install -e .
```

For tests:

```bash
python -m pip install -e ".[test]"
```

## Command Line

The main command is `corotating-carousel`:

```bash
corotating-carousel "2015 DD349"
```

By default this writes both PDF and PNG plots into a directory named after the
object, with spaces replaced by underscores and `/` replaced by `+`.

Common options:

```bash
corotating-carousel "C/2014 OG392" --planets auto --format png
corotating-carousel "2000 OG44" --frame heliocentric --planets Venus,Earth,Mars,Jupiter
corotating-carousel "2010 RJ226" --frame-body Saturn --figsize 8 8 --output-dir plots
corotating-carousel "2015 DD349" --exclude-planet Mercury --exclude-planet Venus
```

`--planets auto` first queries the target, finds its maximum heliocentric
distance across the requested epochs, and plots planets through the next planet
outside that distance. Objects beyond Neptune keep all supported planets.

## Python API

```python
from orbital_carousel import plot_orbit

paths = plot_orbit(
    "2015 DD349",
    frame="corotating",
    frame_body="Jupiter",
    planets="all",
    formats=("pdf", "png"),
)
```

`plot_orbit()` returns the paths it wrote. The supported planets are Mercury
through Neptune, using JPL Horizons heliocentric vectors.
