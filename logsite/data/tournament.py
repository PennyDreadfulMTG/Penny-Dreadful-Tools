from typing import Dict

import peewee

from .. import db


class TournamentInfo(db.BaseModel):  # type: ignore
    id = peewee.AutoField()
    match_id = peewee.DeferredForeignKey('Match')
    tournament_id = peewee.DeferredForeignKey('Tournament')
    round_num = peewee.IntegerField()

    def to_dict(self) -> Dict:
        return {
            'id': self.id,
            'match_id': self.match_id,
            'tournament_id': self.tournament_id,
            'rount_num': self.round_num,
        }

class Tournament(db.BaseModel):  # type: ignore
    id = peewee.AutoField()
    name = peewee.CharField(max_length=200, unique=True, index=True)
    active = peewee.BooleanField()


def get_tournament(name: str) -> Tournament:
    return Tournament.query.filter_by(name=name).one_or_none()


def create_tournament(name: str) -> Tournament:
    local = Tournament.get_or_create(name=name, defaults={'active': True})
    return local[0]


def create_tournament_info(match_id: int, tournament_id: int) -> TournamentInfo:
    local = TournamentInfo.get_or_create(match_id=match_id, tournament_id=tournament_id)
    return local[0]
