import calendar
import datetime
import json
import time
from enum import Enum
from typing import Any

from flask import url_for
from werkzeug.datastructures import ImmutableMultiDict

from decksite.data import competition, deck, match, person, query
from decksite.database import db
from decksite.form import DecklistForm, Form
from magic import card, seasons
from magic.models import Deck
from shared import configuration, dtutil, fetch_tools, guarantee, logger
from shared import redis_wrapper as redis
from shared.container import Container
from shared.database import sqlescape
from shared.pd_exception import InvalidArgumentException, InvalidDataException, LockNotAcquiredException


class Status(Enum):
    CLOSED = 0
    OPEN = 1


class SignUpForm(DecklistForm):
    def __init__(self, form: ImmutableMultiDict, person_id: int | None, mtgo_username: str | None) -> None:
        super().__init__(form, person_id, mtgo_username)
        self.source = 'League'
        self.competition_id = active_league().id
        self.identifier = ''
        self.url = url_for('competition', competition_id=self.competition_id, _external=True)

    def do_validation(self) -> None:
        if len(self.mtgo_username) == 0:
            self.errors['mtgo_username'] = 'Magic Online Username is required'
        elif len(self.mtgo_username) > card.MAX_LEN_VARCHAR:
            self.errors['mtgo_username'] = f'Magic Online Username is too long (max {card.MAX_LEN_VARCHAR})'
        elif active_decks_by(self.mtgo_username):
            self.errors['mtgo_username'] = "You already have an active league run.  If you wish to retire your run early, private message '!retire' to PDBot or visit the retire page."
        elif person.is_banned(self.mtgo_username):
            self.errors['mtgo_username'] = 'You are currently banned from Penny Dreadful. Visit the Discord to appeal – pennydreadfulmagic.com/discord'
        if len(self.name) == 0:
            self.errors['name'] = 'Deck Name is required'
        elif len(self.name) > card.MAX_LEN_TEXT:
            self.errors['name'] = f'Deck Name is too long (max {card.MAX_LEN_TEXT})'
        self.parse_and_validate_decklist()
        self.identifier = identifier(self)


class DeckCheckForm(DecklistForm):
    def __init__(self, form: ImmutableMultiDict, person_id: int | None, mtgo_username: str | None) -> None:
        super().__init__(form, person_id, mtgo_username)
        self.validation_ok_message = ''

    def do_validation(self) -> None:
        self.parse_and_validate_decklist()
        if len(self.errors) == 0:
            self.validation_ok_message = 'The deck is legal'


class ReportForm(Form):
    def __init__(self, form: ImmutableMultiDict, deck_id: int | None = None, person_id: int | None = None) -> None:
        super().__init__(form)

        decks = active_decks()
        if person_id is not None:
            entry_decks = active_decks_by_person(person_id)
        else:
            entry_decks = decks

        if len(entry_decks) == 1:
            ms = match.load_matches_by_deck(entry_decks[0])
            opponents = {m.opponent: m.opponent_deck_id for m in ms}
        else:
            opponents = {}
        self.opponents = json.dumps(opponents)

        self.entry_options = deck_options(entry_decks, self.get('entry', deck_id), person_id, False)
        self.opponent_options = deck_options([d for d in decks if d.person_id != person_id], self.get('opponent', None), person_id, False)
        self.result_options = [
            {'text': 'Win 2–0', 'value': '2–0', 'selected': self.get('result', None) == '2–0'},
            {'text': 'Win 2–1', 'value': '2–1', 'selected': self.get('result', None) == '2–1'},
            {'text': 'Lose 1–2', 'value': '1–2', 'selected': self.get('result', None) == '1–2'},
            {'text': 'Lose 0–2', 'value': '0–2', 'selected': self.get('result', None) == '0–2'},
        ]

    def do_validation(self) -> None:
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
    def __init__(self, form: ImmutableMultiDict, deck_id: int | None = None, discord_user: int | None = None) -> None:
        super().__init__(form)
        person_object = None
        if discord_user is not None:
            person_object = person.maybe_load_person_by_discord_id(discord_user)
        if person_object:
            self.decks = active_decks_by_person(person_object.id)
        else:
            self.decks = active_decks()
        self.entry_options = deck_options(self.decks, self.get('entry', deck_id), person_object.id if person_object else None, True)
        self.discord_user = discord_user
        if len(self.decks) == 0:
            self.errors['entry'] = "You don't have any decks to retire"

    def do_validation(self) -> None:
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


def identifier(params: dict[str, str]) -> str:
    # Current timestamp is part of identifier here because we don't need to defend against dupes in league – it's fine to enter the same league with the same deck, later.
    return json.dumps([params['mtgo_username'], params['competition_id'], str(round(time.time()))])


def deck_options(decks: list[deck.Deck], v: str, viewer_id: int | None, show_details: bool) -> list[dict[str, Any]]:
    if (v is None or v == '') and len(decks) == 1:
        v = str(decks[0].id)
    r = []
    for d in decks:
        r.append({'text': deck_option_text(d, viewer_id, show_details), 'value': d.id, 'selected': v == str(d.id), 'can_draw': d.can_draw})
    return r


def deck_option_text(d: deck.Deck, viewer_id: int | None, show_details: bool) -> str:
    if d.person_id == viewer_id:
        return d.name
    elif show_details:
        return f'{d.person} ({d.name}, {d.id})'
    return d.person


def active_decks(additional_where: str = 'TRUE') -> list[deck.Deck]:
    where = f"""
        d.id IN (
            SELECT
                id
            FROM
                deck
            WHERE
                competition_id = ({active_competition_id_query()})
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
    """
    decks, _ = deck.load_decks(where)
    return sorted(decks, key=lambda d: f'{d.person.ljust(100)}{d.name}')


def active_decks_by(mtgo_username: str) -> list[deck.Deck]:
    return active_decks(f'p.mtgo_username = {sqlescape(mtgo_username, force_string=True)}')


def active_decks_by_person(person_id: int) -> list[deck.Deck]:
    return active_decks(f'p.id = {person_id}')


def report(form: ReportForm) -> bool:
    try:
        db().get_lock(f'deck_id:{form.entry}')
        db().get_lock(f'deck_id:{form.opponent}')

        pdbot = form.get('api_token', None) == configuration.get('pdbot_api_token')

        entry_deck_id = int(form.entry)
        opponent_deck_id = int(form.opponent)

        ds, _ = deck.load_decks(f'd.id IN ({entry_deck_id}, {opponent_deck_id})')
        ds_by_id = {d.id: d for d in ds}
        entry_deck = ds_by_id.get(entry_deck_id)
        opponent_deck = ds_by_id.get(opponent_deck_id)

        if not entry_deck:
            form.errors['entry'] = 'This deck does not appear to exist. Please try again.'
            return False

        if not opponent_deck:
            form.errors['opponent'] = 'This deck does not appear to exist. Please try again.'
            return False

        if not pdbot:
            if entry_deck.retired:
                form.errors['entry'] = 'Your deck is retired, you cannot report results for it. If you need to do this, contact a mod on the Discord.'
                return False
            if opponent_deck.retired:
                form.errors['opponent'] = "Your opponent's deck is retired, you cannot report results against it. If you need to do this, please contact a mod on the Discord."
                return False

        for m in match.load_matches_by_deck(form):
            if int(form.opponent) == m.opponent_deck_id:
                form.errors['result'] = f'This match was reported as You {m.game_wins}–{m.game_losses} {m.opponent} {dtutil.display_date(m.date)}'
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
                fetch_tools.post_discord_webhook(
                    configuration.get_str('league_webhook_id'),
                    configuration.get_str('league_webhook_token'),
                    f'{entry_deck.person} reported {form.entry_games}-{form.opponent_games} vs {opponent_deck.person}',
                )
            else:
                logger.warning('Not posting manual report to discord because not configured.')
        return True
    except LockNotAcquiredException:
        form.errors['entry'] = 'Cannot report right now, somebody else is reporting a match for you or your opponent. Try again a bit later'
        return False
    finally:
        db().release_lock(f'deck_id:{form.opponent}')
        db().release_lock(f'deck_id:{form.entry}')


def winner_and_loser(params: Container) -> tuple[int | None, int | None]:
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


def active_league(should_load_decks: bool = False) -> competition.Competition:
    where = f'c.id = ({active_competition_id_query()})'
    leagues = competition.load_competitions(where, should_load_decks=should_load_decks)
    if len(leagues) == 0:
        start_date = dtutil.now(tz=dtutil.WOTC_TZ)
        end_date = determine_end_of_league(start_date, seasons.next_rotation())
        name = determine_league_name(start_date, end_date)
        comp_id = competition.get_or_insert_competition(start_date, end_date, name, 'League', None, competition.Top.EIGHT)
        if not comp_id:
            raise InvalidDataException(f'No competition id with {start_date}, {end_date}, {name}')
        leagues = [competition.load_competition(comp_id)]
    return guarantee.exactly_one(leagues)


def determine_end_of_league(start_date: datetime.datetime, next_rotation: datetime.datetime, lookahead: bool = True) -> datetime.datetime:
    if start_date >= next_rotation:
        raise InvalidArgumentException(f"You can't start a league on {start_date} if next rotation is on {next_rotation}")
    if start_date.day < 15:
        month = start_date.month + 1
    else:
        month = start_date.month + 2
    if month > 12:
        year = start_date.year + 1
        month = month - 12
    else:
        year = start_date.year
    end_date_s = f'{year}-{month}-01 00:00:00'
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
    local_start_date = start_date.replace(tzinfo=dtutil.UTC_TZ).astimezone(tz=dtutil.WOTC_TZ)
    local_end_date = end_date.replace(tzinfo=dtutil.UTC_TZ).astimezone(tz=dtutil.WOTC_TZ)
    start_of_end_month_s = f'{local_end_date.year}-{local_end_date.month}-01 00:00:00'
    start_of_end_month = dtutil.parse(start_of_end_month_s, '%Y-%m-%d %H:%M:%S', dtutil.WOTC_TZ).astimezone(dtutil.WOTC_TZ)
    first_month_duration = start_of_end_month - local_start_date
    second_month_duration = local_end_date - start_of_end_month
    if first_month_duration >= second_month_duration:
        key_date = local_start_date
    else:
        key_date = local_end_date
    return f'League {calendar.month_name[key_date.month]} {key_date.year}'


def retire_deck(d: Deck) -> None:
    sql = 'UPDATE `deck` SET `retired` = 1, updated_date = UNIX_TIMESTAMP(NOW()) WHERE id = %s'
    db().execute(sql, [d.id])
    redis.clear(f'decksite:deck:{d.id}')


def random_legal_deck() -> Deck | None:
    where = f'd.reviewed AND d.created_date > (SELECT start_date FROM season WHERE number = {seasons.current_season_num()})'
    having = f'(d.competition_id NOT IN ({active_competition_id_query()}) OR SUM(cache.wins + cache.draws + cache.losses) >= 5)'
    try:
        ds, _ = deck.load_decks(where=where, having=having, order_by='RAND()', limit='LIMIT 1')[0]
        return ds
    except IndexError:
        # For a short while at the start of a season there are no decks that match the WHERE/HAVING clauses.
        return None


def get_status() -> Status:
    sql = f'SELECT is_locked FROM competition WHERE id IN ({active_competition_id_query()})'
    is_locked = db().value(sql)
    return Status.CLOSED if is_locked else Status.OPEN


def set_status(status: Status) -> None:
    current = active_league()
    sql = 'UPDATE competition SET is_locked = %s WHERE id = %s'
    db().execute(sql, [1 if status == Status.CLOSED else 0, current.id])
