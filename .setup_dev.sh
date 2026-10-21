#!/usr/bin/env bash
set -euo pipefail

if [[ -z "${VIRTUAL_ENV:-}" && -z "${CONDA_PREFIX:-}" ]]; then
    echo "Activate a Python 3.11+ virtual environment before running this script." >&2
    exit 1
fi
python -m pip install -e '.[dev]' -r docs/requirements.txt
python -m pre_commit install
