#!/bin/sh
# Docker copy-up can seed the volume from a host venv; rebuild it when broken.
.venv/bin/python3 -c '' 2>/dev/null || uv venv --clear
uv pip install -e ".[dev]"

exec "$@"
