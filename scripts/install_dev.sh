#!/usr/bin/env bash
# One-command onboarding for new contributors.
set -euo pipefail

cd "$(dirname "$0")/.."

pip install -e ".[dev,docs]"
pre-commit install
pre-commit install --hook-type commit-msg

echo "==> Dev environment ready. Try: pytest tests/unit -v"
