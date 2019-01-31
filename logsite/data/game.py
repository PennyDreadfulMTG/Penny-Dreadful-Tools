import sqlalchemy as sa

from .. import db
from ..db import DB as fsa

CLEARANCE_PUBLIC = 0    # Anyone can view
CLEARANCE_PLAYERS = 1   # Players in the game can view
CLEARANCE_MODS = 2      # Mods, TOs, etc
CLEARANCE_ADMIN = 3     # Debug info, developer eyes only.

class Game(fsa.Model): # type: ignore
    __tablename__ = 'game'
    id = sa.Column(fsa.Integer, primary_key=True, autoincrement=False)
    match_id = sa.Column(sa.Integer, sa.ForeignKey('match.id'), nullable=False)
    winner_id = sa.Column(sa.Integer, sa.ForeignKey('user.id'), nullable=True)
    log = fsa.Column(sa.Text)
    winner = fsa.relationship('User')

    def sanitized_log(self) -> str:
        if 'Exception:' in self.log:
            return 'Log is not visible at this time.  Please contact Silasary.'
        # If we want to remove chat, or OOB messages, do that here.
        return self.log.strip()

def insert_game(game_id: int, match_id: int, game_lines: str) -> None:
    local = Game(id=game_id, match_id=match_id, log=game_lines)
    db.merge(local) # This will replace an old version of the game, if one exists.
    db.commit()

class Line(fsa.Model): #type: ignore
    id = sa.Column(fsa.Integer, primary_key=True, autoincrement=True)
    game_id = sa.Column(sa.Integer, sa.ForeignKey('game.id'), nullable=False)
    clearance = sa.Column(sa.Integer, nullable=True)
