#!/usr/bin/env bash
set -euo pipefail

ENV="${1:?usage: release.sh <env>}"
BRANCH="$(git rev-parse --abbrev-ref HEAD)"
TAG="${ENV}-${BRANCH//\//-}-$(whoami)-$(date +%d-%m-%y--%H%M%S)"

echo "Branch: ${BRANCH}"
echo "Tag:    ${TAG}"

if [[ "${ENV}" == "prod" ]]; then
  read -r -p "Deploy ${BRANCH} to prod? Enter y to continue: " answer
  [[ "${answer}" == "y" ]] || exit 0
fi

git tag "${TAG}"
git push origin "${TAG}"
echo "Pushed ${TAG}; the release workflow takes it from here."
