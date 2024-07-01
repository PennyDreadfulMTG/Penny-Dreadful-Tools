from enum import Enum

from decksite.database import db


class Permission(Enum):
    ADMIN = 'admin'
    DEMIMOD = 'demimod'
    NONE = None


def permission_changes(discord_id: int) -> set[Permission]:
    if not discord_id:
        return set()
    sql = 'SELECT permission FROM permission_changes WHERE discord_id = %s'
    return {Permission(v) for v in db().values(sql, [discord_id])}
