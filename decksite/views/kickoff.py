import sys

from flask import url_for

from decksite.tournament import CompetitionFlag
from decksite.view import View
from magic import tournaments
from magic.tournaments import StageType
from shared import dtutil


class KickOff(View):
    def __init__(self) -> None:
        super().__init__()
        kick_off_date = tournaments.kick_off_date()
        if dtutil.now() > kick_off_date:
            self.date_info_safe = 'The Season Kick Off is on the second Saturday of the season'
        else:
            display_time = dtutil.display_date_with_date_and_year(kick_off_date)
            self.date_info_safe = f'The next Season Kick Off is on <time datetime="{kick_off_date}" data-format="dddd MMMM Do LT z">{display_time}</time>'
        self.faqs_url = url_for('faqs')
        self.cardhoarder_loan_url = 'https://cardhoarder.com/free-loan-program-faq'
        self.tournaments_url = url_for('tournaments')
        self.discord_url = url_for('discord')
        self.prizes = tournaments.kick_off_prizes()
        self.rounds_info = _rounds_info_for_template()

        # Set up the "Past Winners" table
        self.past_winners = {
            'competition_flag_id': CompetitionFlag.KICK_OFF.value,
            'season_id': 0,  # We want decks from all seasons, not the current season
            'show_season_icon': True,
            'hide_top8': True,
            'show_archetype': True,
        }

    def page_title(self) -> str:
        return 'The Season Kick Off'


def _rounds_info_for_template() -> list[dict[str, object]]:
    result = []
    for entry in tournaments.rounds_info():
        min_p = entry['min_players']
        max_p = entry['max_players']
        if max_p == sys.maxsize:
            player_range = f'{min_p}+'
        elif min_p == max_p:
            player_range = str(min_p)
        else:
            player_range = f'{min_p}–{max_p}'
        elim = entry[StageType.ELIMINATION_ROUNDS]
        top_n = 2 ** elim if elim > 0 else 0
        result.append({
            'player_range': player_range,
            'swiss_rounds': entry[StageType.SWISS_ROUNDS],
            'top_n': top_n if top_n > 0 else None,
        })
    return result
