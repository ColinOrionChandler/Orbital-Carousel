# Development guide

Use Python 3.11 or newer in an isolated environment:

```bash
python -m venv .venv
source .venv/bin/activate
bash .setup_dev.sh
```

`.[test]` retains the lightweight test installation. `.[dev]` adds Ruff,
pre-commit, coverage, build, and Twine. `.[integrator]` is optional and does not
download ephemeris kernels. Documentation requirements live in `docs/requirements.txt`.

## Checks

```bash
python -m pytest --cov=orbital_carousel --cov-report=term-missing
ruff check .
ruff format --check .
pre-commit run --all-files
sphinx-build -W --keep-going -b html docs docs/_build/html
python -m build
python -m twine check --strict dist/*
python tools/check_distributions.py dist
```

Tests block HTTP requests and use synthetic vectors and mocked ASSIST objects.
Normal development checks never require JPL kernels. Set `MPLBACKEND=Agg` for
headless plotting. The distribution check creates separate virtual environments,
installs the wheel and sdist with their dependencies, then exercises public imports
and both CLI names outside the checkout.

CI tests Python 3.11–3.14 on Linux and 3.12 on macOS. Separate jobs exercise
minimum direct runtime dependencies and the optional integrator on Python 3.12.
Coverage is reported without a minimum threshold. Integration outside this matrix
is not implied by the base-package compatibility tests.

## Template maintenance

This is a retrofit of LINCC Frameworks Python Project Template **v2.3.0**, generated
with Copier. `.copier-answers.yml` records the template and selected options.
Use Copier 9.1 or newer. Start from a clean feature branch:

```bash
git switch -c codex/update-lincc-template
bash .update_template.sh --vcs-ref <reviewed-template-tag>
git diff
```

Resolve every conflict and `.rej` file, then run the checks above. For a same-version
compatibility check, use `bash .update_template.sh --defaults --vcs-ref v2.3.0` in a disposable
clone. The wrapper excludes two notebook placeholder directories that v2.3.0
otherwise recreates even with notebooks disabled. The version notification hook may announce a newer release without changing
the pinned template. Update answers through Copier rather than editing them manually.

Project-specific customizations that must survive updates:

- Keep `orbital_carousel`, its public exports, both console scripts, and source-file help.
- Keep runtime requirements and the `test` and `integrator` extras. Exclude Jupyter,
  sample modules, the sample version CLI, notebooks, and benchmarks.
- Keep BSD-3-Clause metadata, the existing mixed-case GitHub repository URL,
  setuptools package discovery, and full-history version derivation in CI.
- Keep existing product/kernel ignore rules. Never delete or move scientific output
  or ephemeris files while cleaning generated build artifacts.
- Keep network-free tests, installed-distribution checks, and warning-fatal docs.
  The template's doctest discovery is intentionally replaced with the existing
  pytest suite; user-guide examples must not query live services during a docs build.
- Keep guarded PyPI/TestPyPI workflows and Codecov's explicit activation flag.
- No template-generated `AGENTS.md`, sample test tree, notebook folders, or
  `.initialize_new_project.sh` is retained. The initialization script runs `git init`
  and commits files; it must never be run against this existing repository.

The Ruff rules come from the template, with test docstrings/naming exempted.
Ruff is pinned consistently in the dev extra and hook configuration. The generated
`_version.py` is excluded from linting and Git. A fresh source checkout reports
`0+unknown` until built, and keeps CLI help available; installed distributions use
the generated version. Development builds omit local hash suffixes so they can
be uploaded to TestPyPI. Untagged source archives fall back to `0.1.dev0`.

## Versions and publishing

`v0.1.0` anchors the pre-migration source at `599ed64`; it is a Git tag, not a
GitHub or PyPI release. `setuptools-scm` derives subsequent development versions.
See [the release procedure](docs/releases.rst) and [service setup](SERVICE_SETUP.md).
