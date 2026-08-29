import unittest
from pathlib import Path

import pytest
import whoosh
from whoosh.index import create_in

from magic import whoosh_write
from magic.models import Card
from magic.whoosh_constants import WhooshConstants
from magic.whoosh_search import WhooshSearcher


@pytest.mark.functional
class WhooshSearchTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        try:
            cls.searcher = WhooshSearcher()  # type: ignore
        except whoosh.index.EmptyIndexError:  # Whoosh hasn't been initialized yet!
            whoosh_write.reindex()
            cls.searcher = WhooshSearcher()  # type: ignore

    def best_match_is(self, query: str, expected_best_match: str, *additional_matches: str) -> None:
        result = self.searcher.search(query)  # type: ignore
        assert result.get_best_match() == expected_best_match
        all_matches = result.get_all_matches()
        for r in additional_matches:
            assert is_included(r, all_matches)

    def best_match_in(self, query: str, expected_best_match: list[str], *additional_matches: str) -> None:
        # For reasons I can't figure out, searching the rear half of a meld card is inconsistent about which front half it wants
        # So we just want to be sure it's one of them
        result = self.searcher.search(query)  # type: ignore
        assert result.get_best_match() in expected_best_match
        all_matches = result.get_all_matches()
        for r in additional_matches:
            assert is_included(r, all_matches)

    def finds_at_least(self, query: str, card_name: str) -> None:
        result = self.searcher.search(query)  # type: ignore
        cards = result.get_all_matches()
        cards = [c for c in cards if c is not None]
        assert len(cards) >= 1
        assert is_included(card_name, cards)

    def aliases_are_exact(self) -> None:
        for q, card in (('bob', 'Dark Confidant'), ('jens', 'Solemn Simulacrum'), ('sad robot', 'Solemn Simulacrum'), ('mom', 'Mother of Runes'), ('tim', 'Prodigal Sorcerer'), ('gary', 'Gray Merchant of Asphodel'), ('finkel', 'Shadowmage Infiltrator'), ('kai', 'Voidmage Prodigy'), ('tiago', 'Snapcaster Mage'), ('pikula', 'Meddling Mage'), ('durdle turtle', 'Meandering Towershell'), ('volvary', 'Aura Barbs'), ('bolt', 'Lightning Bolt'), ('ftk', 'Flametongue Kavu'), ('fow', 'Force of Will'), ('looter scooter', "Smuggler's Copter"), ('nerd ape', "Inventor's Apprentice")):
            result = self.searcher.search(q)  # type: ignore
            assert result.get_best_match() == card

    def test_assorted_typos(self) -> None:
        self.finds_at_least('Define Bloodlord', 'Defiant Bloodlord')
        self.finds_at_least('Ashenmoor Gourger', 'Ashenmoor Gouger')
        self.finds_at_least('Ashenmmor', 'Ashenmoor Gouger')
        self.finds_at_least('narcomeba', 'Narcomoeba')
        self.best_match_is('Uphaeval', 'Upheaval')
        self.finds_at_least('devler of secrets', 'Delver of Secrets')

    def test_split_cards(self) -> None:
        self.finds_at_least('Far/Away', 'Far // Away')
        self.finds_at_least('Ready / Willing', 'Ready // Willing')
        self.finds_at_least('Fire // Ice', 'Fire // Ice')

    def test_special_chars(self) -> None:
        self.finds_at_least('Jötun Grunt', 'Jötun Grunt')
        self.finds_at_least('Jotun Grunt', 'Jötun Grunt')

    def test_2_typos_in_the_same_word(self) -> None:
        self.finds_at_least('Womds of Rath', 'Winds of Rath')

    def test_2_typos_in_2_words(self) -> None:
        self.finds_at_least('Womds of Rogh', 'Winds of Rath')

    def best_match_without_prefix(self) -> None:
        self.best_match_is('Winds of Wrath', 'Winds of Rath')
        self.best_match_is('etherling', 'Aetherling')

    def test_stem_finds_variations(self) -> None:
        self.finds_at_least('Frantic Salvaging', 'Frantic Salvage')
        self.finds_at_least('Efficient Constructor', 'Efficient Construction')

    def test_exact_match(self) -> None:
        for card in ('Upheaval', 'Hellrider', 'Necropotence', 'Skullclamp', 'Mana Leak', 'Wasteland'):
            self.best_match_is(card, card)

    def test_prefix_match(self) -> None:
        for q, card in (('Jeskai Asc', 'Jeskai Ascendancy'), ('Uphe', 'Upheaval')):
            self.best_match_is(q, card)

    def test_whole_word(self) -> None:
        self.best_match_is('rofellos', 'Rofellos, Llanowar Emissary', "Rofellos's Gift")

    def test_normalized_beats_tokenized(self) -> None:
        self.best_match_is('Flash Food', 'Flash Flood')

    def test_10_cycles_are_returned(self) -> None:
        result = self.searcher.search('Guildgate')  # type: ignore
        assert len(result.fuzzy) == 10

    def test_dfc(self) -> None:
        self.best_match_is('Insectile Aberration', 'Delver of Secrets')

    def test_flip(self) -> None:
        self.best_match_is('Dokai, Weaver of Life', 'Budoka Gardener')

    def test_meld(self) -> None:
        self.best_match_is('Graf Rats', 'Graf Rats')
        self.best_match_is('Midnight Scavengers', 'Midnight Scavengers')
        self.best_match_in('Chittering Host', ['Graf Rats', 'Midnight Scavengers'])

    def test_aliases(self) -> None:
        self.best_match_is('Jens', 'Solemn Simulacrum')
        self.best_match_is('Sad Robot', 'Solemn Simulacrum')
        self.best_match_is('Sad Robon', 'Solemn Simulacrum')
        self.best_match_is('Drak Confidant', 'Dark Confidant')

def is_included(name: str, cards: list[str]) -> bool:
    return len([x for x in cards if x == name]) >= 1

def test_canonical_name_wins_alias_collision(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(WhooshConstants, 'index_dir', str(tmp_path))
    ix = create_in(tmp_path, whoosh_write.WhooshWriter().schema)
    writer = ix.writer()
    for card_id, canonical_name, name in [
        (1, 'Brainstorm', 'Brainstorm'),
        (2, 'Harmonized Trio', 'Harmonized Trio'),
        (2, 'Harmonized Trio', 'Brainstorm'),
        (3, 'Graf Rats', 'Chittering Host'),
        (4, 'Midnight Scavengers', 'Chittering Host'),
    ]:
        writer.update_document(
            id=card_id,
            canonical_name=canonical_name,
            name=name,
            name_tokenized=name,
            name_stemmed=name,
            name_normalized=name,
        )
    writer.commit()

    searcher = WhooshSearcher()

    result = searcher.search('Brainstorm')
    assert result.get_best_match() == 'Brainstorm'
    assert result.get_all_matches() == ['Brainstorm', 'Harmonized Trio']

    result = searcher.search('Chittering Host')
    assert result.get_best_match() == 'Midnight Scavengers'
    assert result.get_all_matches() == ['Midnight Scavengers', 'Graf Rats']

def test_flavor_name_is_searchable(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(WhooshConstants, 'index_dir', str(tmp_path))
    ix = create_in(tmp_path, whoosh_write.WhooshWriter().schema)
    card = Card({
        'id': 1,
        'name': "Greymond, Avacyn's Stalwart",
        'names': "Greymond, Avacyn's Stalwart",
        'flavor_names': 'Rick, Steadfast Leader',
        'layout': 'normal',
    })
    whoosh_write.update_index(ix, [card])

    searcher = WhooshSearcher()

    result = searcher.search('Rick, Steadfast Leader')
    assert result.get_best_match() == "Greymond, Avacyn's Stalwart"


def test_refresh_picks_up_an_index_rebuilt_by_another_process(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(WhooshConstants, 'index_dir', str(tmp_path))
    whoosh_write.WhooshWriter().rewrite_index([indexable_card(1, 'Ancestral Recall')])
    searcher = WhooshSearcher()
    # Search by prefix rather than by full name, because fuzzy matching reads the index directly and only prefix matching goes through the trie.
    assert searcher.search('Ancestral Re').get_best_match() == 'Ancestral Recall'
    assert searcher.search('Black Lo').get_best_match() is None

    whoosh_write.WhooshWriter().rewrite_index([indexable_card(1, 'Ancestral Recall'), indexable_card(2, 'Black Lotus')])
    assert searcher.search('Black Lo').get_best_match() is None, 'A rebuilt index is not visible until we refresh'

    searcher.refresh()

    assert searcher.search('Black Lo').get_best_match() == 'Black Lotus'
    assert searcher.search('Ancestral Re').get_best_match() == 'Ancestral Recall'

def indexable_card(card_id: int, name: str) -> Card:
    return Card({'id': card_id, 'name': name, 'names': name, 'flavor_names': None, 'layout': 'normal'})
