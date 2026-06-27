#!/usr/bin/env bash
# Build the wheel/sdist and verify the package is sound before a release.
set -euo pipefail

cd "$(dirname "$0")/.."

rm -rf dist/ build/ ./*.egg-info

echo "==> Building sdist and wheel"
python -m build

echo "==> Checking long description and metadata with twine"
twine check dist/*

echo "==> Checking wheel contents"
check-wheel-contents dist/*.whl

echo "==> Installing the built wheel in --dry-run mode"
python -m pip install --dry-run dist/*.whl

echo "==> All build checks passed"
