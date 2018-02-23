import calendar
import datetime
import json
import time

from flask import url_for

from decksite.data import competition, deck, guarantee, match, person, query
from decksite.database import db
from decksite.scrapers import decklist
from magic import fetcher, legality, rotation
from shared import configuration, dtutil
from shared.container import Container
from shared.database import sqlescape
from shared.pd_exception import InvalidDataException, LockNotAcquiredException


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
    def __init__(self, form, mtgo_username=None):
        super().__init__(form)
        if mtgo_username is not None:
            self.mtgo_username = mtgo_username

    def do_validation(self):
        if len(self.mtgo_username) == 0:
            self.errors['mtgo_username'] = "Magic Online Username is required"
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
                    self.errors['decklist'] = 'Unable to read .dek decklist. Try exporting from Magic Online as Text and pasting the result.'.format(specific=str(e))
            else:
                try:
                    self.cards = decklist.parse(self.decklist)
                except InvalidDataException as e:
                    self.errors['decklist'] = '{specific}. Try exporting from Magic Online as Text and pasting the result.'.format(specific=str(e))
            if self.cards is not None:
                try:
                    vivified = decklist.vivify(self.cards)
                    errors = {}
                    if 'Penny Dreadful' not in legality.legal_formats(vivified, None, errors):
                        self.errors['decklist'] = 'Deck is not legal in Penny Dreadful - {error}'.format(error=errors.get('Penny Dreadful'))
                except InvalidDataException as e:
                    self.errors['decklist'] = str(e)

class ReportForm(Form):
    def __init__(self, form, deck_id=None, person_id=None):
        super().__init__(form)

        decks = active_decks()
        if person_id is not None:
            entry_decks = active_decks_by_person(person_id)
        else:
            entry_decks = decks

        self.entry_options = deck_options(entry_decks, self.get('entry', deck_id))
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
            for m in match.get_matches(self):
                if int(self.opponent) == m.opponent_deck_id:
                    self.errors['result'] = 'This match was reported as You {game_wins}–{game_losses} {opponent} {date}'.format(game_wins=m.game_wins, game_losses=m.game_losses, opponent=m.opponent, date=dtutil.display_date(m.date))
        if len(self.result) == 0:
            self.errors['result'] = 'Please select a result'
        else:
            self.entry_games, self.opponent_games = self.result.split('–')
        if self.entry == self.opponent:
            self.errors['opponent'] = "You can't play yourself"

class RetireForm(Form):
    def __init__(self, form, deck_id=None, discord_user=None):
        super().__init__(form)
        person_object = None
        if discord_user is not None:
            person_object = person.load_person_by_discord_id(discord_user)
        if person_object:
            decks = active_decks_by_person(person_object.id)
        else:
            decks = active_decks()
        self.entry_options = deck_options(decks, self.get('entry', deck_id))
        self.discord_user = discord_user
        if len(decks) == 0:
            self.errors['entry'] = "You don't have any decks to retire"

    def do_validation(self):
        if len(self.entry) == 0:
            self.errors['entry'] = 'Please select your deck'
        if not person.is_allowed_to_retire(self.entry, self.discord_user):
            self.errors['entry'] = 'You cannot retire this deck. This discord user is already assigned to another Magic Online user'
        print(self.errors)

def signup(form):
    form.mtgo_username = form.mtgo_username.strip()
    form.name = form.name.strip()
    return deck.add_deck(form)

def identifier(params):
    # Current timestamp is part of identifier here because we don't need to defend against dupes in league – it's fine to enter the same league with the same deck, later.
    return json.dumps([params['mtgo_username'], params['name'], params['competition_id'], str(int(time.time()))])

def deck_options(decks, v):
    if (v is None or v == '') and len(decks) == 1:
        v = str(decks[0].id)

    return [{'text': '{person} - {deck}'.format(person=d.person, deck=d.name), 'value': d.id, 'selected': v == str(d.id), 'can_draw': d.can_draw} for d in decks]

def active_decks(additional_where='1 = 1'):
    where = """
        d.id IN (
            SELECT
                id
            FROM
                deck
            WHERE
                competition_id = ({active_competition_id_query})
        ) AND (
                SELECT
                    COUNT(id)
                FROM
                    deck_match AS dm
                WHERE
                    dm.deck_id = d.id
            ) <= 4
        AND
            NOT d.retired
        AND
            ({additional_where})
    """.format(active_competition_id_query=active_competition_id_query(), additional_where=additional_where)
    decks = deck.load_decks(where)
    return sorted(decks, key=lambda d: '{person}{deck}'.format(person=d.person.ljust(100), deck=d.name))

def active_decks_by(mtgo_username):
    return active_decks('p.mtgo_username = {mtgo_username}'.format(mtgo_username=sqlescape(mtgo_username, force_string=True)))

def active_decks_by_person(person_id):
    return active_decks('p.id = {id}'.format(id=person_id))

def report(form):
    try:
        if db().supports_lock():
            db().get_lock('deck_id:{id}'.format(id=form.entry))
            db().get_lock('deck_id:{id}'.format(id=form.opponent))
        counts = deck.count_matches(form.entry, form.opponent)
        if counts[int(form.entry)] >= 5:
            form.errors['entry'] = "You already have 5 matches reported"
            return False
        if counts[int(form.opponent)] >= 5:
            form.errors['opponent'] = "Your opponent already has 5 matches reported"
            return False
        pdbot = form.get('api_token', None) == configuration.get('pdbot_api_token')
        if pdbot:
            mtgo_match_id = form.get('matchID', None)
        else:
            mtgo_match_id = None
            entry_name = deck.load_deck(int(form.entry)).person.decode('utf-8')
            opp_name = deck.load_deck(int(form.opponent)).person.decode('utf-8')
            fetcher.post_discord_webhook(
                configuration.get("league_webhook_id"),
                configuration.get("league_webhook_token"),
                "{entry} reported {f.entry_games}-{f.opponent_games} vs {opponent}".format(f=form, entry=entry_name, opponent=opp_name)
            )

        db().begin()
        match.insert_match(dtutil.now(), form.entry, form.entry_games, form.opponent, form.opponent_games, None, None, mtgo_match_id)
        db().commit()
        return True
    except LockNotAcquiredException:
        form.errors['entry'] = "Cannot report right now, somebody else is reporting a match for you or your opponent. Try again a bit later"
        return False
    finally:
        if db().supports_lock():
            db().release_lock('deck_id:{id}'.format(id=form.opponent))
            db().release_lock('deck_id:{id}'.format(id=form.entry))

def winner_and_loser(params):
    if params.entry_games > params.opponent_games:
        return (params.entry, params.opponent)
    elif params.opponent_games > params.entry_games:
        return (params.opponent, params.entry)
    return (None, None)

def active_competition_id_query():
    return """
        SELECT id FROM competition
        WHERE
            start_date < {now}
        AND
            end_date > {now}
        AND
            id IN ({competition_ids_by_type_select})
        """.format(now=dtutil.dt2ts(dtutil.now()), competition_ids_by_type_select=query.competition_ids_by_type_select('League'))

def active_league():
    where = 'c.id = ({id_query})'.format(id_query=active_competition_id_query())
    leagues = competition.load_competitions(where)
    if len(leagues) == 0:
        start_date = dtutil.now(tz=dtutil.WOTC_TZ)
        end_date = determine_end_of_league(start_date)
        name = determine_league_name(end_date)
        comp_id = competition.get_or_insert_competition(start_date, end_date, name, 'League', None)
        leagues = [competition.load_competition(comp_id)]
    return guarantee.exactly_one(leagues)

def determine_end_of_league(start_date):
    if start_date.day < 15:
        month = start_date.month + 1
    else:
        month = start_date.month + 2
    if month > 12:
        year = start_date.year + 1
        month = month - 12
    else:
        year = start_date.year
    end_date_s = '{year}-{month}-01 00:00:00'.format(year=year, month=month)
    end_date = dtutil.parse(end_date_s, '%Y-%m-%d %H:%M:%S', dtutil.WOTC_TZ).astimezone(dtutil.WOTC_TZ)
    if end_date > rotation.next_rotation():
        end_date = rotation.next_rotation()
    end_date = end_date - datetime.timedelta(seconds=1)
    return end_date

def determine_league_name(end_date):
    return "League {MM} {YYYY}".format(MM=calendar.month_name[end_date.month], YYYY=end_date.year)

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
        SELECT m.date, m.id, GROUP_CONCAT(dm.deck_id) AS deck_ids, GROUP_CONCAT(dm.games) AS games
        FROM `match` AS m
        INNER JOIN deck_match AS dm ON m.id = dm.match_id
        WHERE {where}
        GROUP BY m.id
        ORDER BY m.date DESC
    """.format(where=where)
    matches = [Container(m) for m in db().execute(sql)]
    for m in matches:
        m.date = dtutil.ts2dt(m.date)
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
    sql = 'DELETE FROM `match` WHERE id = ?'
    db().execute(sql, [sqlescape(match_id)])

def first_runs():
    sql = """
        SELECT
            d.competition_id,
            c.start_date AS `date`,
            c.name AS competition_name,
            p.mtgo_username
        FROM
            person AS p
        INNER JOIN
            deck AS d ON d.person_id = p.id
        INNER JOIN
            competition AS c ON c.id = d.competition_id
        INNER JOIN
            competition_series AS cs ON cs.id = c.competition_series_id
        INNER JOIN (
            SELECT
                d.person_id,
                MIN(c.start_date) AS start_date
            FROM
                deck AS d
            INNER JOIN
                competition AS c ON d.competition_id = c.id
            INNER JOIN
                competition_series AS cs ON cs.id = c.competition_series_id
            INNER JOIN
                deck_match AS dm ON dm.deck_id = d.id
            WHERE
                cs.competition_type_id IN ({league_competition_type_id})
            GROUP BY
                d.person_id
            HAVING
                COUNT(DISTINCT dm.match_id) >= 5
        ) AS fr ON fr.person_id = p.id AND c.start_date = fr.start_date
        GROUP BY
            d.competition_id, p.id
        ORDER BY
            c.start_date DESC,
            p.mtgo_username
    """.format(league_competition_type_id=query.competition_type_id_select('League'))
    return [Container(r) for r in db().execute(sql)]
