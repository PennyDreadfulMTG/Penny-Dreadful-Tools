import requests
from flask import url_for

from decksite.main import APP


def run() -> None:
    urls = [url_for(rule.endpoint) for rule in APP.url_map.iter_rules() if 'GET' in rule.methods and len(rule.arguments) == 0]

    seasons = ['9', 'all']
    endpoints = [rule.endpoint for rule in APP.url_map.iter_rules() if 'GET' in rule.methods and len(rule.arguments) == 1 and 'season_id' in rule.arguments]
    for endpoint in endpoints:
        for season_id in seasons:
            urls.append(url_for(endpoint, season_id=season_id))

    # We don't currently visit archetypes (~200), cards (~10,000), people (~2000) or decks (~10,000) because they are numerous. But perhaps we should visit some or all fo them?

    session = requests.session()
    session.headers.update({'User-Agent': 'pennydreadfulmagic.com cache renewer'})
    # It would be nice to exclude endpoints that are not cached admin urls but it's hard to determine those programatically. We make an approximation here.
    urls = [url for url in urls if 'admin' not in url and 'api' not in url and 'authenticate' not in url]
    for url in urls:
        print(url)
        session.get(url)
