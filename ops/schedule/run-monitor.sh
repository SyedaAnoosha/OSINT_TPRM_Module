#!/usr/bin/env bash
# The one command every scheduler in this directory invokes.
#
# Environment setup lives here rather than in each timer, so a venv path or an .env location changes
# in one file instead of three. Exits non-zero when the sweep fails or when any vendor failed to
# re-score, which is what makes the host's existing alerting the notification path.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BACKEND="${REPO_ROOT}/backend"

cd "${BACKEND}"

# .env is gitignored and holds DATABASE_URL plus collector credentials. Sourced rather than
# committed to any timer file, because crontabs are world-readable on most hosts.
if [[ -f "${BACKEND}/.env" ]]; then
    set -a
    # shellcheck disable=SC1091
    source "${BACKEND}/.env"
    set +a
fi

PYTHON="${BACKEND}/.venv/bin/python"
[[ -x "${PYTHON}" ]] || PYTHON="${BACKEND}/.venv/Scripts/python.exe"
[[ -x "${PYTHON}" ]] || PYTHON="$(command -v python3 || command -v python)"

exec "${PYTHON}" -m app.scheduler --run "$@"
