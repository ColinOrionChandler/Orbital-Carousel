#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$0")"

# v2.3.0 emits these placeholder directories even when notebooks are disabled.
copier update --exclude docs/notebooks --exclude docs/pre_executed "$@" .
