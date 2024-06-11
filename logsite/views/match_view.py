import datetime
import html

import inflect
import titlecase
from flask import session, url_for

from shared.pd_exception import DoesNotExistException

from .. import APP, importing
from ..data import match
from ..view import View


@APP.route('/match/<int:match_id>/')
def show_match(match_id: int) -> str:
    view = Match(match.get_match(match_id))
    return view.page()

class Match(View):
    def __init__(self, viewed_match: match.Match) -> None:
        super().__init__()
        if not viewed_match:
            raise DoesNotExistException
        self.match = viewed_match
        self.id = viewed_match.id
        self.comment = viewed_match.comment
        self.format_name = viewed_match.format_name()
        self.players_string = ' vs '.join([p.name for p in viewed_match.players])
        self.players_string_safe = ' vs '.join([player_link(p.name) for p in viewed_match.players])
        self.module_string = ', '.join([m.name for m in viewed_match.modules])
        if viewed_match.start_time and viewed_match.start_time > datetime.datetime.now() - datetime.timedelta(days=1) and not session.get('admin'):
            self.hidden = True
            return
        if not viewed_match.games:
            self.no_games = True
            return
        self.game_one = viewed_match.games[0]
        self.has_game_two = False
        self.has_game_three = False
        if len(viewed_match.games) > 1:
            self.has_game_two = True
            self.game_two = viewed_match.games[1]
        if len(viewed_match.games) > 2:
            self.has_game_three = True
            self.game_three = viewed_match.games[2]
        if viewed_match.has_unexpected_third_game is None:
            importing.reimport(viewed_match)
        self.has_unexpected_third_game = viewed_match.has_unexpected_third_game
        if viewed_match.is_tournament is None:
            importing.reimport(viewed_match)
        self.is_tournament = viewed_match.is_tournament

    def og_title(self) -> str:
        return self.players_string

    def og_url(self) -> str:
        return url_for('show_match', match_id=self.id, _external=True)

    def og_description(self) -> str:
        p = inflect.engine()
        fmt = titlecase.titlecase(p.a(self.format_name))
        description = f'{fmt} match.'
        return description

    def page_title(self) -> str:
        return ''

def player_link(name: str) -> str:
    url = url_for('show_person', person=name)
    return f'<a href="{html.escape(url)}">{html.escape(name)}</a>'
