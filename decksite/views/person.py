import json
import math
from collections.abc import Sequence
from typing import Any

import titlecase
from flask import url_for

from decksite import prepare
from decksite.data import person as ps
from decksite.data.achievements import Achievement
from decksite.data.archetype import Archetype
from decksite.view import View
from magic import oracle, seasons

TRAILBLAZER_CARD_PREVIEW_SIZE = 12


class Person(View):
    def __init__(self, person: ps.Person, archetypes: list[Archetype], all_archetypes: list[Archetype], trailblazer_card_seasons: dict[str, int], unique_card_names: list[str], seasons_active: Sequence[int], season_id: int | None) -> None:
        super().__init__()
        self.all_archetypes = all_archetypes
        self.person = person
        self.people = [person]
        self.decks = person.decks
        self.has_decks = len(person.decks) > 0
        self.archetypes = archetypes
        self.hide_person = True
        self.show_seasons = True
        self.displayed_achievements = [{'title': a.title, 'detail': titlecase.titlecase(a.display(self.person))} for a in Achievement.all_achievements if a.display(self.person)]
        self.achievements_url = url_for('.achievements')
        self.person_achievements_url = url_for('.person_achievements', person_id=person.id)
        colors: dict[str, int] = {}
        for d in self.decks:
            for c in d.colors:
                colors[c] = colors.get(c, 0) + 1
        self.charts = [
            {
                'title': 'Colors Played',
                'type': 'bar',
                'labels': json.dumps(['White', 'Blue', 'Black', 'Red', 'Green', 'Colorless']),
                'series': json.dumps([colors.get('W'), colors.get('U'), colors.get('B'), colors.get('R'), colors.get('G'), colors.get('C')]),
                'options': json.dumps({
                    'animation': {
                        'duration': 0,  # Because this causes the canvas to grow sideways it makes the page jump around so even though it's nice let's skip it.
                    },
                    'indexAxis': 'y',
                    'scales': {
                        'x': {
                            'display': False,
                            'max': round(max(colors.values(), default=0) * 1.3),
                        },
                        'y': {
                            'grid': {
                                'display': False,
                            },
                        },
                    },
                }),
            },
        ]
        self.add_note_url = url_for('post_player_note')
        self.matches_url = url_for('.person_matches', person_id=person.id, season_id=None if season_id == seasons.current_season_num() else season_id)
        self.is_person_page = True
        self.trailblazer_cards = oracle.load_cards(trailblazer_card_seasons)
        for card in self.trailblazer_cards:
            first_played_season_id = trailblazer_card_seasons[card.name]
            card.first_played_season_id = first_played_season_id
            card.first_played_season_name = seasons.season_name(first_played_season_id)
            card.first_played_season_icon = prepare.season_icon_link(seasons.season_code(first_played_season_id))
        self.trailblazer_cards.sort(key=lambda card: (-card.first_played_season_id, card.name))
        for i, card in enumerate(self.trailblazer_cards):
            card.additional_trailblazer_card = i >= TRAILBLAZER_CARD_PREVIEW_SIZE
        self.num_trailblazer_cards = len(self.trailblazer_cards)
        self.has_additional_trailblazer_cards = self.num_trailblazer_cards > TRAILBLAZER_CARD_PREVIEW_SIZE
        self.has_trailblazer_cards = len(self.trailblazer_cards) > 0
        self.unique_cards = oracle.load_cards(unique_card_names)
        self.has_unique_cards = len(self.unique_cards) > 0
        self.cards = self.trailblazer_cards + self.unique_cards
        self.seasons_active: list[dict[str, object]] = []
        self.legal_seasons = list(seasons_active)
        self.setup_active_seasons(seasons_active)

    def __getattr__(self, attr: str) -> Any:
        return getattr(self.person, attr)

    def page_title(self) -> str:
        return self.person.name

    def setup_active_seasons(self, seasons_active: Sequence[int]) -> None:
        all_seasons = self.all_seasons()[1:]  # remove "all time" which is not shown here
        total_seasons = len(all_seasons)
        self.seasons_grid_columns = math.ceil(math.sqrt(total_seasons))  # Lay the seasons out in a square.
        for i, setcode in enumerate([s.get('code') for s in all_seasons]):
            season_id = total_seasons - i
            if season_id > seasons.current_season_num():
                continue
            active = season_id in seasons_active
            if setcode:
                class_name = f'ss-{setcode.lower()} season-icon' + ('' if active else ' inactive')
            else:
                class_name = ''
            season = {
                'season_id': season_id,
                'className': class_name,
                'url': url_for('seasons.person', person_id=self.person.id, season_id=season_id) if active else '',
            }
            self.seasons_active.append(season)
