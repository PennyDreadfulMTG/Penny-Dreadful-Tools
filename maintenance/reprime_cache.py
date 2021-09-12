from decksite.data import archetype, card, deck, person, playability, season
from magic import multiverse, oracle


def run() -> None:
    multiverse.rebuild_cache()
    oracle.init()
    archetype.preaggregate()
    person.preaggregate()
    card.preaggregate()
    deck.preaggregate()
    season.preaggregate()
    playability.preaggregate()
    # rule.cache_all_rules()
