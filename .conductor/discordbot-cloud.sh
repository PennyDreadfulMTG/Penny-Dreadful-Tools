#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

if [[ "${CONDUCTOR_IS_LOCAL:-1}" != 0 ]]; then
    echo 'This runner is only for Conductor cloud workspaces.' >&2
    exit 1
fi

required=(PDT_TEST_DISCORD_TOKEN PDT_GOOGLE_MAPS_API_KEY PDT_TEST_DISCORD_GUILD_ID)
for name in "${required[@]}"; do
    if [[ -z "${!name:-}" ]]; then
        echo "Missing required Conductor cloud environment variable: $name" >&2
        exit 1
    fi
done

echo 'Starting the Discord test bot. Production background tasks are disabled.'
exec uv run --frozen python run.py discordbot
