import json
import datetime

from flask import Response
import munch

from decksite import APP, league
from decksite.data import deck, competition as comp, guarantee

# from shared import configuration
# from decksite.scrapers import tappedout

# def auth():
#     if not tappedout.is_authorised():
#         tappedout.login(configuration.get('to_username'), configuration.get('to_password'))

# @APP.route("/api/scrape/tappedout/")
# def tappedout_recent():
#     auth()
#     return return_json(tappedout.fetch_decks())

@APP.route("/api/decks/<deck_id>")
def deck_api(deck_id):
    blob = deck.load_deck(deck_id)
    return return_json(blob)

@APP.route('/api/competitions/<competition_id>/')
def competition_api(competition_id):
    return return_json(comp.load_competition(competition_id))

@APP.route('/api/league')
def league_api():
    return return_json(league.active_league())

@APP.route('/api/league/run/<person>')
def league_run_api(person):
    decks = league.active_decks_by(person)
    if len(decks) == 0:
        return return_json(None)

    run = guarantee.exactly_one(decks)

    decks = league.active_decks()
    already_played = [m.opponent for m in league.get_matches(run)]
    run.can_play = [d.person for d in decks if d.person != person and d.person not in already_played]

    return return_json(run)

def return_json(content):
    content = json.dumps(content, default=extra_serializer)
    r = Response(response=content, status=200, mimetype="application/json")
    return r

def extra_serializer(obj):
    """JSON serializer for objects not serializable by default json code"""

    if isinstance(obj, datetime.datetime):
        return obj.isoformat()
    elif isinstance(obj, bytes):
        return obj.decode('utf-8')
    elif isinstance(obj, set):
        return list(obj)

    raise TypeError("Type {t} not serializable".format(t=type(obj)))
