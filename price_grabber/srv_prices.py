import json
from typing import Optional

from flask import Flask

from magic import multiverse, oracle
from price_grabber import price
from shared.serialization import extra_serializer

SRV = Flask(__name__)

@SRV.route('/<card>/') # type: ignore
def cardprice(card: str) -> Optional[str]:
    if card == 'favicon.ico':
        return None
    card = card.replace('-split-', '//')
    return json.dumps(price.info_cached(name=card), default=extra_serializer)

def init() -> None:
    multiverse.init()
    oracle.init()
    SRV.run(port=5800, host='0.0.0.0')
