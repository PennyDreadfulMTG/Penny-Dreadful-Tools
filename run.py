import sys


def run():
    if len(sys.argv) == 0:
        print("No entry point specified.")
        exit(1)

    app = sys.argv[0]

    if app == "discordbot":
        from discordbot import bot
        bot.init()
    elif app == "decksite":
        from decksite import main
        main.init()
    elif app == "price_grabber":
        from price_grabber import price_grabber
        price_grabber.fetch()
        price_grabber.price.cache()
    elif app == "srv_price":
        from price_grabber import srv_prices
        srv_prices.init()
