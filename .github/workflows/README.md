# Workflows

Pull requests and main run tests, configuration/style checks, documentation builds,
and wheel/sdist validation. Daily/manual smoke tests detect dependency drift.

Codecov uploads run only after the repository is activated and CODECOV_ENABLED
is set to true. Coverage artifacts are retained regardless.

PyPI publishing requires a published stable GitHub release at least v0.2.0 on main.
TestPyPI is a separate manual workflow. Both use environment-bound OIDC publishers
and the reusable build/validation workflow. See SERVICE_SETUP.md and docs/releases.rst.
