# Penny Dreadful Tools

Repository for the tools used by the Penny Dreadful Community.

View individual subdirectories for details

[![Build Status](https://travis-ci.org/PennyDreadfulMTG/Penny-Dreadful-Tools.svg?branch=master)](https://travis-ci.org/PennyDreadfulMTG/Penny-Dreadful-Tools)
[![Uptime Robot status](https://img.shields.io/uptimerobot/status/m778417564-ebc98d54a784806de06fee4d.svg)](https://status.pennydreadfulmagic.com)

# Modules

**analysis** is for Magic Online game log analysis.

**decksite** is the code for [pennydreadfulmagic.com](https://pennydreadfulmagic.com/).

**discordbot** is the Discord chatbot.

**github_tools** are some GitHub integration utillities.

**logsite** is the code for [logs.pennydreadfulmagic.com](https://logs.pennydreadfulmagic.com/).

**logsite_migrations** are alembic database migrations for logsite.

**magic** is for information about Magic – cards, decklists, card images, legality, etc.

**maintenance** is for useful scripts, usually run via cron.

**modo_bugs** is for integration with <https://github.com/PennyDreadfulMTG/modo-bugs/issues>.

**price_grabber** builds a database of card prices.

**rotation_script** is for the script that handles Penny Dreadful rotation (card legality changes each season).

**shared** contains a bunch of general purpose helper classes. Things that could be used in any project.

**shared_web** contains a bunch of web-specific helper classes. It also contains our React code for "live" data tables.

# Contributing

Contributions are very welcome. Please join the Discord at <https://pennydreadfulmagic.com/discord/> and feel free to ask questions in #code.

## Development Environment Setup

- Install Docker (https://www.docker.com/get-started)
- git clone <https://github.com/PennyDreadfulMTG/Penny-Dreadful-Tools.git>
- docker-compose build
- docker-compose up

If you plan on running things outside of the containers (eg: dev.py or logsite):
- Install python 3.10
- Install pipenv
- Install npm
- git clone <https://github.com/PennyDreadfulMTG/Penny-Dreadful-Tools.git>
- cd Penny-Dreadful-Tools
- pipenv install
- pipenv run python dev.py build

## Configuring Environment

- Add a bot at <https://discordapp.com/developers/applications/me>
- Add a bot user for the bot
- Add the bot to your server with `https://discordapp.com/oauth2/authorize?client_id=<your client id here>&scope=bot`
- Go to the Bot section.
- Click to reveal the token (not secret) on <https://discordapp.com/developers/applications/me>
- Copy `.env.example` to `.env` and alter the value for "token" to this value. (or to "token" in config.json if not in docker setup)
- Do the same for the discord client_id and client_secret
- Optionally take a look at shared/configuration.py and enter any required non-default information into `.env`
- You will want to investigate the various targets in dev.py that acts as a Makefile. Some of these utilities use GitHub's commandline git-enchancer, hub: <https://github.com/github/hub>

## Manual Development Environment Setup (Non-docker instructions)

- Install MariaDB 10.0+
- Install python 3.10
- Install pipenv
- Install npm
- git clone <https://github.com/PennyDreadfulMTG/Penny-Dreadful-Tools.git>
- cd Penny-Dreadful-Tools
- pipenv install
- pipenv run python build.py
- Using the values from your `.env` issue the following commands in MySQL (you don't need to create the databases):
  - CREATE USER '<mysql_user>'@'<mysql_host>' IDENTIFIED BY '<mysql_passwd>';
  - GRANT ALL ON <decksite_database>.* TO '<mysql_user>'@'<mysql_host>';
    GRANT ALL ON <decksite_test_database>.* TO '<mysql_user>'@'<mysql_host>';
  - GRANT ALL ON <prices_database>.* TO '<mysql_user>'@'<mysql_host>';
  - GRANT ALL ON <magic_database>.* TO '<mysql_user>'@'<mysql_host>';
  - GRANT ALL ON <logsite_database>.* TO '<mysql_user>'@'<mysql_host>';
- Download a copy of the production decksite database (with personal information stripped):
  - mysql -u <mysql_user> -p<mysql_passwd> -e "CREATE DATABASE <decksite_database>"
  - curl <https://pennydreadfulmagic.com/static/dev-db.sql.gz> >/tmp/dev-db.sql.gz
  - gunzip /tmp/dev-db.sql.gz
  - mysql -u <mysql_user> -p<mysql_passwd> <decksite_database> </tmp/dev-db.sql
  - mysql -u <mysql_user> -p<mysql_passwd> -e "CREATE DATABASE <decksite_test_database>"
- Some very minor parts of the bot (the "modofail" command) use libopus and ffmpeg which are not in pip and must be installed in a your-OS-specific way separately. Very optional.

## Running Decksite (pennydreadfulmagic.com)

- pipenv run python run.py decksite
- Visit <http://localhost:5000/>

## Running Logsite (logs.pennydreadfulmagic.com)

- pipenv run python run.py logsite
- Visit <http://localhost:5001/>

## Running Discordbot

- pipenv run python run.py discordbot
- Visit your Discord server.

## Running the tests

There are various levels of granularity but in general use you want:

- pipenv run python dev.py test # Runs the unit tests, type checking, lint.

Check the dev.py source code for the full set of options including `unit`, `types`, `lint` (covered by `test` above) as well as `functional` (integration tests), `perf` (performance tests). `release` will take you all the way from your committed change to a PR via the tests (needs GitHub's commandline `gh`/`hub` installed).

## Working on React components

- Run logsite
- pipenv run python dev.py watch # Builds bundle.js after every file change.
