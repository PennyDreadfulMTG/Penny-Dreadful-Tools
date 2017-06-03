import json
import datetime

from flask import Response, request

from decksite import APP, league
from decksite.data import deck, competition as comp, guarantee

from shared import configuration

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
    already_played = [m.opponent_deck_id for m in league.get_matches(run)]
    run.can_play = [d.person for d in decks if d.person != person and d.id not in already_played]

    return return_json(run)

@APP.route('/api/league/drop/<person>', methods=['POST'])
def drop(person):
    error = validate_api_key()
    if error:
        return error

    decks = league.active_decks_by(person)
    if len(decks) == 0:
        return return_json(generate_error('NO_ACTIVE_RUN', 'That person does not have an active run'))

    run = guarantee.exactly_one(decks)

    league.retire_deck(run)
    result = {'success':True}
    return return_json(result)

def validate_api_key():
    if request.form.get('api_token', None) == configuration.get('pdbot_api_token'):
        return None

    return return_json(generate_error('UNAUTHORIZED', 'Invalid API key'), status=403)

def generate_error(code, msg):
    return {'error':True, 'code':code, 'msg':msg}

def return_json(content, status=200):
    content = json.dumps(content, default=extra_serializer)
    r = Response(response=content, status=status, mimetype="application/json")
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
