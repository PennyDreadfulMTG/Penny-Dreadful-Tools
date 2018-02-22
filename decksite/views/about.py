import random

import inflect
from flask import url_for

from decksite.view import View
from magic import legality, oracle, tournaments


# pylint: disable=no-self-use
class About(View):
    def __init__(self, src):
        if src == 'gp':
            self.show_gp_card = True
            self.gp_card_url = url_for('static', filename='images/gp_card.png')
        self.cards = exciting_cards()
        self.num_tournaments = inflect.engine().number_to_words(len(tournaments.all_series_info())).title()

    def subtitle(self):
        return 'About Penny Dreadful'

def exciting_cards():
    cards = fancy_cards()
    random.shuffle(cards)
    return cards[:3]

def fancy_cards():
    return legality.cards_legal_in_format(oracle.load_cards([
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
