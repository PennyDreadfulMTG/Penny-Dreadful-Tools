from decksite.data.archetype import Archetype
from decksite.views.archetype import Archetype as ArchetypeView
from decksite.views.deck import Deck as DeckView
from shared.container import Container


def test_deck_open_graph_metadata_replaces_emoji_with_words() -> None:
    view = DeckView.__new__(DeckView)
    view.deck = Container({
        'name': '🃏🔥',
        'archetype_name': None,
        'reviewed': False,
        'person': 'Pilot✋',
    })
    view.is_in_current_run = False
    view.person_id = None

    assert view.og_title() == 'black joker fire'
    assert view.og_description() == 'A deck by Pilot raised hand'


def test_archetype_open_graph_metadata_replaces_emoji_with_words() -> None:
    view = ArchetypeView.__new__(ArchetypeView)
    view.archetype = Archetype(name='Burn🔥')

    assert view.og_title() == 'Burn fire'
    assert view.og_description() == 'Penny Dreadful Burn fire archetype'
