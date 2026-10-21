"""Install each built distribution outside the checkout and verify its public interfaces."""

import argparse
import os
import subprocess
import tempfile
import venv
from pathlib import Path


def main():
    """Validate wheels and source distributions using separate, clean environments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    artifacts = sorted(args.directory.resolve().glob("*.whl")) + sorted(
        args.directory.resolve().glob("*.tar.gz")
    )
    if not any(p.suffix == ".whl" for p in artifacts) or not any(
        p.name.endswith(".tar.gz") for p in artifacts
    ):
        parser.error("Expected both a wheel and a source distribution")
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    env.pop("PYTHONHOME", None)
    versions = set()
    for artifact in artifacts:
        with tempfile.TemporaryDirectory(prefix="orbital-package-") as directory:
            root = Path(directory)
            venv.EnvBuilder(with_pip=True).create(root / "venv")
            binary = root / "venv" / ("Scripts" if os.name == "nt" else "bin")
            python = binary / ("python.exe" if os.name == "nt" else "python")
            subprocess.run(
                [str(python), "-m", "pip", "install", "--disable-pip-version-check", str(artifact)],
                cwd=root,
                env=env,
                check=True,
            )
            check = """
from importlib import metadata, util
from pathlib import Path
import sys
import orbital_carousel as package
distribution = metadata.distribution('orbital-carousel')
assert Path(package.__file__).resolve().is_relative_to(Path(sys.prefix).resolve())
assert package.__version__ == distribution.version
assert distribution.metadata['Requires-Python'] == '>=3.11'
assert distribution.metadata['License-Expression'] == 'BSD-3-Clause'
assert {'test', 'dev', 'integrator'} <= set(distribution.metadata.get_all('Provides-Extra'))
assert callable(package.plot_orbit)
assert callable(package.resolve_epochs)
assert package.DEFAULT_EPHEMERIS == 'horizons'
assert util.find_spec('assist') is None and util.find_spec('rebound') is None
scripts = {entry.name: entry.value for entry in distribution.entry_points if entry.group == 'console_scripts'}
assert scripts['orbital-carousel'] == scripts['corotating-carousel'] == 'orbital_carousel.cli:main'
print(distribution.version)
"""
            result = subprocess.run(
                [str(python), "-I", "-c", check],
                cwd=root,
                env=env,
                check=True,
                capture_output=True,
                text=True,
            )
            versions.add(result.stdout.strip())
            for command in ("orbital-carousel", "corotating-carousel"):
                result = subprocess.run(
                    [str(binary / command), "--help"],
                    cwd=root,
                    env=env,
                    check=True,
                    capture_output=True,
                    text=True,
                )
                assert f"usage: {command}" in result.stdout
                assert "--ephemeris" in result.stdout
            subprocess.run(
                [str(python), "-I", "-m", "orbital_carousel.cli", "--help"],
                cwd=root,
                env=env,
                check=True,
                capture_output=True,
            )
            print(f"Validated {artifact.name}", flush=True)
    assert len(versions) == 1, f"Distributions disagree on version: {versions}"


if __name__ == "__main__":
    main()
