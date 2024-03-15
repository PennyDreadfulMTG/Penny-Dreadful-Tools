from enum import Enum

from typing import Set

from decksite.database import db

class Permission(Enum):
    ADMIN = 'admin'
    DEMIMOD = 'demimod'

def permission_changes(discord_id: int) -> Set[Permission]:
    if not discord_id:
        return set()
    sql = 'SELECT permission FROM permission_changes WHERE discord_id = %s'
    return set(Permission(v) for v in db().values(sql, [discord_id]))

def delete_changes(discord_id: int) -> None:
    sql = 'DELETE FROM permission_changes WHERE discord_id = %s'
    db().execute(sql, [discord_id])
