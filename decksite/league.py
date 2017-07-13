import json
import time
import datetime
import calendar

from magic import legality, rotation
from shared import dtutil
from shared.container import Container
from shared.database import sqlescape
from shared.pd_exception import InvalidDataException

from decksite.data import competition, deck, guarantee
from decksite.database import db
from decksite.scrapers import decklist

class Form(Container):
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
        elif active_decks_by(self.mtgo_username):
            self.errors['mtgo_username'] = "You already have an active league run.  If you wish to retire your run early, private message '!retire' to PDBot"
        if len(self.name) == 0:
            self.errors['name'] = 'Deck Name is required'
        else:
            self.source = 'League'
            self.competition_id = db().value(active_competition_id_query())
            self.identifier = identifier(self)
            self.url = 'http://pennydreadfulmagic.com/competitions/{competition_id}/'.format(competition_id=self.competition_id)
        self.decklist = self.decklist.strip()
        if len(self.decklist) == 0:
            self.errors['decklist'] = 'Decklist is required'
        else:
            try:
                self.cards = decklist.parse(self.decklist)
                vivified = decklist.vivify(self.cards)
                errors = {}
                if 'Penny Dreadful' not in legality.legal_formats(vivified, None, errors):
                    self.errors['decklist'] = 'Deck is not legal in Penny Dreadful - {error}'.format(error=errors.get('Penny Dreadful'))
            except InvalidDataException as e:
                self.errors['decklist'] = '{specific}. Try exporting from MTGO as Text and pasting the result.'.format(specific=str(e))

class ReportForm(Form):
    def __init__(self, form, deck_id=None):
        super().__init__(form)
        decks = active_decks()
        self.entry_options = deck_options(decks, self.get('entry', deck_id))
        self.opponent_options = deck_options(decks, self.get('opponent', None))
        self.result_options = [
            {'text': 'Win 2–0', 'value': '2–0', 'selected': self.get('result', None) == '2–0'},
            {'text': 'Win 2–1', 'value': '2–1', 'selected': self.get('result', None) == '2–1'},
            {'text': 'Lose 1–2', 'value': '1–2', 'selected': self.get('result', None) == '1–2'},
            {'text': 'Lose 0–2', 'value': '0–2', 'selected': self.get('result', None) == '0–2'},
        ]

    def do_validation(self):
        self.id = self.entry
        if len(self.entry) == 0:
            self.errors['entry'] = 'Please select your deck'
        if len(self.opponent) == 0:
            self.errors['opponent'] = "Please select your opponent's deck"
        else:
            for match in get_matches(self):
                if int(self.opponent) == match.opponent_deck_id:
                    self.errors['result'] = 'This match was reported as You {game_wins}–{game_losses} {opponent} {date}'.format(game_wins=match.game_wins, game_losses=match.game_losses, opponent=match.opponent, date=dtutil.display_date(match.date))
        if len(self.result) == 0:
            self.errors['result'] = 'Please select a result'
        else:
            self.entry_games, self.opponent_games = self.result.split('–')
        if self.entry == self.opponent:
            self.errors['opponent'] = "You can't play yourself"

def signup(form):
    return deck.add_deck(form)

def identifier(params):
    # Current timestamp is part of identifier here because we don't need to defend against dupes in league – it's fine to enter the same league with the same deck, later.
    return json.dumps([params['mtgo_username'], params['name'], params['competition_id'], str(int(time.time()))])

def deck_options(decks, v):
    return [{'text': '{person} - {deck}'.format(person=d.person, deck=d.name), 'value': d.id, 'selected': v == str(d.id), 'can_draw': d.can_draw} for d in decks]

def active_decks(additional_where='1 = 1'):
    where_clause = "d.id IN (SELECT id FROM deck WHERE competition_id = ({active_competition_id_query})) AND (d.wins + d.losses + d.draws < 5) AND NOT d.retired AND ({additional_where})".format(active_competition_id_query=active_competition_id_query(), additional_where=additional_where)
    decks = deck.load_decks(where_clause)
    return sorted(decks, key=lambda d: '{person}{deck}'.format(person=d.person.ljust(100), deck=d.name))

def active_decks_by(mtgo_username):
    return active_decks('p.mtgo_username = {mtgo_username}'.format(mtgo_username=sqlescape(mtgo_username)))

def report(form):
    db().begin()
    match_id = insert_match(form)
    winner, loser = winner_and_loser(form)
    if winner:
        db().execute('UPDATE deck SET wins = (SELECT COUNT(*) FROM decksite.deck_match WHERE `deck_id` = %s AND `games` = 2) WHERE `id` = %s', [winner, winner])
        db().execute('UPDATE deck SET losses = (SELECT COUNT(*) FROM decksite.deck_match WHERE `deck_id` = %s AND `games` < 2) WHERE `id` = %s', [loser, loser])
    else:
        db().execute('UPDATE deck SET draws = draws + 1 WHERE id = %s OR id = %s', [form.entry, form.opponent])
    db().commit()
    return match_id

def winner_and_loser(params):
    if params.entry_games > params.opponent_games:
        return (params.entry, params.opponent)
    elif params.opponent_games > params.entry_games:
        return (params.opponent, params.entry)
    return (None, None)

def active_competition_id_query():
    return "SELECT id FROM competition WHERE start_date < {now} AND end_date > {now} AND competition_type_id = (SELECT id FROM competition_type WHERE name = 'League')".format(now=dtutil.dt2ts(dtutil.now()))

def get_active_competition_id():
    return db().execute(active_competition_id_query())[0]['id']

def active_league():
    where_clause = 'c.id = ({id_query})'.format(id_query=active_competition_id_query())
    leagues = competition.load_competitions(where_clause)
    if len(leagues) == 0:
        start_date = datetime.datetime.combine(dtutil.now().date(), datetime.time(tzinfo=dtutil.WOTC_TZ))
        end_date = determine_end_of_league(start_date)
        name = "League {MM} {YYYY}".format(MM=calendar.month_name[end_date.month], YYYY=end_date.year)
        comp_id = competition.get_or_insert_competition(start_date, end_date, name, "League", 'http://pennydreadfulmagic.com/league/')
        leagues = [competition.load_competition(comp_id)]
    return guarantee.exactly_one(leagues)

def insert_match(params):
    match_id = db().insert("INSERT INTO `match` (`date`) VALUES (%s)", [time.time()])
    sql = 'INSERT INTO deck_match (deck_id, match_id, games) VALUES (%s, %s, %s)'
    db().execute(sql, [params.entry, match_id, params.entry_games])
    db().execute(sql, [params.opponent, match_id, params.opponent_games])
    return match_id

def get_matches(d, load_decks=False):
    sql = """
        SELECT m.`date`, m.id, dm2.deck_id AS opponent_deck_id, dm1.games AS game_wins, dm2.games AS game_losses, d2.name AS opponent_deck_name, p.mtgo_username AS opponent
        FROM `match` AS m
        INNER JOIN deck_match AS dm1 ON m.id = dm1.match_id AND dm1.deck_id = %s
        INNER JOIN deck_match AS dm2 ON m.id = dm2.match_id AND dm2.deck_id <> %s
        INNER JOIN deck AS d1 ON dm1.deck_id = d1.id
        INNER JOIN deck AS d2 ON dm2.deck_id = d2.id
        INNER JOIN person AS p ON p.id = d2.person_id
    """
    matches = [Container(m) for m in db().execute(sql, [d.id, d.id])]
    if load_decks and len(matches) > 0:
        decks = deck.load_decks('d.id IN ({ids})'.format(ids=', '.join([sqlescape(str(m.opponent_deck_id)) for m in matches])))
        decks_by_id = {d.id: d for d in decks}
    for m in matches:
        m.date = dtutil.ts2dt(m.date)
        if load_decks:
            m.opponent_deck = decks_by_id[m.opponent_deck_id]
    return matches

def determine_end_of_league(start_date):
    if start_date.day < 15:
        month = start_date.month + 1
    else:
        month = start_date.month + 2
    if month > 12:
        end_date = datetime.datetime(start_date.year + 1, month - 12, 1, tzinfo=dtutil.WOTC_TZ)
    else:
        end_date = datetime.datetime(start_date.year, month, 1, tzinfo=dtutil.WOTC_TZ)
    if end_date > rotation.next_rotation():
        end_date = rotation.next_rotation()
    return end_date - datetime.timedelta(seconds=1)

def retire_deck(d):
    if d.wins == 0 and d.losses == 0 and d.draws == 0:
        sql = 'DELETE FROM deck WHERE id = %s'
    else:
        sql = 'UPDATE `deck` SET `retired` = 1 WHERE id = %s'
    db().execute(sql, [d.id])
