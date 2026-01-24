#!/bin/bash
export SKIP_PERF_CHECKS=1
APP="$@"
if [ $# -lt "1" ]
then
    APP="discordbot"
fi
# if uv in not in the path, add ~/.local/bin/ to the path
if ! command -v uv &> /dev/null
then
    export PATH="$HOME/.local/bin/:$PATH"
fi
echo $APP
cd $(dirname $0)
git pull
uv sync
uv run run.py $APP
