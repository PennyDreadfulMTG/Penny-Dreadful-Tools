import pytest
from cachelib.simple import SimpleCache

from decksite.controllers import banners
from shared.container import Container
from shared.pd_exception import DatabaseException


@pytest.fixture
def banner_cards(monkeypatch: pytest.MonkeyPatch) -> list[Container]:
    cards = [Container({'name': f'Card {color}', 'colors': list(color), 'type_line': 'Instant'}) for color in ['W', 'U', 'B', 'R', 'G', '', 'WU', 'UB']]
    by_name = {c.name: c for c in cards}
    monkeypatch.setattr(banners.oracle, 'load_card', by_name.__getitem__)
    monkeypatch.setattr(banners, 'BANNER_CACHE', SimpleCache(default_timeout=5 * 60))
    return cards


@pytest.mark.parametrize('failure', ['empty', 'database'])
def test_placeholder_is_cached_briefly_then_retried(monkeypatch: pytest.MonkeyPatch, banner_cards: list[Container], failure: str) -> None:
    available = False
    now = 1000
    calls = 0
    monkeypatch.setattr('cachelib.simple.time', lambda: now)

    def season_playability(_season: int) -> list[Container]:
        nonlocal calls
        calls += 1
        if not available:
            if failure == 'database':
                raise DatabaseException('Stats unavailable')
            return []
        return banner_cards

    monkeypatch.setattr(banners.playability, 'season_playability', season_playability)
    assert banners.guess_banner(43)[1] == 'New Perspectives'

    available = True
    now += 59
    assert banners.guess_banner(43)[1] == 'New Perspectives'
    assert calls == 1

    now += 2
    assert banners.guess_banner(43) == ([c.name for c in banner_cards[:7]], banner_cards[7].name)
    assert calls == 2


@pytest.mark.parametrize('qualifiers', [1, 2, 6, 7, 8])
def test_banner_uses_available_qualifiers_and_caches_the_result(monkeypatch: pytest.MonkeyPatch, banner_cards: list[Container], qualifiers: int) -> None:
    calls = 0
    cards = banner_cards[:qualifiers]

    def season_playability(_season: int) -> list[Container]:
        nonlocal calls
        calls += 1
        return cards

    monkeypatch.setattr(banners.playability, 'season_playability', season_playability)
    expected = [c.name for c in cards[:-1]], cards[-1].name

    assert banners.guess_banner(43) == expected
    assert banners.guess_banner(43) == expected
    assert calls == 1


def test_partial_banner_skips_basics_duplicate_cards_and_repeated_colors(monkeypatch: pytest.MonkeyPatch, banner_cards: list[Container]) -> None:
    banner_cards[0].type_line = 'Basic Land'
    banner_cards[7].colors = banner_cards[1].colors
    cards = [banner_cards[0], banner_cards[1], banner_cards[1], banner_cards[7], *banner_cards[2:7]]
    monkeypatch.setattr(banners.playability, 'season_playability', lambda _season: cards)

    assert banners.guess_banner(43) == ([c.name for c in banner_cards[1:6]], banner_cards[6].name)


def test_only_basic_lands_uses_placeholder(monkeypatch: pytest.MonkeyPatch, banner_cards: list[Container]) -> None:
    for card in banner_cards:
        card.type_line = 'Basic Land'
    monkeypatch.setattr(banners.playability, 'season_playability', lambda _season: banner_cards)

    assert banners.guess_banner(43)[1] == 'New Perspectives'


def test_successful_banner_refreshes_after_five_minutes(monkeypatch: pytest.MonkeyPatch, banner_cards: list[Container]) -> None:
    now = 1000
    monkeypatch.setattr('cachelib.simple.time', lambda: now)
    cards = banner_cards[:]
    monkeypatch.setattr(banners.playability, 'season_playability', lambda _season: cards[:])
    original = banners.guess_banner(43)

    cards.reverse()
    now += 299
    assert banners.guess_banner(43) == original

    now += 2
    assert banners.guess_banner(43) == ([c.name for c in cards[:7]], cards[7].name)


def test_banner_cache_is_separate_for_each_season(monkeypatch: pytest.MonkeyPatch, banner_cards: list[Container]) -> None:
    cards_by_season = {42: banner_cards, 43: list(reversed(banner_cards))}
    monkeypatch.setattr(banners.playability, 'season_playability', cards_by_season.__getitem__)

    previous = banners.guess_banner(42)
    current = banners.guess_banner(43)

    assert previous != current
    assert previous == ([c.name for c in banner_cards[:7]], banner_cards[7].name)
    assert current == ([c.name for c in reversed(banner_cards[1:])], banner_cards[0].name)
