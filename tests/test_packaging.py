"""Exercise version metadata and fresh-checkout compatibility."""

import os
import shutil
import subprocess
import sys
from importlib.metadata import version
from pathlib import Path

import orbital_carousel


def test_generated_version_matches_installed_distribution():
    assert orbital_carousel.__version__ == version("orbital-carousel")


def test_fresh_source_checkout_help_without_generated_version(tmp_path):
    source = Path(__file__).resolve().parents[1] / "src" / "orbital_carousel"
    target = tmp_path / "src" / "orbital_carousel"
    shutil.copytree(source, target, ignore=shutil.ignore_patterns("_version.py", "__pycache__"))
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    result = subprocess.run(
        [sys.executable, str(target / "cli.py"), "--help"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    assert "Plot a minor-body orbit" in result.stdout
