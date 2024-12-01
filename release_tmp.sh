#!/usr/bin/env bash

# Release to anonymous pypi

set -euo pipefail

sed -i '' 's/name = "swerex"/name = "0fdb5604"/g' pyproject.toml
echo "" > README.md

rm -r dist/**
python -m build
twine upload dist/*
