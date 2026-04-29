#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${REPO_ROOT}"

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "error: not inside a git repository" >&2
  exit 1
fi

if ! git diff --cached --quiet --exit-code; then
  echo "error: staged changes exist; clear the index before running this script" >&2
  exit 1
fi

TMP_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/ios-web-blocker-filter.XXXXXX")"
trap 'rm -rf "${TMP_ROOT}"' EXIT

ADGUARD_DIR="${TMP_ROOT}/adguard-japanese"
EASYLIST_DIR="${TMP_ROOT}/easylist"
UBO_DIR="${TMP_ROOT}/ublock-origin"
UBO_FLAT_DIR="${TMP_ROOT}/ublock-origin-flat"

echo "Updating AdGuard Japanese dist outputs..."
python3 scripts/fetch_adguard_japanese_filter.py --output-dir "${ADGUARD_DIR}"
python3 scripts/parse_adguard_japanese_filter.py --input-dir "${ADGUARD_DIR}"

echo "Updating EasyList / EasyPrivacy dist outputs..."
python3 scripts/fetch_easylist_filters.py --output-dir "${EASYLIST_DIR}"
python3 scripts/parse_easylist_filters.py --input-dir "${EASYLIST_DIR}"

echo "Updating uBlock Origin dist outputs..."
python3 scripts/fetch_ublock_origin_filters.py --output-dir "${UBO_DIR}"
python3 scripts/flatten_ublock_origin_filters.py \
  --input-dir "${UBO_DIR}" \
  --output-dir "${UBO_FLAT_DIR}"
python3 scripts/parse_ublock_origin_filters.py --input-dir "${UBO_FLAT_DIR}"

if [[ -z "$(git status --porcelain -- dist)" ]]; then
  echo "No changes detected under dist/; nothing to commit."
  exit 0
fi

git add dist

if git diff --cached --quiet --exit-code; then
  echo "No staged changes under dist/ after git add; nothing to commit."
  exit 0
fi

COMMIT_MESSAGE="${1:-Update dist outputs}"

git commit -m "${COMMIT_MESSAGE}"
git push

echo "Done: updated, committed, and pushed dist/ only."
