# Orbital Carousel

Plot small-body orbits in heliocentric or planet co-rotating reference frames.
This package provides a command-line interface and a Python API, with Horizons
vectors by default and optional ASSIST/REBOUND integration for long time spans.

## Install

Requires **Python 3.11+**. From this checkout:

```bash
python -m pip install -e .
orbital-carousel "2015 DD349"
```

The compatibility command `corotating-carousel` remains available. By default,
the command writes PNG and PDF plots using 20 target orbits and 120 samples per
orbit, with Jupiter defining the co-rotating frame.

```bash
orbital-carousel "2015 DD349" --frame-body Jupiter,Saturn --format png
orbital-carousel "2000 OG44" --frame heliocentric --planets Venus,Earth,Mars,Jupiter
python -m pip install -e '.[integrator]'  # Optional ASSIST/REBOUND backend
```

ASSIST also requires external JPL kernels; see the [user guide](docs/usage.rst)
for setup, epoch options, output naming, and scientific limitations.

## Python API

```python
from orbital_carousel import plot_orbit

paths = plot_orbit("2025 NN80", frame_body=("Jupiter", "Saturn"), planets="auto")
```

## Documentation and development

- [User guide](docs/usage.rst): installation, CLI, Python API, and ASSIST.
- [Development guide](DEVELOPMENT_GUIDE.md): tests, tooling, and template updates.
- [Release procedure](docs/releases.rst) and [service setup status](SERVICE_SETUP.md).

This repository uses the [LINCC Frameworks Python Project Template](https://github.com/lincc-frameworks/python-project-template)
with Copier-managed updates. It is licensed under [BSD 3-Clause](LICENSE).
