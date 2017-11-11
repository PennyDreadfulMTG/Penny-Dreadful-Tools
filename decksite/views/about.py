import random

from decksite.view import View
from magic import legality, oracle

FANCY_CARDS = legality.cards_legal_in_format(oracle.load_cards([
    'Mother of Runes',
    'Treasure Cruise',
    'Hymn to Tourach',
    'Hermit Druid',
    'Frantic Search',
    'Necropotence',
    'Tendrils of Agony',
    'Hypergenesis',
    "Mind's Desire",
    'Recurring Nightmare',
    'Worldgorger Dragon',
    'Astral Slide',
    'Dark Ritual',
    'Fact or Fiction',
    'High Tide',
    "Nevinyrral's Disk",
    'Lake of the Dead',
    ]), "Penny Dreadful")

# pylint: disable=no-self-use
class About(View):
    def subtitle(self):
        return 'About'

    def exciting_cards(self):
        random.shuffle(FANCY_CARDS)
        return FANCY_CARDS[:2]

    def third_exciting_card(self):
        return FANCY_CARDS[3].name
