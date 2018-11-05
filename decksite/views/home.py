from typing import List

from flask import url_for
from flask_babel import gettext

from decksite.view import View
from magic.models import Card, Deck
from shared.container import Container


# pylint: disable=no-self-use,too-many-instance-attributes
class Home(View):
    def __init__(self, news: List[Container], decks: List[Deck], cards: List[Card]) -> None:
        super().__init__()
        self.setup_news(news)
        self.setup_decks(decks)
        self.setup_cards(cards)

    def setup_news(self, news):
        self.news = news
        self.has_news = len(news) > 0
        self.all_news_url = url_for('news')

    def setup_decks(self, decks):
        min_decks = 20
        tournament_id, league_id, tournament_decks, league_decks, latest_decks = None, None, [], [], []
        for d in decks:
            if d.source_name == 'Gatherling' and tournament_id is None:
                tournament_id = d.competition_id
            if d.source_name == 'League' and league_id is None:
                league_id = d.competition_id
            if d.competition_id is not None and d.competition_id == tournament_id and d.finish <= 8:
                tournament_decks.append(d)
            if d.competition_id is not None and d.competition_id == league_id and d.wins >= 5 and (d.losses + d.draws) == 0 and len(league_decks) < 8:
                league_decks.append(d)
            if len(latest_decks) < min_decks:
                latest_decks.append(d)
            if len(tournament_decks) >= 8 and len(league_decks) >= 8 and len(latest_decks) >= min_decks:
                break
        self.deck_tables = []
        if league_decks:
            self.deck_tables.append(
                {
                    'title': gettext('Recent Top League Decks'),
                    'url': url_for('current_league'),
                    'link_text': gettext('Current League…'),
                    'decks': league_decks
                }
            )
        if tournament_decks:
            self.deck_tables.append(
                {
                    'title': gettext('Latest Tournament Top 8'),
                    'url': url_for('competitions', competition_id=tournament_id),
                    'link_text': gettext('View Tournament…'),
                    'decks': tournament_decks
                }
            )
        if latest_decks:
            self.deck_tables.append(
                {
                    'title': gettext('Latest Decks'),
                    'url': self.decks_url(),
                    'link_text': gettext('More Decks…'),
                    'decks': latest_decks
                }
            )
        self.decks = league_decks + tournament_decks + latest_decks
        self.show_active_runs_text = False

    def setup_cards(self, cards):
        cards = [c for c in cards if 'Basic Land' not in c.type]
        self.top_cards = cards[0:8]
        self.cards = self.top_cards # To get prepare_card treatment
        self.cards_url = url_for('cards')
