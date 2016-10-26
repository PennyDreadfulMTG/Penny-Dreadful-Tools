import json

from flask import Flask

from price_grabber import price

SRV = Flask(__name__)

@SRV.route("/<card>/")
def cardprice(card):
    return json.dumps(price.info_cached(name=card))

SRV.run(port=5800, host='0.0.0.0')
