#!/usr/bin/env bash
set -euo pipefail

ALLOCATIONS_FILE="$HOME/.worktree/port-allocations.json"
LOCK_DIR="$HOME/.worktree/port-allocations.lock"
WORKSPACE_PATH="${WORKTREE_PATH:-$(pwd)}"

if [ -f .env.worktree ]; then
  set -a; source .env; source .env.worktree; set +a
  docker compose down --volumes --rmi local
fi

rm -f .env.worktree

if [ -f "$ALLOCATIONS_FILE" ]; then
  while ! mkdir "$LOCK_DIR" 2>/dev/null; do sleep 0.1; done
  trap 'rm -rf "$LOCK_DIR"' EXIT

  jq --arg path "$WORKSPACE_PATH" 'del(.[$path])' "$ALLOCATIONS_FILE" \
    > "${ALLOCATIONS_FILE}.tmp"
  mv "${ALLOCATIONS_FILE}.tmp" "$ALLOCATIONS_FILE"
fi
