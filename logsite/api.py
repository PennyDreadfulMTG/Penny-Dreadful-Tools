import json
import subprocess

from flask import Response, request, session

from shared import configuration
from shared.serialization import extra_serializer

from . import APP, importing
from .data import match


@APP.route('/api/admin/')
def admin():
    return return_json(session.get('admin'))

@APP.route('/api/matchExists/<match_id>')
def match_exists(match_id):
    return return_json(match.get_match(match_id) is not None)

@APP.route('/api/upload', methods=['POST'])
def upload():
    error = validate_api_key()
    if error:
        return error
    match_id = int(request.form['match_id'])
    lines = request.form['lines']
    importing.import_log(lines.split('\n'), match_id)
    start_time = int(request.form['start_time_utc'])
    end_time = int(request.form['end_time_utc'])
    match.get_match(match_id).set_times(start_time, end_time)

    return return_json({'success': True})

@APP.route('/api/gitpull', methods=['GET', 'POST'])
def gitpull():
    subprocess.check_output(['git', 'pull'])
    try:
        import uwsgi
        uwsgi.reload()
    except ImportError:
        pass
    return return_json(APP.config['commit-id'])

@APP.route('/export/<match_id>')
def export(match_id: int):
    local = match.get_match(match_id)
    text = '{format}\n{comment}\n{mods}\n{players}\n\n'.format(
        format=local.format.name,
        comment=local.comment,
        mods=",".join([m.name for m in local.modules]),
        players=",".join([p.name for p in local.players]))
    n = 1
    for game in local.games:
        text += '== Game {n} ({id}) ==\n'.format(n=n, id=game.id)
        n = n + 1
        text += game.sanitized_log().strip()
        text += '\n\n'
    return (text, 200, {
        'Content-type': 'text/plain; charset=utf-8',
        'Content-Disposition': 'attachment; filename={match_id}.txt'.format(match_id=match_id)
        })

def generate_error(code, msg):
    return {'error': True, 'code': code, 'msg': msg}

def return_json(content, status=200):
    content = json.dumps(content, default=extra_serializer)
    r = Response(response=content, status=status, mimetype='application/json')
    return r

def validate_api_key():
    if request.form.get('api_token', None) == configuration.get('pdbot_api_token'):
        return None
    return return_json(generate_error('UNAUTHORIZED', 'Invalid API key'), status=403)
