# Penny Dreadful Tools

Repository for the tools used by the Penny Dreadful Community.

View individual subdirectories for details

For Conductor cloud setup and Mac browser previews, see [Conductor development](.conductor/README.md).

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

### Docker Compose

- Install Docker (https://www.docker.com/get-started)
- Install [Git LFS](https://git-lfs.com/)
- git clone <https://github.com/PennyDreadfulMTG/Penny-Dreadful-Tools.git>
- cd Penny-Dreadful-Tools
- git lfs pull
- cp .env.example .env
- docker compose build
- docker compose up

The first run will download a copy of the prod decksite db and set it up as well as build cards db from scryfall data so it will take a while.

After this, various components will be available in your browser:

- The decksite (PDM) at <http://127.0.0.1:80> (to be able to login see [Configuring Environment](#configuring-environment))
- The admin panel at <http://127.0.0.1:8080>
- The logsite at <http://127.0.0.1:5001>

Once the cards and deck databases are initialized, generate the custom symbols font from another terminal:

```
docker compose exec decksite uv run --frozen python dev.py buildfonts
```

### Non-Docker development

If you plan on running things outside of the containers (eg: dev.py or logsite):

- Install python 3.13
- Install uv
- Install npm
- Install [Git LFS](https://git-lfs.com/)
- git clone <https://github.com/PennyDreadfulMTG/Penny-Dreadful-Tools.git>
- cd Penny-Dreadful-Tools
- git lfs pull
- uv sync --frozen --dev
- uv run --frozen python dev.py build

## Configuring Environment

- Add a new application at <https://discordapp.com/developers/applications/me>
- Go to the OAuth2 section in your application
- Reset the client secret
- In the root folder of the project copy `.env.example` to `.env`
- In `.env` set `oauth2_client_id` and `oauth2_client_secret` to the client id and client secret found in the OAuth2 section
- Still under the OAuth2 section, add a redirect with the following URI `http://127.0.0.1/authenticate/callback/`
- Go to the Bot section of your application
- Reset the token, use it to fill out `token` in `.env`
- Optionally, add the bot to your server with `https://discordapp.com/oauth2/authorize?client_id=<your client id here>&scope=bot`
- Optionally, take a look at shared/configuration.py and enter any required non-default information into `.env`
- You will want to investigate the various targets in dev.py that acts as a Makefile. Some of these utilities use GitHub's official CLI, gh: <https://cli.github.com/>

## Manual Development Environment Setup (Non-docker instructions)

- Install MariaDB 10.0+
- Install python 3.13
- Install uv
- Install npm
- Install [Git LFS](https://git-lfs.com/)
- git clone <https://github.com/PennyDreadfulMTG/Penny-Dreadful-Tools.git>
- cd Penny-Dreadful-Tools
- git lfs pull
- uv sync --frozen --dev
- uv run --frozen python build.py
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
- Initialize the cards database with `uv run --frozen python run.py init-cards`.
- Generate the custom symbols font with `uv run --frozen python dev.py buildfonts`.
- Some very minor parts of the bot (the "modofail" command) use libopus and ffmpeg which are not in pip and must be installed in a your-OS-specific way separately. Very optional.

## Running Decksite (pennydreadfulmagic.com)

- uv run --frozen python run.py decksite
- Visit <http://localhost/> (or the port set by `decksite_port` in `config.json`; the default is port 80).

## Running Logsite (logs.pennydreadfulmagic.com)

- uv run --frozen python run.py logsite
- Visit <http://localhost:5001/>

## Running Discordbot

- uv run --frozen python run.py discordbot
- Visit your Discord server.

## Running the tests

There are various levels of granularity but in general use you want:

- uv run --frozen python dev.py test # Runs the unit tests, type checking, lint.

Check the dev.py source code for the full set of options including `unit`, `types`, `lint` (covered by `test` above) as well as `functional` (integration tests), `perf` (performance tests). `release` will take you all the way from your committed change to a PR via the tests (needs GitHub's commandline `gh` installed).

Two more targets look at what a user would actually see, because a page can return 200 and still be broken:

- `uv run --frozen python dev.py smoke` renders every page that has a "live" React table against a small seeded database (`decksite/conftest.py`), makes exactly the API request the browser's DataManager would make from the page's `data-*` attributes, and checks rows come back. A few seconds. Run it when you touch templates, CSS, JSX, `decksite/controllers/api.py` or `decksite/data/clauses.py`.
- `uv run --frozen python dev.py browser` loads real pages in headless Chromium (`decksite/browser_test.py`): live tables fill, no request fails, no JavaScript throws, and the navigation submenu is genuinely visible and clickable at mobile, medium and wide widths, by mouse and by touch. Needs `uv run --frozen playwright install chromium` once and a built JS bundle. About 30 seconds. `--url https://pennydreadfulmagic.com` runs the same checks read-only against a deployed site; the `Production Canary` GitHub workflow does that after every push to master and every two hours.

CI runs the browser tests as a separate `browser` job, in parallel, so they add no time to the main test job. It is a required check: `.mergify.yml` lists it alongside `mypy`, `lint`, `test` and `jslint`, so a red `browser` job blocks the merge.

### Validating card-import changes

Changes to the Scryfall importer should also be checked with two disposable databases made from exactly the same bulk data:

1. Create a worktree at `origin/master` and place the same `scryfall-default-cards.json` and `sets.json` in both worktree roots. The candidate also accepts Scryfall's compressed `scryfall-default-cards.jsonl.gz` format.
2. Force an import from the master worktree into a database named `pd_alias_shadow_master` and from the candidate into `pd_alias_shadow_candidate`. Shadow database names deliberately use the `pd_alias_shadow_` prefix to keep them separate from development and production data.
3. From the candidate worktree, run `uv run python dev.py compare-card-databases pd_alias_shadow_master pd_alias_shadow_candidate`.

The comparison fails if canonical card data was removed or changed, if an existing alias or legality was removed, or if aliases became ambiguous. It permits and reports newly recognized aliases and legality rows derived from those aliases.

After importing current cards, run `uv run pytest magic/omenpaths_test.py rotation_script/rotation_script_test.py` for the focused acceptance cases. They cover normal and double-faced alternate names, mixed-name aggregation, the shared four-copy limit across main deck and sideboard, canonical deck and legal-list output, legacy name matching, and search indexing. The full `uv run pytest` suite remains the final regression gate.

## Working on React components

- Run logsite
- uv run --frozen python dev.py watch # Builds bundle.js after every file change. Uses development build so that you get source maps - useful line numbers and error messages, unlike build/buildjs.

## Decksite performance testing/monitoring

- You can run decksite in profiling mode with:
    - $ uv run --frozen python3 ~/pd/run.py profiler
- You can be warned about slowness by setting `slow_query`, `slow_page` and `slow_fetch` limits in conifg.json
