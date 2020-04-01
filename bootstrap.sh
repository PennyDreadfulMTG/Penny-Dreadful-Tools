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
pip install -U --user -r requirements.txt --no-cache
python3 run.py $APP
