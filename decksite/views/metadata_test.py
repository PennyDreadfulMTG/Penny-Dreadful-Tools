from decksite.data.archetype import Archetype
from decksite.views.archetype import Archetype as ArchetypeView
from decksite.views.deck import Deck as DeckView
from shared.container import Container


def test_deck_open_graph_metadata_removes_emoji_from_mixed_text() -> None:
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
    assert view.og_description() == 'A deck by Pilot'


def test_archetype_open_graph_metadata_removes_emoji_from_mixed_text() -> None:
    view = ArchetypeView.__new__(ArchetypeView)
    view.archetype = Archetype(name='Burn🔥')

    assert view.og_title() == 'Burn'
    assert view.og_description() == 'Penny Dreadful Burn archetype'


def test_open_graph_metadata_uses_words_for_emoji_only_fields() -> None:
    deck_view = DeckView.__new__(DeckView)
    deck_view.deck = Container({
        'name': '🔥',
        'archetype_name': None,
        'reviewed': False,
        'person': '🐟',
    })
    deck_view.is_in_current_run = False
    deck_view.person_id = None
    archetype_view = ArchetypeView.__new__(ArchetypeView)
    archetype_view.archetype = Archetype(name='🔥')

    assert deck_view.og_title() == 'fire'
    assert deck_view.og_description() == 'A deck by fish'
    assert archetype_view.og_description() == 'Penny Dreadful fire archetype'
