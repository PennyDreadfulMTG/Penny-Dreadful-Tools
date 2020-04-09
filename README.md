
# Penny Dreadful Tools
Repository for the tools used by the Penny Dreadful Community.

View individual subdirectories for details

[![Build Status](https://travis-ci.org/PennyDreadfulMTG/Penny-Dreadful-Tools.svg?branch=master)](https://travis-ci.org/PennyDreadfulMTG/Penny-Dreadful-Tools)
[![Codacy Badge](https://api.codacy.com/project/badge/Grade/b4e068a91bd048e9a8e803e8bde29c9d)](https://www.codacy.com/app/clockwork-singularity/Penny-Dreadful-Tools?utm_source=github.com&amp;utm_medium=referral&amp;utm_content=PennyDreadfulMTG/Penny-Dreadful-Tools&amp;utm_campaign=Badge_Grade)
[![Uptime Robot status](https://img.shields.io/uptimerobot/status/m778417564-ebc98d54a784806de06fee4d.svg)](https://status.pennydreadfulmagic.com)

# Modules:

**analysis** is for Magic Online game log analysis.

**decksite** is the code for [pennydreadfulmagic.com](https://pennydreadfulmagic.com/).

**discordbot** is the Discord chatbot.

**github_tools** are some GitHub integration utillities.

**magic** knows everything about all magic cards and how to fetch that information from the internet and model it.

**logsite** is the code for [logs.pennydreadfulmagic.com](https://logs.pennydreadfulmagic.com/).

**logsite_migrations** are alembic database migrations for logsite.

**magic** is for information about Magic: the Gathering such as cards, decklists, card images, legality, etc.

**maintenance** is for useful scripts, usually run via cron.

**modo_bugs** is for integration with https://github.com/PennyDreadfulMTG/modo-bugs/issues.

**price_grabber** builds a database of card prices.

**pylint_monolith** is for our custom extensions to pylint.

**rotation_script** is for the script that handles Penny Dreadful rotation (card legality changes each season).

**shared** contains a bunch of general purpose helper classes. Things that could be used in any project.

**shared_web** contains a bunch of web-specific helper classes.

# Contributing

Contributions are very welcome. Please join the Discord at https://pennydreadfulmagic.com/discord/ and feel free to ask questions in #code.

## Development Environment Setup

- Install MariaDB 10.0+ (alternative MySQL 8.0+)
- Install python3.6+
- Install pip3
- pip3 install -r requirements.txt # If your default python is python2 try `python3 -m pip install -r requirements.txt` instead.
- Install npm
- npm install
- python3 dev.py buildjs
- Add a bot at https://discordapp.com/developers/applications/me
- Add a bot user for the bot
- Add the bot to your server with https://discordapp.com/oauth2/authorize?client_id=<your client id here>&scope=bot
- Click to reveal the token (not secret) on https://discordapp.com/developers/applications/me
- git clone https://github.com/PennyDreadfulMTG/Penny-Dreadful-Tools.git
- Copy config.json.example to config.json and alter the value for "token" to this value
- Optionally take a look at configuration.py and enter any required non-default information into config.json.
- Using the values from your config.json issue the following commands in MySQL (you don't need to create the databases):
    - CREATE USER '<mysql_user>'@'<mysql_host>' IDENTIFIED BY '<mysql_password>';
    - GRANT ALL ON <decksite_database>.* TO '<mysql_user>'@'<mysql_host>';
    - GRANT ALL ON <prices_database>.* TO '<mysql_user>'@'<mysql_host>';
    - GRANT ALL ON <magic_database>.* TO '<mysql_user>'@'<mysql_host>';
    - GRANT ALL ON <logsite_database>.* TO '<mysql_user>'@'<mysql_host>';
- Download a copy of the production decksite database (with personal information stripped):
    - mysql -u <mysql_user> -p<mysql_password> -e "CREATE DATABASE <decksite_database>"
    - curl https://pennydreadfulmagic.com/static/dev-db.sql.gz >/tmp/dev-db.sql.gz
    - gunzip /tmp/dev-db.sql.gz
    - mysql -u <mysql_user> -p<mysql_password> <decksite_database> </tmp/dev-db.sql
- Some very minor parts of the bot (the "modofail" command) use libopus and ffmpeg which are not in pip and must be installed in a your-OS-specific way separately. Very optional.
- You will want to investigate the various targets in dev.py that acts as a Makefile.

### Windows

Python 3.8 pynacl win32 artifacts

For Windows, download the archive from here: https://silasary.visualstudio.com/7b0dd580-087f-44ae-98e1-c7a876a4dafd/_apis/build/builds/2/artifacts?artifactName=pynacl-windows-x86_64-python38&api-version=5.2-preview.5&%24format=zip

Extract it, then e.g. `py -m pip install C:\Users\...\Downloads\pynacl-windows-x86_64-python38\PyNaCl-1.3.0-cp38-cp38-win_amd64.whl`.

## Running Decksite

- cd <github checkout directory>
- python3 run.py decksite
- Visit http://localhost:5000/

## Running Logsite

- cd <github checkout directory>
- python3 run.py logsite
- Visit http://localhost:5001/

## Running Discordbot

- cd <github checkout directory>
- python3 run.py discordbot
- Visit your Discord server.
