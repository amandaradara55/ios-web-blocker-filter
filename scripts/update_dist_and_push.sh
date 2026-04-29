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

PUBLISH_BRANCH="${PUBLISH_BRANCH:-gh-pages}"
COMMIT_MESSAGE="${1:-Publish dist outputs}"
TMP_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/ios-web-blocker-filter-publish.XXXXXX")"
WORKTREE_DIR="${TMP_ROOT}/publish-worktree"

cleanup() {
  if [[ -d "${WORKTREE_DIR}" ]]; then
    git worktree remove --force "${WORKTREE_DIR}" >/dev/null 2>&1 || true
  fi
  rm -rf "${TMP_ROOT}"
}
trap cleanup EXIT

./scripts/update_dist.sh

if git show-ref --verify --quiet "refs/heads/${PUBLISH_BRANCH}"; then
  git worktree add "${WORKTREE_DIR}" "${PUBLISH_BRANCH}" >/dev/null
elif git ls-remote --exit-code --heads origin "${PUBLISH_BRANCH}" >/dev/null 2>&1; then
  git fetch origin "${PUBLISH_BRANCH}:refs/heads/${PUBLISH_BRANCH}" >/dev/null
  git worktree add "${WORKTREE_DIR}" "${PUBLISH_BRANCH}" >/dev/null
else
  git worktree add -b "${PUBLISH_BRANCH}" "${WORKTREE_DIR}" HEAD >/dev/null
fi

find "${WORKTREE_DIR}" -mindepth 1 -maxdepth 1 ! -name .git -exec rm -rf {} +
mkdir -p "${WORKTREE_DIR}/dist"
cp -R "${REPO_ROOT}/dist/." "${WORKTREE_DIR}/dist/"
cat > "${WORKTREE_DIR}/README.md" <<'EOF'
# gh-pages

This branch is generated automatically.

Published filter JSON files are under `dist/`.
EOF
touch "${WORKTREE_DIR}/.nojekyll"

(
  cd "${WORKTREE_DIR}"
  git add -A
  if git diff --cached --quiet --exit-code; then
    echo "No changes detected for ${PUBLISH_BRANCH}; nothing to commit."
    exit 0
  fi
  git commit -m "${COMMIT_MESSAGE}"
  git push -u origin "${PUBLISH_BRANCH}"
)

echo "Done: published dist/ to ${PUBLISH_BRANCH}."
