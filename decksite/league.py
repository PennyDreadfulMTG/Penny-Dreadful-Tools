import calendar
import datetime
import json
import time
from typing import Any, Dict, List, Optional

from flask import url_for
from werkzeug.datastructures import ImmutableMultiDict

from decksite.data import competition, deck, match, person, query
from decksite.data.form import Form
from decksite.database import db
from magic import card, decklist, fetcher, legality, rotation
from magic.models import Deck
from shared import configuration, dtutil, guarantee, redis
from shared.container import Container
from shared.database import sqlescape
from shared.pd_exception import InvalidDataException, LockNotAcquiredException
from shared_web import logger


# pylint: disable=attribute-defined-outside-init,too-many-instance-attributes
class SignUpForm(Form):
    def __init__(self,
                 form: ImmutableMultiDict,
                 person_id: Optional[int],
                 mtgo_username: Optional[str]) -> None:
        super().__init__(form)
        if person_id is not None:
            ps = person.load_person_by_id(person_id)
            self.recent_decks: List[Dict[str, Any]] = []
            for d in sorted(ps.decks, key=lambda deck: deck['created_date'], reverse=True)[0:10]:
                recent_deck = {'name': d['name'], 'main': [], 'sb':[]}
                for c in d.maindeck:
                    recent_deck['main'].append('{n} {c}'.format(n=c['n'], c=c['name']))
                for c in d.sideboard:
                    recent_deck['sb'].append('{n} {c}'.format(n=c['n'], c=c['name']))
                self.recent_decks.append({'name':d['name'], 'list':json.dumps(recent_deck)})
        if mtgo_username is not None:
            self.mtgo_username = mtgo_username
        self.deck = None
        self.card_errors: Dict[str, List[str]] = {}
        self.card_warnings: Dict[str, List[str]] = {}

    def do_validation(self):
        if len(self.mtgo_username) == 0:
            self.errors['mtgo_username'] = 'Magic Online Username is required'
        elif len(self.mtgo_username) > card.MAX_LEN_VARCHAR:
            self.errors['mtgo_username'] = 'Magic Online Username is too long (max {n})'.format(n=card.MAX_LEN_VARCHAR)
        elif active_decks_by(self.mtgo_username):
            self.errors['mtgo_username'] = "You already have an active league run.  If you wish to retire your run early, private message '!retire' to PDBot or visit the retire page."
        elif person.is_banned(self.mtgo_username):
            self.errors['mtgo_username'] = 'You are currently banned from Penny Dreadful'
        if len(self.name) == 0:
            self.errors['name'] = 'Deck Name is required'
        elif len(self.name) > card.MAX_LEN_TEXT:
            self.errors['name'] = 'Deck Name is too long (max {n})'.format(n=card.MAX_LEN_TEXT)
        else:
            self.source = 'League'
            self.competition_id = db().value(active_competition_id_query())
            self.identifier = identifier(self)
            self.url = url_for('competition', competition_id=self.competition_id, _external=True)
        self.parse_and_validate_decklist()

    def parse_and_validate_decklist(self):
        self.decklist = self.decklist.strip()
        if len(self.decklist) == 0:
            self.errors['decklist'] = 'Decklist is required'
        else:
            self.parse_decklist()
            if self.cards is not None:
                self.vivify_deck()
            if self.deck is not None:
                self.check_deck_legality()

    def parse_decklist(self):
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

    def vivify_deck(self):
        try:
            self.deck = decklist.vivify(self.cards)
        except InvalidDataException as e:
            self.errors['decklist'] = str(e)

    def check_deck_legality(self):
        errors: Dict[str, Dict[str, List[str]]] = {}
        if 'Penny Dreadful' not in legality.legal_formats(self.deck, None, errors):
            self.errors['decklist'] = ' '.join(errors.get('Penny Dreadful', {}).pop('Legality_General', ['Not a legal deck']))
            self.card_errors = errors.get('Penny Dreadful')
        banned_for_bugs = {c.name for c in self.deck.all_cards() if any([b.get('bannable', False) for b in c.bugs or []])}
        playable_bugs = {c.name for c in self.deck.all_cards() if c.pd_legal and any([not b.get('bannable', False) for b in c.bugs or []])}
        if len(banned_for_bugs) > 0:
            self.errors['decklist'] = 'Deck contains cards with game-breaking bugs'
            self.card_errors['Legality_Bugs'] = [name for name in banned_for_bugs]
        if len(playable_bugs) > 0:
            self.warnings['decklist'] = 'Deck contains playable bugs'
            self.card_warnings['Warnings_Bugs'] = [name for name in playable_bugs]


class DeckCheckForm(SignUpForm):
    def do_validation(self):
        self.parse_and_validate_decklist()
        if len(self.errors) == 0:
            self.validation_ok_message = 'The deck is legal'

class ReportForm(Form):
    def __init__(self,
                 form: ImmutableMultiDict,
                 deck_id: int = None,
                 person_id: int = None) -> None:
        super().__init__(form)

        decks = active_decks()
        if person_id is not None:
            entry_decks = active_decks_by_person(person_id)
        else:
            entry_decks = decks

        self.entry_options = deck_options(entry_decks, self.get('entry', deck_id), person_id)
        self.opponent_options = deck_options(decks, self.get('opponent', None), person_id)
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
        if len(self.result) == 0:
            self.errors['result'] = 'Please select a result'
        else:
            self.entry_games, self.opponent_games = self.result.split('–')
        if self.entry == self.opponent:
            self.errors['opponent'] = "You can't play yourself"

class RetireForm(Form):
    def __init__(self,
                 form: ImmutableMultiDict,
                 deck_id: int = None,
                 discord_user: int = None) -> None:
        super().__init__(form)
        person_object = None
        if discord_user is not None:
            person_object = person.maybe_load_person_by_discord_id(discord_user)
        if person_object:
            self.decks = active_decks_by_person(person_object.id)
        else:
            self.decks = active_decks()
        self.entry_options = deck_options(self.decks, self.get('entry', deck_id), person_object.id if person_object else None)
        self.discord_user = discord_user
        if len(self.decks) == 0:
            self.errors['entry'] = "You don't have any decks to retire"

    def do_validation(self):
        if len(self.decks) == 0:
            self.errors['entry'] = "You don't have any decks to retire"
        elif len(self.entry) == 0:
            self.errors['entry'] = 'Please select your deck'
        elif not person.is_allowed_to_retire(self.entry, self.discord_user):
            self.errors['entry'] = 'You cannot retire this deck. This discord user is already assigned to another Magic Online user'

def signup(form: SignUpForm) -> deck.Deck:
    form.mtgo_username = form.mtgo_username.strip()
    form.name = form.name.strip()
    return deck.add_deck(form)

def identifier(params: Dict[str, str]) -> str:
    # Current timestamp is part of identifier here because we don't need to defend against dupes in league – it's fine to enter the same league with the same deck, later.
    return json.dumps([params['mtgo_username'], params['competition_id'], str(round(time.time()))])

def deck_options(decks: List[deck.Deck], v: str, viewer_id: Optional[int]) -> List[Dict[str, Any]]:
    if (v is None or v == '') and len(decks) == 1:
        v = str(decks[0].id)
    return [{'text': d.name if d.person_id == viewer_id else d.person, 'value': d.id, 'selected': v == str(d.id), 'can_draw': d.can_draw} for d in decks]

def active_decks(additional_where: str = '1 = 1') -> List[deck.Deck]:
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

def active_decks_by(mtgo_username: str) -> List[deck.Deck]:
    return active_decks('p.mtgo_username = {mtgo_username}'.format(mtgo_username=sqlescape(mtgo_username, force_string=True)))

def active_decks_by_person(person_id: int) -> List[deck.Deck]:
    return active_decks('p.id = {id}'.format(id=person_id))

def report(form: ReportForm) -> bool:
    try:
        db().get_lock('deck_id:{id}'.format(id=form.entry))
        db().get_lock('deck_id:{id}'.format(id=form.opponent))

        pdbot = form.get('api_token', None) == configuration.get('pdbot_api_token')

        entry_deck_id = int(form.entry)
        opponent_deck_id = int(form.opponent)

        ds = {d.id: d for d in deck.load_decks(f'd.id IN ({entry_deck_id}, {opponent_deck_id})')}
        entry_deck = ds.get(entry_deck_id)
        opponent_deck = ds.get(opponent_deck_id)

        if not pdbot:
            if not entry_deck or entry_deck.retired:
                form.errors['entry'] = 'This deck is retired, you cannot report results for it. If you need to do this, contact a mod on the Discord.'
                return False
            if not opponent_deck or opponent_deck.retired:
                form.errors['opponent'] = "Your opponent's deck is retired, you cannot report results against it. If you need to do this, please contact a mod on the Discord."
                return False

            for m in match.load_matches_by_deck(form):
                if int(form.opponent) == m.opponent_deck_id:
                    form.errors['result'] = 'This match was reported as You {game_wins}–{game_losses} {opponent} {date}'.format(game_wins=m.game_wins, game_losses=m.game_losses, opponent=m.opponent, date=dtutil.display_date(m.date))
                    return False

        counts = deck.count_matches(form.entry, form.opponent)
        if counts[int(form.entry)] >= 5:
            form.errors['entry'] = 'You already have 5 matches reported'
            return False
        if counts[int(form.opponent)] >= 5:
            form.errors['opponent'] = 'Your opponent already has 5 matches reported'
            return False

        if pdbot:
            mtgo_match_id = form.get('matchID', None)
        else:
            mtgo_match_id = None
        match.insert_match(dtutil.now(), form.entry, form.entry_games, form.opponent, form.opponent_games, None, None, mtgo_match_id)
        if not pdbot:
            if configuration.get('league_webhook_id') and configuration.get('league_webhook_token'):
                fetcher.post_discord_webhook(
                    configuration.get_str('league_webhook_id'),
                    configuration.get_str('league_webhook_token'),
                    '{entry} reported {f.entry_games}-{f.opponent_games} vs {opponent}'.format(f=form, entry=entry_deck.person, opponent=opponent_deck.person)
                )
            else:
                logger.warning('Not posting manual report to discord because not configured.')
        return True
    except LockNotAcquiredException:
        form.errors['entry'] = 'Cannot report right now, somebody else is reporting a match for you or your opponent. Try again a bit later'
        return False
    finally:
        db().release_lock('deck_id:{id}'.format(id=form.opponent))
        db().release_lock('deck_id:{id}'.format(id=form.entry))

def winner_and_loser(params):
    if params.entry_games > params.opponent_games:
        return (params.entry, params.opponent)
    if params.opponent_games > params.entry_games:
        return (params.opponent, params.entry)
    return (None, None)

def active_competition_id_query() -> str:
    return """
        SELECT id FROM competition
        WHERE
            start_date < {now}
        AND
            end_date > {now}
        AND
            id IN ({competition_ids_by_type_select})
        """.format(now=dtutil.dt2ts(dtutil.now()), competition_ids_by_type_select=query.competition_ids_by_type_select('League'))

def active_league() -> competition.Competition:
    where = 'c.id = ({id_query})'.format(id_query=active_competition_id_query())
    leagues = competition.load_competitions(where)
    if len(leagues) == 0:
        start_date = dtutil.now(tz=dtutil.WOTC_TZ)
        end_date = determine_end_of_league(start_date, rotation.next_rotation())
        name = determine_league_name(start_date, end_date)
        comp_id = competition.get_or_insert_competition(start_date, end_date, name, 'League', None, competition.Top.EIGHT)
        if not comp_id:
            raise InvalidDataException(f'No competition id with {start_date}, {end_date}, {name}')
        leagues = [competition.load_competition(comp_id)]
    return guarantee.exactly_one(leagues)

def determine_end_of_league(start_date: datetime.datetime, next_rotation: datetime.datetime, lookahead: bool = True) -> datetime.datetime:
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
    if start_date < next_rotation < end_date:
        end_date = next_rotation
    end_date = end_date - datetime.timedelta(seconds=1)
    # Now we have an end date for this league let's make sure that it doesn't make the next league too short. See #5061.
    if lookahead:
        next_end_date = determine_end_of_league(end_date, next_rotation, False)
        if next_end_date - end_date < datetime.timedelta(days=14):
            end_date = next_end_date
    return end_date

def determine_league_name(start_date: datetime.datetime, end_date: datetime.datetime) -> str:
    start_of_end_month_s = '{year}-{month}-01 00:00:00'.format(year=end_date.year, month=end_date.month)
    start_of_end_month = dtutil.parse(start_of_end_month_s, '%Y-%m-%d %H:%M:%S', dtutil.WOTC_TZ).astimezone(dtutil.WOTC_TZ)
    if start_date + datetime.timedelta(weeks=2) < start_of_end_month:
        key_date = start_date
    else:
        key_date = end_date
    return 'League {MM} {YYYY}'.format(MM=calendar.month_name[key_date.month], YYYY=key_date.year)

def retire_deck(d: Deck) -> None:
    sql = 'UPDATE `deck` SET `retired` = 1, updated_date = UNIX_TIMESTAMP(NOW()) WHERE id = %s'
    db().execute(sql, [d.id])
    redis.clear(f'decksite:deck:{d.id}')

def load_latest_league_matches() -> List[Container]:
    competition_id = active_league().id
    where = 'dm.deck_id IN (SELECT id FROM deck WHERE competition_id = {competition_id})'.format(competition_id=competition_id)
    return load_matches(where)

def load_matches(where: str = '1 = 1') -> List[Container]:
    sql = """
        SELECT m.date, m.id, GROUP_CONCAT(dm.deck_id) AS deck_ids, GROUP_CONCAT(dm.games) AS games, mtgo_id
        FROM `match` AS m
        INNER JOIN deck_match AS dm ON m.id = dm.match_id
        WHERE {where}
        GROUP BY m.id
        ORDER BY m.date DESC
    """.format(where=where)
    matches = [Container(m) for m in db().select(sql)]
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

def delete_match(match_id: int) -> None:
    deck_ids = db().values('SELECT deck_id FROM deck_match WHERE match_id = %s', [match_id])
    sql = 'DELETE FROM `match` WHERE id = %s'
    db().execute(sql, [match_id])
    for deck_id in deck_ids:
        redis.clear(f'decksite:deck:{deck_id}')

def first_runs() -> List[Container]:
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
    return [Container(r) for r in db().select(sql)]

def update_match(match_id: int, left_id: int, left_games: int, right_id: int, right_games: int) -> None:
    db().begin('update_match')
    update_games(match_id, left_id, left_games)
    update_games(match_id, right_id, right_games)
    db().commit('update_match')
    redis.clear(f'decksite:deck:{left_id}', f'decksite:deck:{right_id}')

def update_games(match_id: int, deck_id: int, games: int) -> int:
    sql = 'UPDATE deck_match SET games = %s WHERE match_id = %s AND deck_id = %s'
    args = [games, match_id, deck_id]
    return db().execute(sql, args)

def random_legal_deck() -> Optional[Deck]:
    where = 'd.reviewed AND d.created_date > (SELECT start_date FROM season WHERE number = {current_season_num})'.format(current_season_num=rotation.current_season_num())
    having = '(d.competition_id NOT IN ({active_competition_id_query}) OR SUM(cache.wins + cache.draws + cache.losses) >= 5)'.format(active_competition_id_query=active_competition_id_query())
    try:
        return deck.load_decks(where=where, having=having, order_by='RAND()', limit='LIMIT 1')[0]
    except IndexError:
        # For a short while at the start of a season there are no decks that match the WHERE/HAVING clauses.
        return None
