import json

from flask import Flask

from magic import oracle
from shared.serialization import extra_serializer

from price_grabber import price

SRV = Flask(__name__)

@SRV.route("/<card>/")
def cardprice(card):
    if card == 'favicon.ico':
        return None
    card = card.replace('-split-', '//')
    return json.dumps(price.info_cached(name=card), default=extra_serializer)

def init():
    multiverse.init()
    oracle.init()
    SRV.run(port=5800, host='0.0.0.0')
