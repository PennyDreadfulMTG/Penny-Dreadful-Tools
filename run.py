import importlib
import pkgutil
import sys

def run():
    if len(sys.argv) == 0:
        print("No entry point specified.")
        sys.exit(1)

    if "discordbot" in sys.argv:
        from discordbot import bot
        bot.init()
    elif "decksite" in sys.argv:
        from decksite import main
        main.init()
    elif "price_grabber" in sys.argv:
        from price_grabber import price_grabber
        price_grabber.run()
    elif "srv_price" in sys.argv:
        from price_grabber import srv_prices
        srv_prices.init()
    elif sys.argv[1] in ["scraper", "scrapers", "maintenance"]:
        module = sys.argv[1]
        if module == "scraper":
            module = "scrapers"
        name = sys.argv.pop()
        from decksite.main import APP
        APP.config["SERVER_NAME"] = "127:0.0.1:5000"
        with APP.app_context():
            from magic import oracle
            oracle.init()
            if name == "all":
                m = importlib.import_module('decksite.{module}'.format(module=module))
                #pylint: disable=unused-variable
                for importer, modname, ispkg in pkgutil.iter_modules(m.__path__):
                    s = importlib.import_module('decksite.{module}.{name}'.format(name=modname, module=module))
                    if getattr(s, "scrape", None) is not None:
                        s.scrape()
                    elif getattr(s, "run", None) is not None:
                        s.run()
            else:
                s = importlib.import_module('decksite.{module}.{name}'.format(name=name, module=module))
                if getattr(s, "scrape", None) is not None:
                    s.scrape()
                elif getattr(s, "run", None) is not None:
                    s.run()
    elif "tests" in sys.argv:
        import pytest
        sys.argv.remove("tests")
        code = pytest.main()
        sys.exit(code)
    elif "decksite-profiler" in sys.argv:
        from werkzeug.contrib.profiler import ProfilerMiddleware
        from decksite import main
        main.APP.config['PROFILE'] = True
        main.APP.wsgi_app = ProfilerMiddleware(main.APP.wsgi_app, restrictions=[30])
        main.init()
    else:
        print("You didn't tell me what to run or I don't recognize that name")
        sys.exit(1)
    sys.exit(0)

run()
