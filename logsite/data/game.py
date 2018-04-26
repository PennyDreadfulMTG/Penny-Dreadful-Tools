import sqlalchemy as sa
from typing import List

from .. import db
from ..db import DB as fsa


class Game(fsa.Model): # type: ignore
    __tablename__ = 'game'
    id = sa.Column(fsa.Integer, primary_key=True, autoincrement=False)
    match_id = sa.Column(sa.Integer, sa.ForeignKey('match.id'), nullable=False)
    winner_id = sa.Column(sa.Integer, sa.ForeignKey('user.id'), nullable=True)
    log = fsa.Column(sa.Text)
    winner = fsa.relationship('User')

    def sanitized_log(self):
        if 'Exception:' in self.log:
            return 'Log is not visible at this time.  Please contact Silasary.'
        # If we want to remove chat, or OOB messages, do that here.
        return self.log.strip()

def insert_game(game_id: int, match_id: int, game_lines: str) -> None:
    local = Game(id=game_id, match_id=match_id, log=game_lines)
    db.Merge(local) # This will replace an old version of the game, if one exists.
    db.Commit()
