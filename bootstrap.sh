#!/bin/bash
if [ -d "~/.pyenv/bin" ]
then
echo 'Using pyenv'
export PATH=~/.pyenv/shims:~/.pyenv/bin:"$PATH"
fi
APP="$@"
if [ $# -lt "1" ]
then
    APP="discordbot"
fi
echo $APP
cd $(dirname $0)
git pull
python3 run.py build
python3 run.py $APP
