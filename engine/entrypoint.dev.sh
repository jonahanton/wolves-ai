#!/bin/sh
# Sync deps from the bind-mounted pyproject.toml into the persistent
# venv volume; near-instant when nothing changed. Docker's copy-up can
# seed the volume from a host (macOS) venv whose interpreter cannot run
# here, so rebuild the venv whenever its python is not executable.
.venv/bin/python3 -c '' 2>/dev/null || uv venv --clear
uv pip install -e ".[dev]"

exec "$@"
