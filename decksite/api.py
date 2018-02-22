import json
import subprocess

from flask import Response, request, session, url_for

from decksite import APP, league
from decksite.data import card as cs
from decksite.data import competition as comp
from decksite.data import person as ps
from decksite.data import deck, guarantee, match
from magic import oracle, rotation
from shared import configuration, dtutil
from shared.serialization import extra_serializer


@APP.route('/api/decks/<deck_id>')
def deck_api(deck_id):
    blob = deck.load_deck(deck_id)
    return return_json(blob)

@APP.route('/api/competitions/<competition_id>/')
def competition_api(competition_id):
    return return_json(comp.load_competition(competition_id))

@APP.route('/api/league')
def league_api():
    return return_json(league.active_league())

@APP.route('/api/person/<person>')
def person_api(person):
    p = ps.load_person(person)
    p.decks = url_for('person_decks_api', person=person)
    return return_json(p)

@APP.route('/api/person/<person>/decks')
def person_decks_api(person):
    p = ps.load_person(person)
    return return_json(p.decks)

@APP.route('/api/league/run/<person>')
def league_run_api(person):
    decks = league.active_decks_by(person)
    if len(decks) == 0:
        return return_json(None)

    run = guarantee.exactly_one(decks)

    decks = league.active_decks()
    already_played = [m.opponent_deck_id for m in match.get_matches(run)]
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

@APP.route('/api/rotation')
def rotation_api():
    now = dtutil.now()
    diff = rotation.next_rotation() - now
    result = {
        "last": rotation.last_rotation_ex(),
        "next": rotation.next_rotation_ex(),
        "diff": diff.total_seconds(),
        "friendly_diff": dtutil.display_time(diff.total_seconds())
    }
    return return_json(result)

@APP.route('/api/cards')
def cards_api():
    return return_json(cs.played_cards())

@APP.route('/api/card/<card>')
def card_api(card):
    return return_json(oracle.load_card(card))

@APP.route('/api/sitemap/')
def sitemap():
    urls = [url_for(rule.endpoint) for rule in APP.url_map.iter_rules() if 'GET' in rule.methods and len(rule.arguments) == 0]
    return return_json(urls)

@APP.route('/api/admin/')
def admin():
    return return_json(session.get('admin'))

@APP.route('/api/gitpull', methods=['POST'])
def gitpull():
    if request.headers.get('X-GitHub-Event') == "push":
        payload = json.loads(request.data)
        if payload['ref'] == "refs/heads/master":
            try:
                subprocess.check_output(['git', 'pull'])
                subprocess.check_output(['pip', 'install', '-U', '--user', '-r', 'requirements.txt', '--no-cache'])
                import uwsgi
                uwsgi.reload()
                return return_json({'rebooting': True})
            except ImportError:
                pass
    return return_json({'rebooting': False, 'commit-id': APP.config['commit-id']})

def validate_api_key():
    if request.form.get('api_token', None) == configuration.get('pdbot_api_token'):
        return None
    return return_json(generate_error('UNAUTHORIZED', 'Invalid API key'), status=403)

def generate_error(code, msg):
    return {'error': True, 'code': code, 'msg': msg}

def return_json(content, status=200):
    content = json.dumps(content, default=extra_serializer)
    r = Response(response=content, status=status, mimetype="application/json")
    return r
