import json
import time
import datetime
import calendar

from flask import url_for

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
        elif active_decks_by(self.mtgo_username.strip()):
            self.errors['mtgo_username'] = "You already have an active league run.  If you wish to retire your run early, private message '!retire' to PDBot"
        if len(self.name.strip()) == 0:
            self.errors['name'] = 'Deck Name is required'
        else:
            self.source = 'League'
            self.competition_id = db().value(active_competition_id_query())
            self.identifier = identifier(self)
            self.url = url_for('competitions', competition_id=self.competition_id)
        self.decklist = self.decklist.strip()
        if len(self.decklist) == 0:
            self.errors['decklist'] = 'Decklist is required'
        else:
            self.cards = None
            if self.decklist.startswith('<?xml'):
                try:
                    self.cards = decklist.parse_xml(self.decklist)
                except InvalidDataException as e:
                    self.errors['decklist'] = 'Unable to read .dek decklist. Try exporting from MTGO as Text and pasting the result.'.format(specific=str(e))
            else:
                try:
                    self.cards = decklist.parse(self.decklist)
                except InvalidDataException as e:
                    self.errors['decklist'] = '{specific}. Try exporting from MTGO as Text and pasting the result.'.format(specific=str(e))
            if self.cards is not None:
                try:
                    vivified = decklist.vivify(self.cards)
                    errors = {}
                    if 'Penny Dreadful' not in legality.legal_formats(vivified, None, errors):
                        self.errors['decklist'] = 'Deck is not legal in Penny Dreadful - {error}'.format(error=errors.get('Penny Dreadful'))
                except InvalidDataException as e:
                    self.errors['decklist'] = str(e)

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
            for match in deck.get_matches(self):
                if int(self.opponent) == match.opponent_deck_id:
                    self.errors['result'] = 'This match was reported as You {game_wins}–{game_losses} {opponent} {date}'.format(game_wins=match.game_wins, game_losses=match.game_losses, opponent=match.opponent, date=dtutil.display_date(match.date))
        if len(self.result) == 0:
            self.errors['result'] = 'Please select a result'
        else:
            self.entry_games, self.opponent_games = self.result.split('–')
        if self.entry == self.opponent:
            self.errors['opponent'] = "You can't play yourself"

def signup(form):
    form.mtgo_username = form.mtgo_username.strip()
    form.name = form.name.strip()
    return deck.add_deck(form)

def identifier(params):
    # Current timestamp is part of identifier here because we don't need to defend against dupes in league – it's fine to enter the same league with the same deck, later.
    return json.dumps([params['mtgo_username'], params['name'], params['competition_id'], str(int(time.time()))])

def deck_options(decks, v):
    return [{'text': '{person} - {deck}'.format(person=d.person, deck=d.name), 'value': d.id, 'selected': v == str(d.id), 'can_draw': d.can_draw} for d in decks]

def active_decks(additional_where='1 = 1'):
    where = "d.id IN (SELECT id FROM deck WHERE competition_id = ({active_competition_id_query})) AND (d.wins + d.losses + d.draws < 5) AND NOT d.retired AND ({additional_where})".format(active_competition_id_query=active_competition_id_query(), additional_where=additional_where)
    decks = deck.load_decks(where)
    return sorted(decks, key=lambda d: '{person}{deck}'.format(person=d.person.ljust(100), deck=d.name))

def active_decks_by(mtgo_username):
    return active_decks('p.mtgo_username = {mtgo_username}'.format(mtgo_username=sqlescape(mtgo_username)))

def report(form):
    db().begin()
    match_id = deck.insert_match(dtutil.now(), form.entry, form.entry_games, form.opponent, form.opponent_games)
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
    where = 'c.id = ({id_query})'.format(id_query=active_competition_id_query())
    leagues = competition.load_competitions(where)
    if len(leagues) == 0:
        start_date = datetime.datetime.combine(dtutil.now().date(), datetime.time(tzinfo=dtutil.WOTC_TZ))
        end_date = determine_end_of_league(start_date)
        name = "League {MM} {YYYY}".format(MM=calendar.month_name[end_date.month], YYYY=end_date.year)
        comp_id = competition.get_or_insert_competition(start_date, end_date, name, "League", url_for('league'))
        leagues = [competition.load_competition(comp_id)]
    return guarantee.exactly_one(leagues)

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

def load_latest_league_matches():
    competition_id = active_league().id
    where = 'dm.deck_id IN (SELECT id FROM deck WHERE competition_id = {competition_id})'.format(competition_id=competition_id)
    return load_matches(where)

def load_matches(where='1 = 1'):
    sql = """
        SELECT m.id, GROUP_CONCAT(dm.deck_id) AS deck_ids, GROUP_CONCAT(dm.games) AS games
        FROM `match` AS m
        INNER JOIN deck_match AS dm ON m.id = dm.match_id
        WHERE {where}
        GROUP BY m.id
    """.format(where=where)
    print(sql)
    matches = [Container(m) for m in db().execute(sql)]
    for m in matches:
        deck_ids = m.deck_ids.split(',')
        games = m.games.split(',')
        m.left_id = deck_ids[0]
        m.left_games = int(games[0])
        try:
            m.right_id = deck_ids[1]
            m.right_games = int(games[1])
        except IndexError:
            m.right_id = None
            m.right_games = 0
        if m.left_games > m.right_games:
            m.winner = m.left_id
            m.loser = m.right_id
        elif m.right_games > m.left_games:
            m.winner = m.right_id
            m.loser = m.left_id
        else:
            m.winner = None
            m.loser = None
    return matches

def delete_match(match_id):
    m = guarantee.exactly_one(load_matches('m.id = {match_id}'.format(match_id=sqlescape(match_id))))
    db().begin()
    sql = 'DELETE FROM deck_match WHERE match_id = ?'
    db().execute(sql, [m.id])
    sql = 'DELETE FROM `match` WHERE id = ?'
    db().execute(sql, [m.id])
    if m.winner:
        sql = 'UPDATE deck SET wins = wins - 1 WHERE id = ?'
        db().execute(sql, [m.winner])
        sql = 'UPDATE deck SET losses = losses - 1 WHERE id = ?'
        db().execute(sql, [m.loser])
    else:
        sql = 'UPDATE deck SET draws = draws - 1 WHERE id IN (?, ?)'
        db().execute(sql, [m.left_id, m.right_id])
    db().commit()
