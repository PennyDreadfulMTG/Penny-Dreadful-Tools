#!/usr/bin/env bash
set -euo pipefail
if [[ "${CONDUCTOR_IS_LOCAL:-0}" == 1 ]]; then exit 0; fi
cd "$(dirname "$0")/.."
export PATH="$HOME/.local/bin:$PATH"
if ! command -v uv >/dev/null; then
    curl -LsSf https://astral.sh/uv/install.sh | sh
fi
# Preinstall these in the cloud image to keep startup within 1–2 minutes.
if ! command -v mariadbd >/dev/null || ! command -v pkg-config >/dev/null || ! command -v zstd >/dev/null; then
    sudo dnf install -y mariadb118-server mariadb118-devel pkgconf-pkg-config gcc python3-devel zstd
fi
uv sync --frozen
python3 .conductor/cloud.py setup
npm ci --no-audit --no-fund
npm run build
