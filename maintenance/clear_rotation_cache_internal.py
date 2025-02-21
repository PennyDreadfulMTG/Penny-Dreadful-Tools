from decksite.data import rotation as rot
from magic import rotation


def clear(hard: bool = False) -> None:
    rotation.clear_redis()
    rotation.rotation_redis_store()
    rot.force_cache_update(hard=hard)
