import copy
import json
from typing import Any, TypedDict

from flask import url_for

from decksite import prepare
from decksite.data import archetype as archs
from decksite.deck_type import DeckType
from decksite.view import View
from shared.container import Container
from shared.pd_exception import DoesNotExistException


class Matchups(TypedDict):
    is_matchups: bool
    archetypes: list[archs.Archetype]

class Archetype(View):
    def __init__(self, archetype: archs.Archetype, archetypes: list[archs.Archetype], matchups: list[Container], seasons_active: list[int], meta_share: list[float], tournament_only: bool = False) -> None:
        super().__init__()
        if not archetype:
            raise DoesNotExistException('No archetype supplied to view.')
        self.archetype = archetype
        self.archetypes = []
        for a in archetypes:
            if a.id == archetype.id:
                self.archetype = a
                self.archetypes = list(a.ancestors) + [a] + list(a.descendants)
                break
        self.matchups: Matchups = {
            'is_matchups': True,
            'archetypes': copy.deepcopy(archetypes),  # Take a copy of the archetypes, so we can update their stats without interfering with the other section.
        }
        matchups_by_id = {m.id: m for m in matchups}
        for m in self.matchups['archetypes']:
            m.update(matchups_by_id.get(m.id, {'hide_archetype': True}))
        for m in self.matchups['archetypes']:
            prepare.prepare_archetype(m, self.matchups['archetypes'], None, tournament_only, self.season_id())
        self.tournament_only = self.hide_source = tournament_only
        self.show_seasons = True
        self.legal_seasons = seasons_active
        self.show_tournament_toggle = True
        self.toggle_results_url = url_for('.archetype', archetype_id=self.archetype.id, deck_type=None if tournament_only else DeckType.TOURNAMENT.value)
        self.show_archetype_tree = len(self.archetypes) > 0
        self.has_cards = True
        if self.season_id() == 0:
            self.history_chart = {
                'type': 'bar',
                'labels': json.dumps(list(range(1, len(meta_share) + 1))),
                'series': json.dumps(meta_share),
                'options': json.dumps({
                    'pd': {
                        'title': {
                            'style': 'season',
                        },
                    },
                    'indexAxis': 'x',
                    'plugins': {
                        'datalabels': {
                            'display': False,
                        },
                        'tooltip': {
                            'enabled': True,
                        },
                    },
                    'scales': {
                        'x': {
                            'grid': {
                                'display': False,
                            },
                        },
                        'y': {
                            'ticks': {
                                'format': {
                                    'style': 'percent',
                                },
                            },
                        },
                    },
                }),
            }

    def og_title(self) -> str:
        return self.archetype.name

    def og_url(self) -> str:
        return url_for('.archetype', archetype_id=self.archetype.id, _external=True)

    def og_description(self) -> str:
        return f'Penny Dreadful {self.archetype.name} archetype'

    def __getattr__(self, attr: str) -> Any:
        return getattr(self.archetype, attr)

    def page_title(self) -> str:
        return self.archetype.name
