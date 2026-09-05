#!/usr/bin/env bash
# Restricted SSH entry point: restart this workspace's preview after VM resume.
set -euo pipefail
cd "$(dirname "$0")/.."
export CONDUCTOR_IS_LOCAL=0
export PATH="$HOME/.local/bin:$PATH"
mkdir -p .context
# Keep a separate flock process alive even when the application execs/reloads.
if [[ "${1:-}" != --locked ]]; then
    exec flock .context/preview-ssh.lock bash .conductor/preview-ssh.sh --locked
fi
python3 .conductor/cloud.py start
# A run-panel server may already be serving this workspace. Reuse it until it
# exits; the Mac supervisor then reconnects and starts a replacement.
if python3 -c 'import socket; socket.create_connection(("127.0.0.1", 5000), timeout=1).close()' 2>/dev/null; then
    while python3 -c 'import socket; socket.create_connection(("127.0.0.1", 5000), timeout=1).close()' 2>/dev/null; do
        sleep 5
    done
else
    exec bash .conductor/decksite-cloud.sh
fi
