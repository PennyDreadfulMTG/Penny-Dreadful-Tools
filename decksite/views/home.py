from flask import url_for
from flask_babel import gettext

from decksite.view import View
from magic import rotation, seasons, tournaments
from magic.models import Card, Deck
from shared import dtutil
from shared.container import Container


class Home(View):
    def __init__(self, news: list[Container], decks: list[Deck], cards: list[Card], matches_stats: dict[str, int]) -> None:
        super().__init__()
        self.setup_news(news)
        self.setup_decks(decks)
        self.setup_cards(cards)
        self.setup_rotation()
        self.setup_stats(matches_stats)
        self.setup_tournaments()
        self.pd500_url = url_for('pd500')
        pd500_date = tournaments.pd500_date()
        if pd500_date > dtutil.now():
            self.pd500_date = dtutil.display_date_with_date_and_year(pd500_date)
        self.kick_off_url = url_for('kickoff')
        kick_off_date = tournaments.kick_off_date()
        if kick_off_date > dtutil.now():
            self.kick_off_date = dtutil.display_date_with_date_and_year(kick_off_date)
        self.is_home_page = True

    def setup_news(self, news: list[Container]) -> None:
        self.news = news
        self.has_news = len(news) > 0

    def setup_decks(self, decks: list[Deck]) -> None:
        min_decks = 20
        tournament_id, league_id = None, None
        tournament_decks: list[Deck] = []
        league_decks: list[Deck] = []
        latest_decks: list[Deck] = []
        for d in decks:
            if d.source_name == 'Gatherling' and tournament_id is None:
                tournament_id = d.competition_id
            if d.source_name == 'League' and league_id is None:
                league_id = d.competition_id
            if d.competition_id is not None and d.competition_id == tournament_id and d.finish is not None and d.finish <= 8:
                tournament_decks.append(d)
            if d.competition_id is not None and d.competition_id == league_id and d.wins >= 5 and (d.losses + d.draws) == 0 and len(league_decks) < 8:
                league_decks.append(d)
            if len(latest_decks) < min_decks and not d.is_in_current_run():
                latest_decks.append(d)
            if len(tournament_decks) >= 8 and len(league_decks) >= 8 and len(latest_decks) >= min_decks:
                break
        self.deck_tables: list[dict] = []
        if league_decks:
            self.deck_tables.append(
                {
                    'title': gettext('Recent Top League Decks'),
                    'url': url_for('current_league'),
                    'link_text': gettext('Current League…'),
                    'decks': league_decks,
                    'hide_source': True,
                    'show_omw': True,
                    'hide_top8': True,
                },
            )
        if tournament_decks:
            self.deck_tables.append(
                {
                    'hide_source': True,
                    'title': gettext('Latest Tournament Top 8'),
                    'url': url_for('competition', competition_id=tournament_id),
                    'link_text': gettext('View Tournament…'),
                    'decks': tournament_decks,
                },
            )
        if latest_decks:
            self.deck_tables.append(
                {
                    'title': gettext('Latest Decks'),
                    'url': self.decks_url(),
                    'link_text': gettext('More Decks…'),
                    'decks': latest_decks,
                },
            )
        self.decks = league_decks + tournament_decks + latest_decks

    def setup_cards(self, cards: list[Card]) -> None:
        cards = [c for c in cards if 'Basic' not in c.type_line]
        self.top_cards = cards[0:8]
        self.has_top_cards = len(cards) > 0
        self.cards = self.top_cards  # To get prepare_card treatment
        self.cards_url = url_for('.cards')

    def setup_rotation(self) -> None:
        self.season_start_display = dtutil.display_date(seasons.last_rotation())
        self.season_end_display = dtutil.display_date(seasons.next_rotation())
        self.scryfall_url = 'https://scryfall.com/search?q=f%3Apd'
        self.legal_cards_url = 'http://pdmtgo.com/legal_cards.txt'
        self.in_rotation = rotation.in_rotation()
        self.rotation_msg = 'Rotation is in progress.'
        self.rotation_url = url_for('rotation')

    def setup_stats(self, matches_stats: dict[str, int]) -> None:
        # Human-friendly number formatting like "29,000".
        matches_stats_display = {}
        for k, v in matches_stats.items():
            matches_stats_display[k] = f'{v:,}' if v is not None else ''
        self.community_stats = [
            {
                'header': 'League and Tournament Matches Played',
                'stats': [
                    {
                        'text': f"{matches_stats_display['num_matches_today']} matches played today",
                    },
                    {
                        'text': f"{matches_stats_display['num_matches_this_week']} matches played this week",
                    },
                    {
                        'text': f"{matches_stats_display['num_matches_this_month']} matches played this month",
                    },
                    {
                        'text': f"{matches_stats_display['num_matches_this_season']} matches played this season",
                    },
                    {
                        'text': f"{matches_stats_display['num_matches_all_time']} matches played all time",
                    },
                ],
            },
        ]
