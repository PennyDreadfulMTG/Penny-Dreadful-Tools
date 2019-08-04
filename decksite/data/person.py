from typing import List, Optional, Sequence

from decksite.data import achievements, deck, query
from decksite.database import db
from shared import dtutil, guarantee
from shared.container import Container
from shared.database import sqlescape
from shared.decorators import retry_after_calling
from shared.pd_exception import AlreadyExistsException, DoesNotExistException
from shared_web import logger


class Person(Container):
    __decks = None
    @property
    def decks(self) -> List[deck.Deck]:
        if self.__decks is None:
            self.__decks = deck.load_decks(f'd.person_id = {self.id}', season_id=self.season_id)
        return self.__decks

def load_person_by_id(person_id: int, season_id: Optional[int] = None) -> Person:
    return load_person(f'p.id = {person_id}', season_id=season_id)

def load_person_by_mtgo_username(username: str, season_id: Optional[int] = None) -> Person:
    return load_person('p.mtgo_username = {username}'.format(username=sqlescape(username, force_string=True)), season_id=season_id)


def load_person_by_discord_id(discord_id: int, season_id: Optional[int] = None) -> Person:
    return load_person(f'p.discord_id = {discord_id}', season_id=season_id)

# pylint: disable=invalid-name
def load_person_by_id_or_mtgo_username(person: str, season_id: Optional[int] = None) -> Person:
    if person.isdigit():
        try:
            return load_person_by_id(int(person), season_id)
        except DoesNotExistException:
            pass # If we failed to load by id we want to try and load as a Magic Online username for people with Magic Online usernames that are integers like '4423'.
    return load_person_by_mtgo_username(person, season_id)

# pylint: disable=invalid-name


def load_person_by_discord_id_or_username(person: str, season_id: int = 0) -> Person:
    # It would probably be better if this method did not exist but for now it's required by the API.
    # The problem is that Magic Online usernames can be integers so we cannot be completely unambiguous here.
    # We can make a really good guess, though.
    # See https://discordapp.com/developers/docs/reference#snowflakes
    # Unix timestamp (ms) for 2015-01-01T00:00:00.0000    =       1420070400000
    # Unix timestamp (ms) for 2015-01-01T00:00:00.0001    =       1420070400001
    # Unix timestamp (ms) for 2015-02-01T00:00:00.0000    =       1422748800000
    # Unix timestamp (ms) for 2100-01-01T00:00:00.0000    =       4102444800000
    # Discord timestamp (ms) for 2015-01-01T00:00:00.0000 =                   0
    # Discord timestamp (ms) for 2015-01-01T00:00:00.0001 =                   1
    # Discord timestamp (ms) for 2015-02-01T00:00:00.0000 =          2678400000
    # Min Discord snowflake for 2015-01-01T00:00:00.0000  =                   0 (                                        00000000000000000000000 in binary)
    # Min Discord snowflake for 2015-01-01T00:00:00.0001  =             4194304 (                                        10000000000000000000000 in binary)
    # Min Discord snowflake for 2015-02-01T00:00:00.0000  =   11234023833600000 (         100111111010010100100100000000000000000000000000000000 in binary)
    # Min Discord snowflake for 2100-01-01T00:00:00.0000  = 5625346837708800000 (100111000010001001111110010010100000000000000000000000000000000 in binary)
    # Discord snowflakes created between 2015-01-01T00:00:00.001Z and 2100-01-01T00:00:00.000Z will therefore fall in the range 2097152-5625346837708800000 if created before the year 2100.
    # We use 2015-02-01T00:00:00.000Z (11234023833600000) as the start of the range instead because it greatly reduces the range and we have seen no evidence of Discord snowflakes from before December 28th 2015.
    # This function will fail or (very unlikely) return incorrect results if we ever have a player with a Magic Online username that falls numerically between MIN_DISCORD_ID and MAX_DISCORD_ID.
    MIN_DISCORD_ID = 11234023833600000
    MAX_DISCORD_ID = 5625346837708800000
    if person.isdigit() and int(person) >= MIN_DISCORD_ID and int(person) <= MAX_DISCORD_ID:
        return load_person_by_discord_id(int(person), season_id=season_id)
    return load_person_by_mtgo_username(person, season_id=season_id)

# pylint: disable=invalid-name
def maybe_load_person_by_discord_id(discord_id: Optional[int]) -> Optional[Person]:
    if discord_id is None:
        return None
    return guarantee.at_most_one(load_people(f'p.discord_id = {discord_id}'))

# pylint: disable=invalid-name
def maybe_load_person_by_tappedout_name(username: str) -> Optional[Person]:
    return guarantee.at_most_one(load_people('p.tappedout_username = {username}'.format(username=sqlescape(username))))

# pylint: disable=invalid-name
def maybe_load_person_by_mtggoldfish_name(username: str) -> Optional[Person]:
    return guarantee.at_most_one(load_people('p.mtggoldfish_username = {username}'.format(username=sqlescape(username))))

def load_person(where: str, season_id: Optional[int] = None) -> Person:
    person = guarantee.exactly_one(load_people(where, season_id=season_id))
    set_achievements([person], season_id)
    set_head_to_head([person], season_id)
    return person

def load_people(where: str = '1 = 1',
                order_by: str = '`num_decks` DESC, name',
                season_id: Optional[int] = None) -> Sequence[Person]:
    sql = """
        SELECT
            p.id,
            {person_query} AS name,
            p.mtgo_username,
            p.tappedout_username,
            p.mtggoldfish_username,
            p.discord_id,
            p.elo,
            p.locale,
            num_decks,
            wins,
            losses,
            draws,
            perfect_runs,
            tournament_wins,
            tournament_top8s,
            win_percent,
            num_competitions
        FROM
            person AS p
        LEFT JOIN
            (
                SELECT
                    d.person_id,
                    COUNT(d.id) AS num_decks,
                    SUM(wins) AS wins,
                    SUM(losses) AS losses,
                    SUM(draws) AS draws,
                    SUM(CASE WHEN wins >= 5 AND losses = 0 AND d.source_id IN (SELECT id FROM source WHERE name = 'League') THEN 1 ELSE 0 END) AS perfect_runs,
                    SUM(CASE WHEN d.finish = 1 THEN 1 ELSE 0 END) AS tournament_wins,
                    SUM(CASE WHEN d.finish <= 8 THEN 1 ELSE 0 END) AS tournament_top8s,
                    IFNULL(ROUND((SUM(wins) / NULLIF(SUM(wins + losses), 0)) * 100, 1), '') AS win_percent,
                    SUM(DISTINCT CASE WHEN d.competition_id IS NOT NULL THEN 1 ELSE 0 END) AS num_competitions
                FROM
                    deck AS d
                LEFT JOIN
                    deck_cache AS dc ON d.id = dc.deck_id
                {season_join}
                WHERE
                    {season_query}
                GROUP BY
                    d.person_id
            ) AS stats ON p.id = stats.person_id
        WHERE
            {where}
        GROUP BY
            p.id
        ORDER BY
            {order_by}
    """.format(person_query=query.person_query(), season_join=query.season_join(), where=where, season_query=query.season_query(season_id, 'season.id'), order_by=order_by)
    people = [Person(r) for r in db().select(sql)]
    for p in people:
        p.season_id = season_id
    return people

def preaggregate() -> None:
    achievements.preaggregate_achievements()
    preaggregate_head_to_head()

def preaggregate_head_to_head() -> None:
    db().execute('DROP TABLE IF EXISTS _new_head_to_head_stats')
    sql = """
        CREATE TABLE IF NOT EXISTS _new_head_to_head_stats (
            person_id INT NOT NULL,
            opponent_id INT NOT NULL,
            season_id INT NOT NULL,
            num_matches INT NOT NULL,
            wins INT NOT NULL,
            losses INT NOT NULL,
            draws INT NOT NULL,
            PRIMARY KEY (season_id, person_id, opponent_id),
            FOREIGN KEY (season_id) REFERENCES season (id) ON UPDATE CASCADE ON DELETE CASCADE,
            FOREIGN KEY (person_id) REFERENCES person (id) ON UPDATE CASCADE ON DELETE CASCADE,
            FOREIGN KEY (opponent_id) REFERENCES person (id) ON UPDATE CASCADE ON DELETE CASCADE
        ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci AS
        SELECT
            p.id AS person_id,
            opp.id AS opponent_id,
            season.id AS season_id,
            COUNT(p.id) AS num_matches,
            SUM(CASE WHEN dm.games > odm.games THEN 1 ELSE 0 END) AS wins,
            SUM(CASE WHEN dm.games < odm.games THEN 1 ELSE 0 END) AS losses,
            SUM(CASE WHEN dm.games = odm.games THEN 1 ELSE 0 END) AS draws
        FROM
            person AS p
        INNER JOIN
            deck AS d ON p.id = d.person_id
        INNER JOIN
            deck_match AS dm ON dm.deck_id = d.id
        INNER JOIN
            deck_match AS odm ON dm.match_id = odm.match_id AND dm.deck_id <> IFNULL(odm.deck_id, 0)
        INNER JOIN
            deck AS od ON odm.deck_id = od.id
        INNER JOIN
            person AS opp ON od.person_id = opp.id
        {season_join}
        GROUP BY
            p.id,
            opp.id,
            season.id
    """.format(season_join=query.season_join())
    db().execute(sql)
    db().execute('DROP TABLE IF EXISTS _old_head_to_head_stats')
    db().execute('CREATE TABLE IF NOT EXISTS _head_to_head_stats (_ INT)') # Prevent error in RENAME TABLE below if bootstrapping.
    db().execute('RENAME TABLE _head_to_head_stats TO _old_head_to_head_stats, _new_head_to_head_stats TO _head_to_head_stats')
    db().execute('DROP TABLE IF EXISTS _old_head_to_head_stats')

@retry_after_calling(achievements.preaggregate_achievements)
def set_achievements(people: List[Person], season_id: int = None) -> None:
    people_by_id = {person.id: person for person in people}
    sql = achievements.load_query(people_by_id, season_id)
    results = [Container(r) for r in db().select(sql)]
    for result in results:
        people_by_id[result['id']].num_achievements = len([k for k, v in result.items() if k != 'id' and v > 0])
        people_by_id[result['id']].achievements = result
        people_by_id[result['id']].achievements.pop('id')

@retry_after_calling(preaggregate_head_to_head)
def set_head_to_head(people: List[Person], season_id: int = None) -> None:
    people_by_id = {person.id: person for person in people}
    sql = """
        SELECT
            hths.person_id AS id,
            LOWER(opp.mtgo_username) AS opp_mtgo_username,
            SUM(num_matches) AS num_matches,
            SUM(wins) AS wins,
            SUM(losses) AS losses,
            SUM(draws) AS draws,
            IFNULL(ROUND((SUM(wins) / NULLIF(SUM(wins + losses), 0)) * 100, 1), '') AS win_percent
        FROM
            _head_to_head_stats AS hths
        INNER JOIN
            person AS opp ON hths.opponent_id = opp.id
        WHERE
            hths.person_id IN ({ids}) AND ({season_query})
        GROUP BY
            hths.person_id,
            hths.opponent_id
        ORDER BY
            SUM(num_matches) DESC,
            SUM(wins - losses) DESC,
            win_percent DESC,
            SUM(wins) DESC,
            opp_mtgo_username
    """.format(ids=', '.join(str(k) for k in people_by_id.keys()), season_query=query.season_query(season_id))
    results = [Container(r) for r in db().select(sql)]
    for result in results:
        people_by_id[result.id].head_to_head = people_by_id[result.id].get('head_to_head', []) + [result]
    for person in people:
        if person.get('head_to_head') is None:
            person.head_to_head = []

def associate(d: deck.Deck, discord_id: int) -> int:
    person_id = db().value('SELECT person_id FROM deck WHERE id = %s', [d.id], fail_on_missing=True)
    sql = 'UPDATE person SET discord_id = %s WHERE id = %s'
    return db().execute(sql, [discord_id, person_id])

def is_allowed_to_retire(deck_id: int, discord_id: int) -> bool:
    if not deck_id:
        return False
    if not discord_id:
        return True
    person = maybe_load_person_by_discord_id(discord_id)
    if person is None:
        return True
    return any(int(deck_id) == deck.id for deck in person.decks)

def get_or_insert_person_id(mtgo_username: Optional[str], tappedout_username: Optional[str], mtggoldfish_username: Optional[str]) -> int:
    sql = 'SELECT id FROM person WHERE LOWER(mtgo_username) = LOWER(%s) OR LOWER(tappedout_username) = LOWER(%s) OR LOWER(mtggoldfish_username) = LOWER(%s)'
    person_id = db().value(sql, [mtgo_username, tappedout_username, mtggoldfish_username])
    if person_id:
        return person_id
    sql = 'INSERT INTO person (mtgo_username, tappedout_username, mtggoldfish_username) VALUES (%s, %s, %s)'
    return db().insert(sql, [mtgo_username, tappedout_username, mtggoldfish_username])

def load_aliases() -> List[Container]:
    sql = """
        SELECT
            pa.person_id,
            pa.alias,
            p.mtgo_username
        FROM
            person_alias AS pa
        INNER JOIN
            person AS p ON p.id = pa.person_id
    """
    return [Container(r) for r in db().select(sql)]

def add_alias(person_id: int, alias: str) -> None:
    db().begin('add_alias')
    try:
        p = load_person_by_mtgo_username(alias)
        db().execute('UPDATE deck SET person_id = %s WHERE person_id = %s', [person_id, p.id])
        db().execute('DELETE FROM person WHERE id = %s', [p.id])
    except DoesNotExistException:
        pass
    db().execute('INSERT INTO person_alias (person_id, alias) VALUES (%s, %s)', [person_id, alias])
    db().commit('add_alias')

def load_notes(person_id: int = None) -> List[Container]:
    where = f'subject_id = {person_id}' if person_id else 'TRUE'
    sql = """
        SELECT
            pn.created_date,
            pn.creator_id,
            {creator_query} AS creator,
            pn.subject_id,
            {subject_query} AS subject,
            note
        FROM
            person_note AS pn
        INNER JOIN
            person AS c ON pn.creator_id = c.id
        INNER JOIN
            person AS s ON pn.subject_id = s.id
        WHERE
            {where}
        ORDER BY
            s.id,
            pn.created_date DESC
    """.format(creator_query=query.person_query('c'), subject_query=query.person_query('s'), where=where)
    notes = [Container(r) for r in db().select(sql)]
    for n in notes:
        n.created_date = dtutil.ts2dt(n.created_date)
        n.display_date = dtutil.display_date(n.created_date)
    return notes

def add_note(creator_id: int, subject_id: int, note: str) -> None:
    sql = 'INSERT INTO person_note (created_date, creator_id, subject_id, note) VALUES (UNIX_TIMESTAMP(NOW()), %s, %s, %s)'
    db().execute(sql, [creator_id, subject_id, note])

def link_discord(mtgo_username: str, discord_id: int) -> Person:
    person_id = deck.get_or_insert_person_id(mtgo_username, None, None)
    p = load_person_by_id(person_id)
    if p.discord_id is not None:
        raise AlreadyExistsException('Player with mtgo username {mtgo_username} already has discord id {old_discord_id}, cannot add {new_discord_id}'.format(mtgo_username=mtgo_username, old_discord_id=p.discord_id, new_discord_id=discord_id))
    sql = 'UPDATE person SET discord_id = %s WHERE id = %s'
    db().execute(sql, [discord_id, p.id])
    return p

def unlink_discord(person_id: int) -> int:
    sql = 'UPDATE person SET discord_id = NULL WHERE id = %s'
    return db().execute(sql, [person_id])

def remove_discord_link(discord_id: int) -> int:
    sql = 'UPDATE person SET discord_id = NULL WHERE discord_id = %s'
    return db().execute(sql, [discord_id])

def is_banned(mtgo_username: str) -> bool:
    return db().value('SELECT banned FROM person WHERE mtgo_username = %s', [mtgo_username]) == 1

def squash(p1id: int, p2id: int, col1: str, col2: str) -> None:
    logger.warning('Squashing {p1id} and {p2id} on {col1} and {col2}'.format(p1id=p1id, p2id=p2id, col1=col1, col2=col2))
    db().begin('squash')
    new_value = db().value('SELECT {col2} FROM person WHERE id = %s'.format(col2=col2), [p2id])
    db().execute('UPDATE deck SET person_id = %s WHERE person_id = %s', [p1id, p2id])
    db().execute('DELETE FROM person WHERE id = %s', [p2id])
    db().execute('UPDATE person SET {col2} = %s WHERE id = %s'.format(col2=col2), [new_value, p1id])
    db().commit('squash')

def set_locale(person_id: int, locale: str) -> None:
    db().execute('UPDATE person SET locale = %s WHERE id = %s', [locale, person_id])
