from typing import Any

from flask import url_for

from decksite.view import View


class RotationChanges(View):
    def __init__(self) -> None:
        super().__init__()
        self.sections: list[dict[str, Any]] = []
        self.has_cards = True
        self.show_seasons = True
        self.new_cards_deck_url = url_for('rotation_changes_files', changes_type='new')
        self.rotated_out_cards_deck_url = url_for('rotation_changes_files', changes_type='out')
        self.all_legal = True
        season_id = self.season_id()
        previous_season_id = season_id - 1 if season_id > 1 else None
        new_query = f'f:pd{season_id}'
        if previous_season_id:
            new_query += f' -f:pd{previous_season_id}'
            out_query = f'f:pd{previous_season_id} -f:pd{season_id}'
            self.rotated_out = {'base_query': out_query, 'season_id': previous_season_id}
        self.new_this_season = {'base_query': new_query, 'season_id': season_id}

    def page_title(self) -> str:
        return 'Rotation Changes'
