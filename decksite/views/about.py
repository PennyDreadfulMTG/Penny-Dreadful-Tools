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
        self.num_cards_thousands = str(len(oracle.legal_cards()) // 1000) + ',000'
        self.exciting_cards_safe = ' • '.join(f'<b class="card">{c.name}</b>' for c in exciting_cards())
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
    # The last time I updated this I eyeballed
    #     SELECT name, playability FROM _playability ORDER BY playability DESC LIMIT 200;
    # and picked out the ones that sounded marketable to a non-PD player.
    # And I left a few in from old list (at the bottom) that weren't in that 200 but are cool.
    return legality.cards_legal_in_format(oracle.load_cards([
        'Ponder',
        'Path to Exile',
        'Counterspell',
        'Brainstorm',
        'Gitaxian Probe',
        'Hymn to Tourach',
        'Treasure Cruise',
        'Dark Confidant',
        'Chain Lightning',
        'Dig Through Time',
        "Arcum's Astrolabe",
        'Ramunap Ruins',
        'Field of the Dead',
        'Demonic Consultation',
        'Dark Ritual',
        'Mana Leak',
        'Memory Lapse',
        'Necropotence',
        'Faithless Looting',
        'Abrupt Decay',
        'Thalia, Guardian of Thraben',
        'Channel',
        'Wrath of God',
        "Smuggler's Copter",
        'Birds of Paradise',
        'Fact or Fiction',
        'Simian Spirit Guide',
        'Mystic Sanctuary',
        'Frantic Search',
        'Monastery Swiftspear',
        'Ancestral Vision',
        'Vindicate',
        'Kiki-Jiki, Mirror Breaker',
        'Reanimate',
        'Gush',
        'Lake of the Dead',
        'Mother of Runes',
        'Sylvan Library',
        'High Tide',
        "Council's Judgment",
        'Ugin, the Spirit Dragon',
        'Delver of Secrets',
        'Lurrus of the Dream-Den',
        'Sword of Fire and Ice',
        'Animate Dead',
        'Living Death',
        'Bloodbraid Elf',
        'Cloudpost',
        'Lotus Bloom',
        'Cranial Plating',
        'Iona, Shield of Emeria',
        'Rofellos, Llanowar Emissary',
        'Expressive Iteration',
        'Scavenging Ooze',
        'Meddling Mage',
        'Ephemerate',
        "Mind's Desire",
        'Shardless Agent',
        'Lingering Souls',
        'Yorion, Sky Nomad',

        'Mother of Runes',
        'Hermit Druid',
        'Tendrils of Agony',
        'Hypergenesis',
        'Recurring Nightmare',
        'Worldgorger Dragon',
        'Astral Slide',
        'Brain Freeze',
        'Dragonstorm',
        'Cruel Ultimatum',
        'Smokestack',
        'Invigorate',
    ]), seasons.current_season_name())
