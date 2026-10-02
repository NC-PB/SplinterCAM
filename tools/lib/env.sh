# SPDX-License-Identifier: Apache-2.0
# Sourced by the tools/ entry points: go to the repository root and check that tools/bootstrap ran.
# Expects $tool (the command name) to be set; exits 2 (missing tool) with a one-line summary.
cd "$(dirname "${BASH_SOURCE[0]}")/../.." || exit 2
if ! command -v uv >/dev/null 2>&1; then
  echo "$tool: ERROR (uv not found; see README.md, Prerequisites, then run tools/bootstrap)"
  exit 2
fi
if [ ! -d .venv ]; then
  echo "$tool: ERROR (no .venv; run tools/bootstrap first)"
  exit 2
fi
