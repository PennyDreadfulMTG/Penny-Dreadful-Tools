#!/bin/bash
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
