#!/usr/bin/env python3
import importlib
import logging
import pkgutil
import sys
import time
from types import ModuleType
from typing import Any, List, Optional, Tuple

import click

from shared import configuration

logging.basicConfig(level=logging.INFO)

def wait_for_db(_: Any, __: Any, value: bool) -> None:
    if not value:
        return
    print('waiting for db')

    def attempt(interval: int = 1) -> bool:
        from shared import database, pd_exception
        try:
            database.get_database(configuration.get_str('magic_database'))
            return True
        except pd_exception.DatabaseConnectionRefusedException:
            print(f'DB not accepting connections.  Sleeping for {interval}.')
            time.sleep(interval)
            return False
    i = 1
    while not attempt(i) and i < 60:
        i = i + 1

@click.group()
@click.option('--wait-for-db', is_flag=True, callback=wait_for_db, expose_value=False, help='Idle until the mySQL server starts accepting connections')
def cli() -> None:
    pass

@cli.command()
def discordbot() -> None:
    from discordbot import bot
    bot.init()

@cli.command()
def decksite() -> None:
    from decksite import main
    main.init()

@cli.command()
def profiler() -> None:
    from werkzeug.middleware.profiler import ProfilerMiddleware

    from decksite import main
    main.APP.config['PROFILE'] = True
    main.APP.wsgi_app = ProfilerMiddleware(main.APP.wsgi_app, restrictions=[30])  # type: ignore
    main.init()

@cli.command()
def price_grabber() -> None:
    from price_grabber import price_grabber as grabber
    grabber.run()

@cli.command()
def srv_price() -> None:
    from price_grabber import srv_prices
    srv_prices.init()

@cli.command()
@click.argument('source')
def scraper(source: str) -> None:
    task(['scraper', source])

@cli.command()
@click.argument('eventname')
def scrape_event(eventname: str) -> None:
    task(['scraper', 'gatherling', eventname])

@cli.command()
@click.argument('script')
def maintenance(script: str) -> None:
    task(['maintenance', script])

@cli.command()
def rotation() -> None:
    from rotation_script import rotation_script
    rotation_script.run()

@cli.command()
def logsite() -> None:
    import logsite as site
    site.APP.run(host='0.0.0.0', port=5001, debug=True)

@cli.command()
def github_tools() -> None:
    import github_tools as site
    site.APP.run(host='0.0.0.0', port=5002, debug=True)

@cli.command()
@click.argument('argv', nargs=-1)
def modo_bugs(argv: Tuple[str]) -> None:
    from modo_bugs import main
    main.run(argv)

def task(args: List[str]) -> None:
    try:
        module = args[0]
        if module == 'scraper':
            module = 'scrapers'
        if module == 'scrapers':
            module = 'decksite.scrapers'
        name = args[1]
        from magic import multiverse, oracle
        multiverse.init()
        if name != 'reprime_cache':
            oracle.init()
        if name == 'all':
            run_all_tasks(module)
        elif name == 'hourly':
            run_all_tasks(module, 'HOURLY')
        else:
            s = importlib.import_module('{module}.{name}'.format(name=name, module=module))
            use_app_context = getattr(s, 'REQUIRES_APP_CONTEXT', True)
            exitcode = None
            if use_app_context:
                from decksite.main import APP
                APP.config['SERVER_NAME'] = configuration.server_name()
                with APP.app_context():
                    exitcode = call(args, s)
            else:
                exitcode = call(args, s)

            if exitcode is not None:
                sys.exit(exitcode)
    except Exception as c:
        from shared import repo
        repo.create_issue(f'Error running task {args}', 'CLI', 'CLI', 'PennyDreadfulMTG/perf-reports', exception=c)
        raise

def call(args: List[str], s: ModuleType) -> int:
    exitcode = -99
    if getattr(s, 'scrape', None) is not None:
        exitcode = s.scrape(*args[2:])  # type: ignore
    elif getattr(s, 'run', None) is not None:
        exitcode = s.run()  # type: ignore
    # Only when called directly, not in 'all'
    elif getattr(s, 'ad_hoc', None) is not None:
        exitcode = s.ad_hoc()  # type: ignore
    return exitcode

def run_all_tasks(module: Any, with_flag: Optional[str] = None) -> None:
    error = None
    m = importlib.import_module('{module}'.format(module=module))

    from decksite import APP
    APP.config['SERVER_NAME'] = configuration.server_name()
    with APP.app_context():
        # pylint: disable=unused-variable
        for _importer, modname, _ispkg in pkgutil.iter_modules(m.__path__):  # type: ignore
            try:
                s = importlib.import_module('{module}.{name}'.format(name=modname, module=module))

                if with_flag and not getattr(s, with_flag, False):
                    continue
                if getattr(s, 'scrape', None) is not None:
                    timer = time.perf_counter()
                    s.scrape()  # type: ignore
                    t = time.perf_counter() - timer
                    print(f'{s.__name__} completed in {t}')

                elif getattr(s, 'run', None) is not None:
                    timer = time.perf_counter()
                    s.run()  # type: ignore
                    t = time.perf_counter() - timer
                    print(f'{s.__name__} completed in {t}')
            except Exception as c:  # pylint: disable=broad-except
                from shared import repo
                repo.create_issue(f'Error running task {s.__name__}', 'CLI', 'CLI', 'PennyDreadfulMTG/perf-reports', exception=c)
                error = c

    if error:
        raise error


if __name__ == '__main__':
    cli()
