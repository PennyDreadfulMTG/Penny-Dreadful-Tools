#!/bin/bash
set -euo pipefail

export SKIP_PERF_CHECKS=1
if [ "$#" -lt 1 ]
then
    APP=("discordbot")
else
    APP=("$@")
fi
# if uv in not in the path, add ~/.local/bin/ to the path
if ! command -v uv &> /dev/null
then
    export PATH="$HOME/.local/bin/:$PATH"
fi
echo "${APP[*]}"
cd "$(dirname "$0")"
git pull --ff-only
uv sync --frozen
uv run --frozen run.py "${APP[@]}"
