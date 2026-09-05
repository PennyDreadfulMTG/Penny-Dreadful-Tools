#!/usr/bin/env bash
set -euo pipefail
if [[ "${CONDUCTOR_IS_LOCAL:-}" != 0 ]]; then
    echo 'Use the local decksite run script with CONDUCTOR_PORT on macOS.' >&2
    exit 1
fi
cd "$(dirname "$0")/.."
export PATH="$HOME/.local/bin:$PATH"
python3 .conductor/cloud.py start
exec uv run --frozen python -c 'from decksite import main; main.APP.config["SESSION_COOKIE_SECURE"] = False; main.APP.run(host="0.0.0.0", port=5000, debug=False, use_reloader=True)'
