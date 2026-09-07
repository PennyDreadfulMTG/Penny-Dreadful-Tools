import pytest

from decksite.data import site_search


def test_results_rank_exact_then_prefix_then_substring_and_cap() -> None:
    items: list[site_search.SearchResult] = [
        {'name': 'Bolt', 'type': 'Card', 'url': '/exact'},
        {'name': 'Boltbender', 'type': 'Card', 'url': '/prefix-long'},
        {'name': 'Bolt Bend', 'type': 'Card', 'url': '/prefix-short'},
        {'name': 'Lightning Bolt', 'type': 'Card', 'url': '/substring'},
        {'name': 'Unrelated', 'type': 'Card', 'url': '/unrelated'},
    ]

    assert site_search.results(items, 'BOLT', limit=3) == [items[0], items[2], items[1]]


def test_card_names_searches_the_live_oracle_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(site_search.oracle, 'cards_by_name', lambda: {
        'Lightning Bolt': object(),
        'Bolt Bend': object(),
        'Boltbender': object(),
        'Not a Match': object(),
    })

    monkeypatch.setattr(site_search, 'card_aliases', lambda: {})

    assert site_search.card_names('bolt', limit=2) == [
        {'name': 'Bolt Bend', 'search_name': 'Bolt Bend'},
        {'name': 'Boltbender', 'search_name': 'Boltbender'},
    ]


def test_card_names_rank_aliases_and_return_canonical_names(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(site_search.oracle, 'cards_by_name', lambda: {
        'Dark Confidant': object(),
        'Lightning Bolt': object(),
        'Bolt Bend': object(),
    })
    monkeypatch.setattr(site_search, 'card_aliases', lambda: {
        'bob': 'Dark Confidant',
        'bolt': 'Lightning Bolt',
        'stale': 'Not a Card',
    })

    assert site_search.card_names('bo') == [
        {'name': 'Dark Confidant', 'search_name': 'bob'},
        {'name': 'Lightning Bolt', 'search_name': 'bolt'},
        {'name': 'Bolt Bend', 'search_name': 'Bolt Bend'},
    ]


@pytest.mark.parametrize(
    ('function_name', 'expected_from'),
    [
        ('archetype_names', 'FROM archetype'),
        ('person_names', 'FROM person AS p'),
    ],
)
def test_database_names_are_ranked_and_limited(function_name: str, expected_from: str, monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeDatabase:
        def values(self, sql: str, args: list[str | int]) -> list[str]:
            assert expected_from in sql
            assert 'WHEN' in sql
            assert 'CHAR_LENGTH' in sql
            assert args == ['%bolt%', 'bolt', 'bolt%', 7]
            return ['Bolt Result']

    monkeypatch.setattr(site_search, 'db', FakeDatabase)

    search_names = getattr(site_search, function_name)
    assert search_names('bolt', limit=7) == ['Bolt Result']


def test_database_names_treat_like_wildcards_as_literal_characters(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeDatabase:
        def values(self, _sql: str, args: list[str | int]) -> list[str]:
            assert args == [r'%100\%\_match%', '100%_match', r'100\%\_match%', 10]
            return []

    monkeypatch.setattr(site_search, 'db', FakeDatabase)

    assert site_search.archetype_names('100%_match') == []
