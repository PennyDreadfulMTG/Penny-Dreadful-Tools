import datetime

from flask import url_for

from decksite.view import View
from shared import dtutil


# pylint: disable=no-self-use,too-many-instance-attributes
class Home(View):
    def __init__(self, news, decks, cards):
        self.news = news
        self.has_news = len(news) > 0
        self.all_news_url = url_for('news')
        self.decks = decks
        min_decks = 10
        one_day_ago_ts = dtutil.now() - datetime.timedelta(days=1)
        week_decks = [d for d in self.decks if d.created_date > one_day_ago_ts]
        display_decks = week_decks
        if len(display_decks) < min_decks:
            one_week_ago_ts = dtutil.now() - datetime.timedelta(weeks=1)
            display_decks = [d for d in self.decks if d.created_date > one_week_ago_ts]
            if len(display_decks) < min_decks:
                display_decks = decks
        self.decks = display_decks
        cards = [c for c in cards if 'Basic Land' not in c.type]
        week_cards = sorted(cards, key=lambda x: x['week_num_decks'], reverse=True)
        for c in cards:
            c.movement = c.week_num_decks / (max(c.season_num_decks, 1) + len(week_decks))
        self.top_cards = cards[0:5]
        self.week_cards = week_cards[0:5]
        rising_cards = sorted(cards, key=lambda x: x.movement, reverse=True)
        self.rising_cards = rising_cards[0:5]
        self.cards = self.top_cards + self.week_cards + self.rising_cards
        self.decks_url = url_for('decks')
        self.cards_url = url_for('cards')

    def subtitle(self):
        return None
