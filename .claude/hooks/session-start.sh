#!/bin/bash
set -euo pipefail

# Only run in remote (Claude Code on the web) environments
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

cd "${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel)}"

# Ensure setuptools is new enough for pyproject.toml builds
pip install --quiet --break-system-packages "setuptools>=82" wheel

# Install project dependencies (including dev extras)
pip install --quiet --break-system-packages -e ".[dev]"
