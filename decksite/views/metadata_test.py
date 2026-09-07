from decksite.data.archetype import Archetype
from decksite.main import APP
from decksite.views.about import About
from decksite.views.archetype import Archetype as ArchetypeView
from decksite.views.competitions import Competitions
from decksite.views.deck import Deck as DeckView
from decksite.views.home import Home
from decksite.views.league_info import LeagueInfo
from decksite.views.metagame import Metagame
from decksite.views.resources import Resources
from decksite.views.tournaments import Tournaments
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


def test_marquee_pages_have_open_graph_metadata() -> None:
    with APP.test_request_context('/tournaments/', base_url='https://pennydreadfulmagic.com/'):
        tournaments_view = Tournaments.__new__(Tournaments)

        assert tournaments_view.og_title() == 'Cardhoarder Tournaments'
        assert tournaments_view.og_url() == 'https://pennydreadfulmagic.com/tournaments/'
        assert tournaments_view.og_description() == 'Play in free weekly Penny Dreadful tournaments on Magic Online, with Cardhoarder prizes and events scheduled across multiple time zones.'

    with APP.test_request_context('/', base_url='https://pennydreadfulmagic.com/'):
        home_view = Home.__new__(Home)

        assert home_view.og_title() == 'Penny Dreadful Magic'
        assert home_view.og_url() == 'https://pennydreadfulmagic.com/'
        assert home_view.og_description() == 'Penny Dreadful is an ultra-budget Magic Online format with thousands of legal cards, free weekly tournaments, a free league, and quarterly rotations.'


def test_other_marquee_pages_have_specific_open_graph_descriptions() -> None:
    assert LeagueInfo.__new__(LeagueInfo).og_description() == 'Join the free, play-anytime Penny Dreadful league on Magic Online, play five-match runs, and compete for monthly Cardhoarder prizes.'
    assert Metagame.__new__(Metagame).og_description() == 'Explore the Penny Dreadful metagame, including popular archetypes, matchups, and successful decklists from recent leagues and tournaments.'
    assert Competitions.__new__(Competitions).og_description() == 'Browse Penny Dreadful tournament and league results, standings, decklists, and match records from the current season and past seasons.'
    assert Resources.__new__(Resources).og_description() == 'Find Penny Dreadful tools and community resources, including deck checks, rotation information, Discord, and useful external links.'
    assert About.__new__(About).og_description() == 'Discover Penny Dreadful, an ultra-budget Magic Online format with thousands of legal cards, quarterly rotations, free events, and a friendly community.'
