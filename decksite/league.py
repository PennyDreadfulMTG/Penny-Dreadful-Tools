import json
import datetime
import calendar

from munch import Munch

from magic import legality, rotation
from shared import dtutil
from shared.pd_exception import InvalidDataException

from decksite.data import competition, deck, guarantee
from decksite.database import db
from decksite.scrapers import decklist

class Form(Munch):
    def __init__(self, form):
        super().__init__()
        form = form.to_dict()
        self.update(form)
        self.errors = {}

    def validate(self):
        self.do_validation()
        return len(self.errors) == 0

# pylint: disable=attribute-defined-outside-init
class SignUpForm(Form):
    def do_validation(self):
        if len(self.mtgo_username) == 0:
            self.errors['mtgo_username'] = "MTGO Username is required"
        if len(self.name) == 0:
            self.errors['name'] = 'Deck Name is required'
        else:
            self.source = 'League'
            self.competition_id = db().value(active_competition_id_query())
            self.identifier = identifier(self)
            self.url = 'http://pennydreadfulmagic.com/competitions/{competition_id}/'.format(competition_id=self.competition_id)
            if deck.get_deck_id(self.source, self.identifier):
                self.errors['name'] = 'You have already entered the league this season with a deck called {name}'.format(name=self.name)
        if len(self.decklist) == 0:
            self.errors['decklist'] = 'Decklist is required'
        else:
            try:
                self.cards = decklist.parse(self.decklist)
                vivified = decklist.vivify(self.cards)
                if 'Penny Dreadful' not in legality.legal_formats(vivified):
                    self.errors['decklist'] = 'Deck is not legal in Penny Dreadful'
            except InvalidDataException as e:
                self.errors['decklist'] = '{specific}. Try exporting from MTGO as Text and pasting the result.'.format(specific=str(e))

class ReportForm(Form):
    def __init__(self, form, deck_id=None):
        super().__init__(form)
        decks = active_decks()
        print(self.get('entry', deck_id))
        self.entry_options = deck_options(decks, self.get('entry', deck_id))
        self.opponent_options = deck_options(decks, self.get('opponent', None))
        self.result_options = [
            {'text': 'Win 2–0', 'value': '2–0', 'selected': self.get('result', None) == '2–0'},
            {'text': 'Win 2–1', 'value': '2–1', 'selected': self.get('result', None) == '2–1'},
            {'text': 'Lose 1–2', 'value': '1–2', 'selected': self.get('result', None) == '1–2'},
            {'text': 'Lose 0–2', 'value': '0–2', 'selected': self.get('result', None) == '0–2'},
        ]

    def do_validation(self):
        if len(self.entry) == 0:
            self.errors['entry'] = 'Please select your deck'
        if len(self.opponent) == 0:
            self.errors['opponent'] = "Please select your opponent's deck"
        if len(self.result) == 0:
            self.errors['result'] = 'Please select a result'
        else:
            self.entry_games, self.opponent_games = self.result.split('–')
        if self.entry == self.opponent:
            self.errors['opponent'] = "You can't play yourself"
        match = get_match(self)
        if match:
            self.errors['result'] = 'This match was reported as {p1} {p1games}–{p2games} {p2} {date}'.format(p1=match['p1name'], p1games=match['p1games'], p2games=match['p2games'], p2=match['p2name'], date=dtutil.display_date(match['date']))

def signup(form):
    return deck.add_deck(form)

def identifier(params):
    return json.dumps([params['mtgo_username'], params['name'], params['competition_id']])

def deck_options(decks, v):
    return [{'text': '{person} - {deck}'.format(person=d.person, deck=d.name), 'value': d.id, 'selected': v == str(d.id), 'can_draw': d.can_draw} for d in decks]

def active_decks():
    decks = deck.load_decks("d.id IN (SELECT id FROM deck WHERE competition_id = ({active_competition_id_query})) AND wins + losses < 5".format(active_competition_id_query=active_competition_id_query()))
    return sorted(decks, key=lambda d: '{person}{deck}'.format(person=d.person.ljust(100), deck=d.name))

def report(form):
    db().execute('BEGIN TRANSACTION')
    match_id = insert_match(form)
    winner, loser = winner_and_loser(form)
    if winner:
        db().execute('UPDATE deck SET wins = wins + 1 WHERE id = ?', [winner])
        db().execute('UPDATE deck SET losses = losses + 1 WHERE id = ?', [loser])
    else:
        db().execute('UPDATE deck SET draws = draws + 1 WHERE id = ? OR id = ?', [form.entry, form.opponent])
    db().execute('COMMIT')
    return match_id

def winner_and_loser(params):
    if params.entry_games > params.opponent_games:
        return (params.entry, params.opponent)
    elif params.opponent_games > params.entry_games:
        return (params.opponent, params.entry)
    return (None, None)

def active_competition_id_query():
    return "SELECT id FROM competition WHERE start_date < {now} AND end_date > {now} AND competition_type_id = (SELECT id FROM competition_type WHERE name = 'League')".format(now=dtutil.dt2ts(dtutil.now()))

def active_league():
    where_clause = 'c.id = ({id_query})'.format(id_query=active_competition_id_query())
    leagues = competition.load_competitions(where_clause)
    if len(leagues) == 0:
        start_date = datetime.datetime.combine(dtutil.now().date(), datetime.time(tzinfo=datetime.timezone.utc))
        end_date = determine_end_of_league(start_date)
        name = "League {MM} {YYYY}".format(MM=calendar.month_name[end_date.month], YYYY=end_date.year)
        comp_id = competition.get_or_insert_competition(start_date, end_date, name, "League", 'http://pennydreadfulmagic.com/league/')
        leagues = [competition.load_competition(comp_id)]
    return guarantee.exactly_one(leagues)

def insert_match(params):
    match_id = db().insert("INSERT INTO match (`date`) VALUES (strftime('%s', 'now'))")
    sql = 'INSERT INTO deck_match (deck_id, match_id, games) VALUES (?, ?, ?)'
    db().execute(sql, [params.entry, match_id, params.entry_games])
    db().execute(sql, [params.opponent, match_id, params.opponent_games])
    return match_id

def get_match(params):
    sql = """
        SELECT m.`date`, m.id, dm1.games AS p1games, dm2.games AS p2games, d1.name AS p1name, d2.name AS p2name
        FROM match AS m
        INNER JOIN deck_match AS dm1 ON m.id = dm1.match_id AND dm1.deck_id = ?
        INNER JOIN deck_match AS dm2 ON m.id = dm2.match_id AND dm2.deck_id = ?
        INNER JOIN deck AS d1 ON dm1.deck_id = d1.id
        INNER JOIN deck AS d2 ON dm2.deck_id = d2.id
    """
    rs = db().execute(sql, [params.entry, params.opponent])
    if len(rs) == 0:
        return None
    elif len(rs) == 1:
        rs[0]['date'] = dtutil.ts2dt(rs[0]['date'])
        return rs[0]
    else:
        raise InvalidDataException('Got more than one match from `{params}`'.format(params=params))

def determine_end_of_league(start_date):
    if start_date.day < 15:
        month = start_date.month + 1
    else:
        month = start_date.month + 2
    if month > 12:
        end_date = datetime.datetime(start_date.year + 1, month - 12, 1, tzinfo=datetime.timezone.utc)
    else:
        end_date = datetime.datetime(start_date.year, month, 1, tzinfo=datetime.timezone.utc)
    if end_date > rotation.next_rotation():
        end_date = rotation.next_rotation()
    return end_date - datetime.timedelta(seconds=1)
