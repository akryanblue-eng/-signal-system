#!/usr/bin/env bash
# One-shot bootstrap: push the V_ref Compliance Suite to GitHub.
# Run from a machine that has 'git' and a GitHub PAT (or SSH access).
#
# Usage:
#   chmod +x bootstrap.sh
#   ./bootstrap.sh
#
# Or with explicit token:
#   GITHUB_TOKEN=ghp_... ./bootstrap.sh

set -euo pipefail

REPO_URL="${GITHUB_TOKEN:+https://${GITHUB_TOKEN}@github.com/akryanblue-eng/v_ref_compliance_suite.git}"
REPO_URL="${REPO_URL:-https://github.com/akryanblue-eng/v_ref_compliance_suite.git}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

cd "$SCRIPT_DIR"

git init
git branch -M main
git remote remove origin 2>/dev/null || true
git remote add origin "$REPO_URL"

git add -A
git commit -m "feat: V_ref Compliance Suite — CER dispatch, Merkle spine, schema lock

16 tests: 9 type-closure assertions + 6 schema-lock golden-vector replays + 1 dispatch exhaustiveness.
Merkle roots committed as golden fixtures; CI verifies, never regenerates.

https://claude.ai/code/session_01MhFqgXjDkA5csxnoChXAQF"

git push -u origin main

echo ""
echo "Push complete. CI will run at:"
echo "  https://github.com/akryanblue-eng/v_ref_compliance_suite/actions"
