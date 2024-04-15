import random

from flask import url_for

from decksite.view import View
from magic import legality, oracle, seasons
from magic.models import Card, Deck


class About(View):
    def __init__(self, src: str | None, last_season_tournament_winners: list[Deck]) -> None:
        super().__init__()
        if src == 'gp':
            self.show_gp_card = True
            self.gp_card_url = url_for('static', filename='images/gp_card.png')
        self.cards = exciting_cards()
        self.num_tournaments_title_case = self.num_tournaments().title()
        s = ' and '.join({d.archetype_name for d in last_season_tournament_winners})
        self.tournament_winning_archetypes_s = s.replace(' and', ',', s.count(' and') - 1)

    def page_title(self) -> str:
        return 'About Penny Dreadful'

def exciting_cards() -> list[Card]:
    cards = fancy_cards()
    random.shuffle(cards)
    return cards[:3]

def fancy_cards() -> list[Card]:
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
        'Mana Leak',
        'Burning of Xinye',
        'Psychatog',
        'Smokestack',
        'Llanowar Elves',
        'Animate Dead',
        'Demonic Consultation',
        'Living Death',
        'Edric, Spymaster of Trest',
        'Invigorate',
    ]), seasons.current_season_name())
