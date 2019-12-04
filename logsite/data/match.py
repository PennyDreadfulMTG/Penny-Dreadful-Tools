import datetime
from typing import Any, Dict, List

import pytz
import peewee
from flask import url_for

from shared import dtutil

from .. import db
# pylint: disable=no-member

class Match(db.BaseModel): # type: ignore
    id = peewee.IntegerField(primary_key=True)
    format_id = peewee.ForeignKeyField(db.Format)
    comment = peewee.CharField(max_length=200)
    start_time = peewee.DateTimeField(null=True)
    end_time = peewee.DateTimeField(null=True)

    has_unexpected_third_game = peewee.BooleanField(null=True)
    is_league = peewee.BooleanField(null=True)
    is_tournament = peewee.BooleanField(null=True)
    # is_timeout = peewee.BooleanField()

    # players = fsa.relationship('User', secondary=db.MATCH_PLAYERS)
    # modules = fsa.relationship('Module', secondary=db.MATCH_MODULES)
    # tournament = fsa.relationship('TournamentInfo', backref='match')

    def url(self) -> str:
        return url_for('show_match', match_id=self.id)

    def format_name(self) -> str:
        return self.format_id.get_name()

    def host(self) -> db.User:
        return self.players[0]

    def other_players(self) -> List[db.User]:
        return self.players[1:]

    def other_player_names(self) -> List[str]:
        return [p.name for p in self.other_players()]

    def set_times(self, start_time: int, end_time: int) -> None:
        self.start_time = dtutil.ts2dt(start_time)
        self.end_time = dtutil.ts2dt(end_time)
        self.save()

    def start_time_aware(self) -> datetime.datetime:
        return pytz.utc.localize(self.start_time)

    def end_time_aware(self) -> datetime.datetime:
        return pytz.utc.localize(self.end_time)

    def display_date(self) -> str:
        if self.start_time is None:
            return ''
        return dtutil.display_date(self.start_time_aware())

    @property
    def players(self):
        return db.User.select().join(db.MatchPlayers).join(Match).where(Match.id == self.id)

    def to_dict(self) -> Dict:
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

def get_or_insert_match(match_id: int, format_name: str, comment: str) -> Match:
    format_id = db.get_or_insert_format(format_name).id
    return Match.get_or_create(id=match_id, defaults={'format_id':format_id, 'comment':comment})[0]


def create_match(match_id: int, format_name: str, comment: str, modules: List[str], players: List[str]) -> Match:
    local = get_or_insert_match(match_id, format_name, comment)
    modules = [db.get_or_insert_module(mod) for mod in modules]
    local.modules = modules
    local.players = [db.get_or_insert_user(user) for user in set(players)]
    local.save()
    return local

def get_match(match_id: int) -> Match:
    return Match.get_or_none(id=match_id)

def get_recent_matches() -> Any:
    return Match.select().order_by(Match.id.desc())

def get_recent_matches_by_player(name: str) -> Any:
    return Match.select().join(db.MatchPlayers).join(db.User).where(db.User.name == name).order_by(Match.id.desc())

def get_recent_matches_by_format(format_id: int) -> Any:
    return Match.select().where(Match.format_id == format_id).order_by(Match.id.desc())
