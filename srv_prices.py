from flask import Flask
import json

import price

SRV = Flask(__name__)

@SRV.route("/<card>/")
def cardprice(card):
    return json.dumps(price.info_cached(name=card))

SRV.run(port=5800)