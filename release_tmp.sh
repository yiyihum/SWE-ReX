#!/usr/bin/env bash

# Release to anonymous pypi

set -euo pipefail

sed -i '' 's/name = "swerex"/name = "0fdb5604"/g' pyproject.toml
echo "Hi there, hello" > README.md

rm -r dist/**
pip install build
python -m build
pipx run twine upload dist/*
