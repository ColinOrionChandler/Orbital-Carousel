# LINCC migration validation

Validated on 2026-10-21 against the pre-migration source `599ed64` and migration
implementation `0ad6821`. The template is pinned to v2.3.0; the update notification
reports v2.3.1, which is deliberately outside this migration's approved scope.

## Compatibility and scientific behavior

- All 47 pre-existing tests and two new packaging tests pass (49 total).
- Clean Python 3.11 minimum-direct-dependency installation passes all 49 tests.
- GitHub tests pass on Linux Python 3.11, 3.12, 3.13, and 3.14; macOS Python 3.12;
  minimum direct dependencies; and optional ASSIST/REBOUND installation on 3.12.
- Base distributions import without ASSIST or REBOUND installed. Both CLI aliases,
  module help, and fresh-source-file help remain functional.
- Synthetic heliocentric, Jupiter-frame, and Saturn-frame plots were generated
  before and after migration using the same runtime and fixed vectors/epochs.
  All three PNG pixel arrays and all three rasterized PDFs matched exactly.
  Representative PNG/PDF output was visually inspected.
- The seven pre-existing local plot/kernel files matched their preservation
  manifest after migration (size and modification time, plus SHA-256 for files
  smaller than 100 MB). Their contents were not included in this migration.
- Local coverage was 85%. Older local/minimum Matplotlib dependencies emit
  Pyparsing deprecation warnings; the test runs pass.

## Packaging and tooling

- Wheel and source distribution metadata pass strict Twine checks.
- Each artifact was installed into a separate clean virtual environment outside
  the checkout. Public imports, metadata, optional-extra declarations, version
  agreement, and both installed commands passed validation.
- A Git archive rebuilt without a `.git` directory retains version `0.1.1.dev3`.
- In a disposable clone only, a temporary `v0.2.0` tag yields `0.2.0`, and an
  additional commit yields `0.2.1.dev1`. That tag was never pushed or added to the
  working repository.
- All local pre-commit hooks pass, including unit tests. Sphinx builds with
  warnings treated as errors; the rendered documentation and navigation were
  inspected.
- A same-version Copier update through `.update_template.sh` leaves a disposable
  clone clean. The wrapper excludes template notebook placeholders even when the
  upstream template recreates them with notebooks disabled.

## Hosted checks and remaining account setup

The implementation passed all ten active PR jobs:
[tests](https://github.com/ColinOrionChandler/Orbital-Carousel/actions/runs/39637961006),
[distributions](https://github.com/ColinOrionChandler/Orbital-Carousel/actions/runs/39637959934),
[documentation](https://github.com/ColinOrionChandler/Orbital-Carousel/actions/runs/39637959983),
and [style/configuration](https://github.com/ColinOrionChandler/Orbital-Carousel/actions/runs/39637960019).

GitHub's `pypi` and `testpypi` environments are configured with version-tag and main
branch restrictions, respectively. Read the Docs/Codecov activation and PyPI/
TestPyPI trusted-publisher registration remain pending owner account access; see
[SERVICE_SETUP.md](SERVICE_SETUP.md). Codecov is deliberately skipped until
activation. No package release or TestPyPI upload has been performed.
