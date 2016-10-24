#!/bin/bash
cd `dirname $0`
git pull
pip install -U --user -r requirements.txt
python3 run.py
