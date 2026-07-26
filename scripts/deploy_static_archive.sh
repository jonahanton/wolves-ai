#!/usr/bin/env bash
set -euo pipefail

readonly ARCHIVE_BUCKET="wolves-superforecaster-prod"
readonly DEFAULT_ARCHIVE_RELEASE="5e751c619a9ce8b18774c3691b0cd025eb9824535c07ef371b3628d61d44a650"
readonly PAGES_PROJECT="wolves-world-cup"
readonly WRANGLER_VERSION="4.114.0"

repo_root=$(git rev-parse --show-toplevel)
archive_release=${ARCHIVE_RELEASE:-$DEFAULT_ARCHIVE_RELEASE}

[[ $(git -C "$repo_root" branch --show-current) == "main" ]] || {
  echo "Production deploys require the main branch." >&2
  exit 2
}
[[ -z $(git -C "$repo_root" status --porcelain) ]] || {
  echo "Production deploys require a clean worktree." >&2
  exit 2
}
git -C "$repo_root" fetch --quiet origin main
[[ $(git -C "$repo_root" rev-parse HEAD) == $(git -C "$repo_root" rev-parse origin/main) ]] || {
  echo "Production deploys require main to match origin/main." >&2
  exit 2
}
[[ $archive_release =~ ^[0-9a-f]{64}$ ]] || {
  echo "ARCHIVE_RELEASE must be a SHA-256 digest." >&2
  exit 2
}

archive_dir=$(mktemp -d "${TMPDIR:-/tmp}/wolves-static-archive.XXXXXX")
trap 'rm -rf -- "$archive_dir"' EXIT

aws s3 sync \
  "s3://${ARCHIVE_BUCKET}/static-archive/releases/${archive_release}/" \
  "$archive_dir/" \
  --region eu-west-2 \
  --only-show-errors

uv run --project "$repo_root/engine" \
  python "$repo_root/scripts/verify_static_archive.py" "$archive_dir" "$archive_release"

npm --prefix "$repo_root/web" ci
STATIC_ARCHIVE_DIR="$archive_dir" npm --prefix "$repo_root/web" run build

test ! -e "$repo_root/web/out/archive/provenance.json"
test ! -d "$repo_root/web/out/archive/sources"

npx --yes "wrangler@${WRANGLER_VERSION}" whoami >/dev/null
npx --yes "wrangler@${WRANGLER_VERSION}" pages deploy "$repo_root/web/out" \
  --project-name "$PAGES_PROJECT" \
  --branch main \
  --commit-hash "$(git -C "$repo_root" rev-parse HEAD)" \
  --commit-message "$(git -C "$repo_root" log -1 --pretty=%s)" \
  --commit-dirty=false
