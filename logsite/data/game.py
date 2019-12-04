from typing import Dict

import peewee

from .. import db

CLEARANCE_PUBLIC = 0    # Anyone can view
CLEARANCE_PLAYERS = 1   # Players in the game can view
CLEARANCE_MODS = 2      # Mods, TOs, etc
CLEARANCE_ADMIN = 3     # Debug info, developer eyes only.

class Game(db.BaseModel): # type: ignore
    id = peewee.IntegerField(primary_key=True)
    match_id = peewee.DeferredForeignKey('Match', backref='games')
    winner_id = peewee.DeferredForeignKey('User')

    log = peewee.TextField()


    def sanitized_log(self) -> str:
        if 'Exception:' in self.log:
            return 'Log is not visible at this time.  Please contact Silasary.'
        # If we want to remove chat, or OOB messages, do that here.
        return str(self.log).strip()

    def to_dict(self) -> Dict:
        return {
            'id': self.id,
            'match_id': self.match_id,
            'winner': self.winner_id,
            'log': self.log,
        }

def insert_game(game_id: int, match_id: int, game_lines: str) -> None:
    Game.insert({'id':game_id, 'match_id':match_id, 'log':game_lines}).on_conflict_replace().execute()

def get_game(game_id: int) -> Game:
    return Game.query.filter_by(id=game_id).one_or_none()

class Line(db.BaseModel): #type: ignore
    id = peewee.AutoField()
    game_id = peewee.DeferredForeignKey('Game')
    clearance = peewee.IntegerField(null=True)
