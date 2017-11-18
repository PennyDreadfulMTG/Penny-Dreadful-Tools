import random

from flask import url_for

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
    'Braids, Cabal Minion',
    'Channel',
    'Chain Lightning',
    'Brain Freeze',
    'Dragonstorm',
    'Day of Judgment',
    'Cruel Ultimatum',
    'Rofellos, Llanowar Emissary',
    'Mana Leak',
    'Burning of Xinye',
    'Psychatog',
    'Smokestack',
    'Llanowar Elves',
    'Isamaru, Hound of Konda',
    'Animate Dead'
]), 'Penny Dreadful')

# pylint: disable=no-self-use
class About(View):
    def __init__(self,  src):
        if src == 'gp':
            self.show_gp_card = True
            self.gp_card_url = url_for('static', filename='images/gp_card.png')

    def subtitle(self):
        return 'About Penny Dreadful'

    def exciting_cards(self):
        random.shuffle(FANCY_CARDS)
        return FANCY_CARDS[:3]
