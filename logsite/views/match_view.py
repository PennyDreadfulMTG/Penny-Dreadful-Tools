import html

import inflect
import titlecase
from flask import url_for

from shared.pd_exception import DoesNotExistException

from .. import APP, importing
from ..data import match
from ..view import View


@APP.route('/match/<match_id>/')
def show_match(match_id):
    view = Match(match.get_match(match_id))
    return view.page()

# pylint: disable=no-self-use,too-many-instance-attributes
class Match(View):
    def __init__(self, viewed_match: match.Match) -> None:
        if not viewed_match:
            raise DoesNotExistException()
        self.match = viewed_match
        self.id = viewed_match.id
        self.comment = viewed_match.comment
        self.format_name = viewed_match.format_name()
        self.players_string = ' vs '.join([p.name for p in viewed_match.players])
        self.players_string_safe = ' vs '.join([player_link(p.name) for p in viewed_match.players])
        self.module_string = ', '.join([m.name for m in viewed_match.modules])
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

    def og_title(self):
        return self.players_string

    def og_url(self):
        return url_for('show_match', match_id=self.id, _external=True)

    def og_description(self):
        p = inflect.engine()
        fmt = titlecase.titlecase(p.a(self.format_name))
        description = '{fmt} match.'.format(fmt=fmt)
        return description

def player_link(name):
    url = url_for('show_person', person=name)
    return '<a href="{url}">{name}</a>'.format(url=html.escape(url), name=html.escape(name))
