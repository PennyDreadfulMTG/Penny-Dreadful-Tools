#!/bin/bash
export PIPENV_VENV_IN_PROJECT="enabled"
APP="$@"
if [ $# -lt "1" ]
then
    APP="discordbot"
fi
echo $APP
cd $(dirname $0)
git pull
pipenv sync
pipenv run $APP
