import unittest

from shared.whoosh_search import WhooshSearcher

class WhooshSearchTest(unittest.TestCase):
    def setUp(self):
        self.searcher = WhooshSearcher()

    def finds_at_least(self, query, card_name):
        cards = self.searcher.search(query)
        assert len(cards) >= 1
        assert is_included(card_name, cards)

    def test_assorted_typos(self):
        self.finds_at_least('Define Bloodlord', 'Defiant Bloodlord')
        self.finds_at_least('Ashenmoor Gourger', 'Ashenmoor Gouger')
        self.finds_at_least('Ashenmmor', 'Ashenmoor Gouger')
        self.finds_at_least('narcomeba', 'Narcomoeba')
        self.finds_at_least('devler of secrets', 'Delver of Secrets')

    def test_split_cards(self):
        self.finds_at_least('Far/Away', 'Far // Away')
        self.finds_at_least('Ready / Willing', 'Ready // Willing')
        self.finds_at_least('Fire // Ice', 'Fire // Ice')

    def test_name_included_in_others(self):
        self.finds_at_least('Upheaval', 'Upheaval')
        self.finds_at_least('Upheaval', 'Volcanic Upheaval')

    def test_special_chars(self):
        self.finds_at_least('Jötun Grunt', 'Jötun Grunt')
        self.finds_at_least('Jotun Grunt', 'Jötun Grunt')

    def test_2_typos_in_the_same_word(self):
        self.finds_at_least('Womds of Rath', 'Winds of Rath')

    def test_2_typos_in_2_words(self):
        self.finds_at_least('Womds of Rogh', 'Winds of Rath')

    def test_stem_finds_variations(self):
        self.finds_at_least('Frantic Salvaging', 'Frantic Salvage')
        self.finds_at_least('Efficient Constructor', 'Efficient Construction')

    def test_exact_match_is_relevant(self):
        for card in ('Upheaval', 'Hellrider', 'Necropotence', 'Skullclamp', 'Mana Leak'):
            cards = self.searcher.search(card)
            assert len(cards) > 1
            assert is_included(card, cards)
            assert cards[0].get('relevant')



def is_included(name, cards):
    return len([x for x in cards if x.name == name]) >= 1
