# Publishing service setup

Repository: `ColinOrionChandler/Orbital-Carousel` (public).
Package: `orbital-carousel`. First public release is deferred.

## Read the Docs

Import the existing repository into the owner's Read the Docs Community account,
using project slug `orbital-carousel` and default branch `main`. The repository's
`.readthedocs.yml` builds Sphinx on Python 3.12 with warnings treated as errors.
Enable pull-request previews and verify the first successful build and rendered
user guide/API pages before adding a documentation badge or claiming activation.

## Codecov

Activate `ColinOrionChandler/Orbital-Carousel` in Codecov. The coverage job uses the
official action's OIDC authentication, with `id-token: write` limited to the upload
job. Set the GitHub Actions repository variable `CODECOV_ENABLED=true` only once the
repository is activated. Until then, CI retains `coverage.xml` as an artifact and
skips the external upload. Verify that Codecov shows coverage for the tested commit.
No minimum coverage threshold is imposed during this migration.

## PyPI and TestPyPI

Register pending GitHub trusted publishers in each index's owner account:

| Field | PyPI | TestPyPI |
| --- | --- | --- |
| Project | `orbital-carousel` | `orbital-carousel` |
| Owner | `ColinOrionChandler` | `ColinOrionChandler` |
| Repository | `Orbital-Carousel` | `Orbital-Carousel` |
| Workflow | `publish-to-pypi.yml` | `publish-to-testpypi.yml` |
| Environment | `pypi` | `testpypi` |

The production workflow runs only on published GitHub releases; the rehearsal
workflow is manually dispatched. Both consume distributions that passed package
validation. Use OpenID Connect rather than long-lived PyPI API tokens. Pending
publishers do not reserve a name or create a public project until the first upload.

See [release instructions](docs/releases.rst). Do not publish a production release
as part of setup.

## Verification status

Checked 2026-10-21:

- GitHub environments were created and verified: `pypi` permits `v*` tags;
  `testpypi` permits the `main` branch.
- Read the Docs setup reached its GitHub sign-in page. Owner sign-in is needed
  before the repository can be imported and a hosted build verified.
- PyPI setup reached its account sign-in page. Pending publisher registration
  remains unverified on both indexes; no distribution has been uploaded.
- Codecov repository activation remains unverified. `CODECOV_ENABLED` is unset,
  so coverage artifacts remain available without implying an external upload.

Complete the account-side steps above after signing in. Configuration files and
GitHub environments alone are not evidence of external-service activation.
