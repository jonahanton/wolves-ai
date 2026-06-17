#!/usr/bin/env bash
# Set or replace a KEY=value line in .env, creating the key if absent.
set -euo pipefail

KEY="$1"
VALUE="$2"
ENV_FILE="$(dirname "$0")/../.env"

if [ ! -f "$ENV_FILE" ]; then
  echo "${KEY}=${VALUE}" > "$ENV_FILE"
  exit 0
fi

if grep -qE "^${KEY}=" "$ENV_FILE"; then
  tmp="$(mktemp)"
  sed "s|^${KEY}=.*|${KEY}=${VALUE}|" "$ENV_FILE" > "$tmp"
  mv "$tmp" "$ENV_FILE"
else
  printf '%s=%s\n' "$KEY" "$VALUE" >> "$ENV_FILE"
fi
