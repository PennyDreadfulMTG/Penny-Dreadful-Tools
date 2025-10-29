#!/bin/bash
export SKIP_PERF_CHECKS=1
export PIPENV_VENV_IN_PROJECT="enabled"
APP="$@"
if [ $# -lt "1" ]
then
    APP="discordbot"
fi
# if pipenv in not in the path, add ~/.local/bin/ to the path
if ! command -v pipenv &> /dev/null
then
    export PATH="$HOME/.local/bin/:$PATH"
fi
echo $APP
cd $(dirname $0)
git pull
pipenv sync
pipenv run $APP
