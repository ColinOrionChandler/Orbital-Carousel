Release procedure
=================

Migration status
----------------

The migration configures publishing; it does not publish the first PyPI release.
The intended first migrated release is **v0.2.0**, which raises the minimum Python
version to 3.11 and introduces BSD-3-Clause licensing, Git-derived versioning,
development tooling, CI, and documentation. Existing CLI names and scientific
behavior are preserved.

The historical ``v0.1.0`` tag anchors version calculation. Do not create a GitHub
release for it. Development versions are derived by setuptools-scm; CI and release
builds must fetch the complete Git history and tags.

Prerequisites
-------------

Connect Read the Docs and Codecov, and register the PyPI and TestPyPI pending
trusted publishers described in ``SERVICE_SETUP.md``. The GitHub environments are
``pypi`` and ``testpypi``. A pending publisher does not reserve the package name.
Account registration and two-factor authentication must be completed by the owner.

Rehearsal
---------

After the migration has merged and service registration is verified:

1. Confirm all tests, documentation, style, and package jobs pass on main.
2. Run ``Publish to TestPyPI`` manually against main. The workflow builds and
   validates the wheel and sdist before uploading them using OpenID Connect.
3. Install that exact development version from TestPyPI into a new environment.
   Install its runtime dependencies from normal PyPI first, then use
   ``--index-url https://test.pypi.org/simple/ --no-deps`` for Orbital Carousel.
4. Check both CLI help commands and the Python API. Confirm installed metadata
   and ``orbital_carousel.__version__`` agree. Never reuse a published version.

First public release
--------------------

After explicit approval to publish:

1. Choose a tested commit on main and create and push the annotated ``v0.2.0`` tag.
2. Publish its GitHub release with the Python compatibility and licensing changes
   described in the release notes.
3. The release workflow checks that the tag is a stable version at least 0.2.0 and
   belongs to main, builds validated distributions, and publishes those artifacts
   to PyPI with the environment-bound trusted publisher.
4. Verify the PyPI page and install ``orbital-carousel==0.2.0`` in a fresh
   environment. Test both commands and confirm version metadata. Enable the
   corresponding Read the Docs stable version and verify its rendered pages.

Do not describe a queued workflow, configured publisher, or successful local build
as a successful publication. If an upload fails, inspect the index and workflow
before retrying: uploaded distribution files cannot simply be replaced.
