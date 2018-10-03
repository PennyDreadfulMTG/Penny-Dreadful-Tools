import datetime

from flask import url_for

from decksite.view import View
from shared import dtutil


# pylint: disable=no-self-use,too-many-instance-attributes
class Home(View):
    def __init__(self, news, decks, cards) -> None:
        super().__init__()
        self.news = news
        self.has_news = len(news) > 0
        self.all_news_url = url_for('news')
        self.decks = decks
        min_decks = 20
        one_day_ago_ts = dtutil.now() - datetime.timedelta(days=1)
        display_decks = [d for d in self.decks if d.active_date > one_day_ago_ts]
        if len([d for d in display_decks if not d.is_in_current_run()]) < min_decks:
            one_week_ago_ts = dtutil.now() - datetime.timedelta(weeks=1)
            display_decks = [d for d in self.decks if d.active_date > one_week_ago_ts]
            if len([d for d in display_decks if not d.is_in_current_run()]) < min_decks:
                display_decks = decks
        self.decks = display_decks
        cards = [c for c in cards if 'Basic Land' not in c.type]
        self.top_cards = cards[0:5]
        self.cards = self.top_cards # To get prepare_card treatment
        self.cards_url = url_for('cards')
        self.show_active_runs_text = False
