#!/bin/sh
# Sync deps from the bind-mounted workspace into the venv volume; near-instant
# when nothing changed. Anonymous-volume copy-up can seed /app/.venv from a
# host venv whose interpreter does not run in the container; rebuild if broken.
cd /app
.venv/bin/python3 -c '' 2>/dev/null || uv venv --clear
uv sync --package wolves-backend --extra dev
cd backend

exec "$@"
