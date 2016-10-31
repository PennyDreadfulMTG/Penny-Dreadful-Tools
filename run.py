import importlib
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
            m = importlib.import_module('decksite.scrapers.{name}'.format(name=name))
            m.scrape()
    else:
        print("You didn't tell me what to run or I don't recognize that name")

run()
