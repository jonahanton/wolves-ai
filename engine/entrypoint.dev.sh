#!/bin/sh
# Anon-volume copy-up can seed /app/.venv from a host venv; rebuild if broken.
cd /app
.venv/bin/python3 -c '' 2>/dev/null || uv venv --clear
uv sync --package wolves --extra dev
cd engine

exec "$@"
