#!/usr/bin/env bash
set -euo pipefail

MAIN_ROOT=$(realpath "$(dirname "$(git rev-parse --git-common-dir)")")
if [ "$MAIN_ROOT" != "$(pwd)" ]; then
  cp "$MAIN_ROOT/.env" .env 2>/dev/null || echo "Warning: no .env found in main repo root, skipping"
fi

.worktree/allocate-ports.sh

git config --unset-all core.hooksPath 2>/dev/null || true
make venv
make frontend/install
