import unittest

from shared.whoosh_search import WhooshSearcher


# pylint: disable=unused-variable
class WhooshSearchTest(unittest.TestCase):
    def setUp(self):
        self.searcher = WhooshSearcher()

    def best_match_is(self, query, expected_best_match, *additional_matches):
        result = self.searcher.search(query)
        assert result.get_best_match() == expected_best_match
        all_matches = result.get_all_matches()
        for r in additional_matches:
            assert is_included(r, all_matches)

    def finds_at_least(self, query, card_name):
        result = self.searcher.search(query)
        cards = result.get_all_matches()
        cards = [c for c in cards if c is not None]
        assert len(cards) >= 1
        assert is_included(card_name, cards)

    # pylint: disable=line-too-long
    def aliases_are_exact(self):
        for q, card in (('bob', 'Dark Confidant'), ('jens', 'Solemn Simulacrum'), ('sad robot', 'Solemn Simulacrum'), ('mom', 'Mother of Runes'), ('tim', 'Prodigal Sorcerer'), ('gary', 'Gray Merchant of Asphodel'), ('finkel', 'Shadowmage Infiltrator'), ('kai', 'Voidmage Prodigy'), ('tiago', 'Snapcaster Mage'), ('pikula', 'Meddling Mage'), ('durdle turtle', 'Meandering Towershell'), ('volvary', 'Aura Barbs'), ('bolt', 'Lightning Bolt'), ('ftk', 'Flametongue Kavu'), ('fow', 'Force of Will'), ('looter scooter', 'Smuggler\'s Copter'), ('nerd ape', 'Inventor\'s Apprentice')):
            result = self.searcher.search(q)
            assert result.get_best_match() == card


    def test_assorted_typos(self):
        self.finds_at_least('Define Bloodlord', 'Defiant Bloodlord')
        self.finds_at_least('Ashenmoor Gourger', 'Ashenmoor Gouger')
        self.finds_at_least('Ashenmmor', 'Ashenmoor Gouger')
        self.finds_at_least('narcomeba', 'Narcomoeba')
        self.best_match_is('Uphaeval', 'Upheaval')
        self.finds_at_least('devler of secrets', 'Delver of Secrets')

    def test_split_cards(self):
        self.finds_at_least('Far/Away', 'Far // Away')
        self.finds_at_least('Ready / Willing', 'Ready // Willing')
        self.finds_at_least('Fire // Ice', 'Fire // Ice')

    def test_special_chars(self):
        self.finds_at_least('Jötun Grunt', 'Jötun Grunt')
        self.finds_at_least('Jotun Grunt', 'Jötun Grunt')

    def test_2_typos_in_the_same_word(self):
        self.finds_at_least('Womds of Rath', 'Winds of Rath')

    def test_2_typos_in_2_words(self):
        self.finds_at_least('Womds of Rogh', 'Winds of Rath')

    def best_match_without_prefix(self):
        self.best_match_is('Winds of Wrath', 'Winds of Rath')
        self.best_match_is('etherling', 'Aetherling')

    def test_stem_finds_variations(self):
        self.finds_at_least('Frantic Salvaging', 'Frantic Salvage')
        self.finds_at_least('Efficient Constructor', 'Efficient Construction')

    def test_exact_match(self):
        for card in ('Upheaval', 'Hellrider', 'Necropotence', 'Skullclamp', 'Mana Leak'):
            self.best_match_is(card, card)

    def test_prefix_match(self):
        for q, card in (('Jeskai Asc', 'Jeskai Ascendancy'), ('Uphe', 'Upheaval')):
            self.best_match_is(q, card)

    def test_whole_word(self):
        self.best_match_is("rofellos", "Rofellos, Llanowar Emissary", "Rofellos's Gift")

    def test_normalized_beats_tokenized(self):
        self.best_match_is("Flash Food", "Flash Flood")

def is_included(name, cards):
    return len([x for x in cards if x == name]) >= 1
