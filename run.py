import importlib
import pkgutil
import sys

def run():
    if len(sys.argv) == 0:
        print("No entry point specified.")
        exit(1)

    if "discordbot" in sys.argv:
        from discordbot import bot
        bot.init()
    elif "decksite" in sys.argv:
        from decksite import main
        main.init()
    elif "price_grabber" in sys.argv:
        from price_grabber import price_grabber
        price_grabber.fetch()
        price_grabber.price.cache()
    elif "srv_price" in sys.argv:
        from price_grabber import srv_prices
        srv_prices.init()
    elif "scraper" in sys.argv:
        name = sys.argv.pop()
        from decksite.main import APP
        APP.config["SERVER_NAME"] = "127:0.0.1:5000"
        with APP.app_context():
            if name == "all":
                m = importlib.import_module('decksite.scrapers')
                #pylint: disable=unused-variable
                for importer, modname, ispkg in pkgutil.iter_modules(m.__path__):
                    s = importlib.import_module('decksite.scrapers.{name}'.format(name=modname))
                    if getattr(s, "scrape", None) is not None:
                        s.scrape()
            else:
                m = importlib.import_module('decksite.scrapers.{name}'.format(name=name))
                m.scrape()
    else:
        print("You didn't tell me what to run or I don't recognize that name")

run()
