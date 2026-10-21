Development
===========

Create a Python 3.11+ virtual environment and install the development dependencies:

.. code-block:: bash

   python -m venv .venv
   source .venv/bin/activate
   bash .setup_dev.sh

Run the local checks:

.. code-block:: bash

   python -m pytest --cov=orbital_carousel
   pre-commit run --all-files
   sphinx-build -W --keep-going -b html docs docs/_build/html
   python -m build
   python -m twine check --strict dist/*
   python tools/check_distributions.py dist

Tests use synthetic vectors, prohibit HTTP requests, and mock ASSIST. They do not
download ephemerides or require local kernels. CI covers Python 3.11–3.14 on Linux,
Python 3.12 on macOS, minimum direct runtime dependencies, and optional integrator
installation on Python 3.12. Coverage is initially informational.

Template updates
----------------

The repository tracks LINCC Frameworks Python Project Template v2.3.0 through
Copier's answer file. Use Copier 9.1+ on a clean feature branch, pin the reviewed
template tag with ``bash .update_template.sh --vcs-ref <tag>``, inspect changes
and conflicts, then repeat the checks above. The wrapper excludes unused notebook
placeholder directories.
Preserve the public package, both CLI names, optional extras, scientific defaults,
product exclusions, and project-specific CI behavior.

See the full `development guide
<https://github.com/ColinOrionChandler/Orbital-Carousel/blob/main/DEVELOPMENT_GUIDE.md>`_
for the customization inventory and update commands.
