import sqlalchemy as sa  # type: ignore

from .. import db
from ..db import DB as fsa  # type: ignore


class TournamentInfo(fsa.Model):  # type: ignore
    __tablename__ = 'match_tournament'
    id = sa.Column(sa.Integer, primary_key=True)
    match_id = sa.Column(sa.Integer, sa.ForeignKey('match.id'), nullable=False)
    tournament_id = sa.Column(sa.Integer, sa.ForeignKey(
        'tournament.id'), nullable=False)
    round_num = sa.Column(sa.Integer)


class Tournament(fsa.Model):  # type: ignore
    __tablename__ = 'tournament'
    id = sa.Column(sa.Integer, primary_key=True)
    name = sa.Column(sa.String(length=200), unique=True, index=True)
    active = sa.Column(sa.Boolean)


def get_tournament(name: str) -> Tournament:
    return Tournament.query.filter_by(name=name).one_or_none()


def create_tournament(name: str) -> Tournament:
    local = Tournament(name=name, active=True)
    db.add(local)
    db.commit()
    return local


def create_tournament_info(match_id: int, tournament_id: int) -> TournamentInfo:
    local = TournamentInfo(match_id=match_id, tournament_id=tournament_id)
    db.add(local)
    db.commit()
    return local
