#!/bin/sh
# Sync deps from the bind-mounted pyproject.toml into the persistent
# venv volume; near-instant when nothing changed.
uv pip install -e ".[dev]"

exec "$@"
