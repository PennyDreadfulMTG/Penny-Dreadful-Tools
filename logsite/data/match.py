import datetime
from typing import Any, List

import pytz
import sqlalchemy as sa  # type: ignore
from flask import url_for

from shared import dtutil

from .. import db
from ..db import DB as fsa  # type: ignore

# pylint: disable=no-member

class Match(fsa.Model): # type: ignore
    __tablename__ = 'match'
    id = sa.Column(sa.Integer, primary_key=True, autoincrement=False)
    format_id = sa.Column(sa.Integer, sa.ForeignKey('format.id'))
    comment = sa.Column(sa.String(200))
    start_time = sa.Column(sa.DateTime)
    end_time = sa.Column(sa.DateTime)

    has_unexpected_third_game = sa.Column(sa.Boolean)
    is_league = sa.Column(sa.Boolean)
    is_tournament = sa.Column(sa.Boolean)
    # is_timeout = sa.Column(sa.Boolean)

    players = fsa.relationship('User', secondary=db.MATCH_PLAYERS)
    modules = fsa.relationship('Module', secondary=db.MATCH_MODULES)
    games = fsa.relationship('Game', backref='match')
    format = fsa.relationship('Format')
    tournament = fsa.relationship('TournamentInfo', backref='match')

    def url(self) -> str:
        return url_for('show_match', match_id=self.id)

    def format_name(self) -> str:
        return self.format.get_name()

    def host(self) -> db.User:
        return self.players[0]

    def other_players(self) -> List[db.User]:
        return self.players[1:]

    def other_player_names(self) -> List[str]:
        return [p.name for p in self.other_players()]

    def set_times(self, start_time: int, end_time: int) -> None:
        self.start_time = dtutil.ts2dt(start_time)
        self.end_time = dtutil.ts2dt(end_time)
        db.commit()

    def start_time_aware(self) -> datetime.datetime:
        return pytz.utc.localize(self.start_time)

    def end_time_aware(self) -> datetime.datetime:
        return pytz.utc.localize(self.end_time)

    def display_date(self) -> str:
        if self.start_time is None:
            return ''
        return dtutil.display_date(self.start_time_aware())

    def to_dict(self) -> str:
        return {
            'id': self.id,
            'format': self.format.get_name(),
            'comment': self.comment,
            'start_time': self.start_time_aware(),
            'end_time': self.end_time_aware(),
            'players': [p.name for p in self.players],
            'games': [g.id for g in self.games],
            'tournament': self.tournament if self.tournament is not None else None,
        }

def create_match(match_id: int, format_name: str, comment: str, modules: List[str], players: List[str]) -> Match:
    format_id = db.get_or_insert_format(format_name).id
    local = Match(id=match_id, format_id=format_id, comment=comment)
    modules = [db.get_or_insert_module(mod) for mod in modules]
    local.modules = modules
    local.players = [db.get_or_insert_user(user) for user in set(players)]
    db.add(local)
    db.commit()
    return local

def get_match(match_id: int) -> Match:
    return Match.query.filter_by(id=match_id).one_or_none()

def get_recent_matches() -> Any:
    return Match.query.order_by(Match.id.desc())

def get_recent_matches_by_player(name: str) -> Any:
    return Match.query.filter(Match.players.any(db.User.name == name)).order_by(Match.id.desc())

def get_recent_matches_by_format(format_id: int) -> Any:
    return Match.query.filter(Match.format_id == format_id).order_by(Match.id.desc())
