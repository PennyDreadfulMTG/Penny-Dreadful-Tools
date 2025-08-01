# type: ignore


from flask import Response, request, session

from shared import repo
from shared.pd_exception import InvalidDataException
from shared_web.api import return_json, validate_api_key

from . import APP, db, importing
from .data import game, match


@APP.route('/api/admin')
@APP.route('/api/admin/')
def admin() -> Response:
    return return_json(session.get('admin'))

@APP.route('/api/status')
@APP.route('/api/status/')
def person_status() -> Response:
    r = {
        'mtgo_username': session.get('mtgo_username'),
        'discord_id': session.get('discord_id'),
        'admin': session.get('admin', False),
        'hide_intro': request.cookies.get('hide_intro', False),
    }
    return return_json(r)

@APP.route('/api/matchExists/<match_id>')
@APP.route('/api/matchExists/<match_id>/')
def match_exists(match_id: int) -> Response:
    return return_json(match.get_match(match_id) is not None)

@APP.route('/api/person/<person>')
@APP.route('/api/person/<person>/')
def person_data(person: str) -> Response:
    return return_json(list(match.Match.query.filter(match.Match.players.any(db.User.name == person))))

@APP.route('/api/match/<match_id>')
@APP.route('/api/match/<match_id>/')
def match_data(match_id: int) -> Response:
    return return_json(match.get_match(match_id))

@APP.route('/api/game/<game_id>')
@APP.route('/api/game/<game_id>/')
def game_data(game_id: int) -> Response:
    return return_json(game.get_game(game_id))

@APP.route('/api/upload', methods=['POST'])
@APP.route('/api/upload/', methods=['POST'])
def upload() -> Response:
    error = validate_api_key()
    if error:
        return error
    match_id = int(request.form['match_id'])
    if match_id in [219603564, 264878023, 279111370]:
        return return_json({'success': True})  # Prevent infinite 500 errors.

    try:
        if request.form.get('lines'):
            lines = request.form['lines']
            importing.import_log(lines.split('\n'), match_id)
        else:
            importing.import_from_pdbot(match_id)
        start_time = int(request.form['start_time_utc'])
        end_time = int(request.form['end_time_utc'])
        match.get_match(match_id).set_times(start_time, end_time)
    except InvalidDataException as e:
        repo.create_issue('Error uploading match', 'logsite', 'logsite', 'PennyDreadfulMTG/perf-reports', exception=e)

    return return_json({'success': True})

@APP.route('/export/<match_id>')
@APP.route('/export/<match_id>/')
def export(match_id: int) -> tuple[str, int, dict[str, str]]:
    local = match.get_match(match_id)
    if local is None:
        return return_json({'success': False})
    text = '{format}\n{comment}\n{mods}\n{players}\n\n'.format(
        format=local.format.name,
        comment=local.comment,
        mods=','.join([m.name for m in local.modules]),
        players=','.join([p.name for p in local.players]))
    n = 1
    for g in local.games:
        text += f'== Game {n} ({g.id}) ==\n'
        n = n + 1
        text += g.sanitized_log().strip()
        text += '\n\n'
    text = text.replace('\n', '\r\n')
    return (text, 200, {
        'Content-type': 'text/plain; charset=utf-8',
        'Content-Disposition': f'attachment; filename={match_id}.txt',
    })
