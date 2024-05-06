from collections.abc import Sequence

from decksite.data import achievements, deck, preaggregation, query
from decksite.data.models.person import Person
from decksite.database import db
from shared import dtutil, guarantee, logger
from shared.container import Container
from shared.database import sqlescape
from shared.decorators import retry_after_calling
from shared.pd_exception import AlreadyExistsException, DoesNotExistException


def load_person_by_id(person_id: int, season_id: int | None = None) -> Person:
    return load_person(f'p.id = {person_id}', season_id=season_id)

def load_person_by_mtgo_username(username: str, season_id: int | None = None) -> Person:
    return load_person(f'p.mtgo_username = {sqlescape(username, force_string=True)}', season_id=season_id)

def load_person_by_discord_id(discord_id: int, season_id: int | None = None) -> Person:
    return load_person(f'p.discord_id = {discord_id}', season_id=season_id)

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

def maybe_load_person_by_discord_id(discord_id: int | None) -> Person | None:
    if discord_id is None:
        return None
    ps, _ = load_people(f'p.discord_id = {discord_id}')
    return guarantee.at_most_one(ps)

def maybe_load_person_by_tappedout_name(username: str) -> Person | None:
    ps, _ = load_people(f'p.tappedout_username = {sqlescape(username)}')
    return guarantee.at_most_one(ps)

def maybe_load_person_by_mtggoldfish_name(username: str) -> Person | None:
    ps, _ = load_people(f'p.mtggoldfish_username = {sqlescape(username)}')
    return guarantee.at_most_one(ps)

def load_person(where: str, season_id: int | None = None) -> Person:
    people, _ = load_people(where, season_id=season_id)
    if len(people) == 0:  # We didn't find an entry for that person with decks, what about without?
        person = load_person_statless(where, season_id)
    else:
        person = guarantee.exactly_one(people)
    set_achievements([person], season_id)
    return person

# Sometimes (person detail page) we want to load what we know about a person even though they had no decks in the specified season.
def load_person_statless(where: str = 'TRUE', season_id: int | None = None) -> Person:
    person_query = query.person_query()
    sql = f"""
        SELECT
            p.id,
            {person_query} AS name,
            p.mtgo_username,
            p.tappedout_username,
            p.mtggoldfish_username,
            p.discord_id,
            p.elo,
            p.locale
        FROM
            person AS p
        WHERE
            {where}
        """
    people = [Person(r) for r in db().select(sql)]
    for p in people:
        p.season_id = season_id
    return guarantee.exactly_one(people)

# Note: This only loads people who have decks in the specified season.
def load_people(where: str = 'TRUE',
                order_by: str = 'num_decks DESC, p.name',
                limit: str = '',
                season_id: str | int | None = None) -> tuple[Sequence[Person], int]:
    person_query = query.person_query()
    season_join = query.season_join() if season_id else ''
    season_query = query.season_query(season_id, 'season.season_id')
    sql = f"""
        SELECT
            p.id,
            {person_query} AS name,
            p.mtgo_username,
            p.tappedout_username,
            p.mtggoldfish_username,
            p.discord_id,
            p.elo,
            p.locale,
            p.banned,
            SUM(1) AS num_decks,
            SUM(dc.wins) AS wins,
            SUM(dc.losses) AS losses,
            SUM(dc.draws) AS draws,
            SUM(dc.wins - dc.losses) AS record,
            SUM(CASE WHEN dc.wins >= 5 AND dc.losses = 0 AND d.source_id IN (SELECT id FROM source WHERE name = 'League') THEN 1 ELSE 0 END) AS perfect_runs,
            SUM(CASE WHEN d.finish = 1 THEN 1 ELSE 0 END) AS tournament_wins,
            SUM(CASE WHEN d.finish <= 8 THEN 1 ELSE 0 END) AS tournament_top8s,
            IFNULL(ROUND((SUM(dc.wins) / NULLIF(SUM(dc.wins + dc.losses), 0)) * 100, 1), '') AS win_percent,
            SUM(DISTINCT CASE WHEN d.competition_id IS NOT NULL THEN 1 ELSE 0 END) AS num_competitions,
            COUNT(*) OVER () AS total
        FROM
            person AS p
        LEFT JOIN
            deck AS d ON d.person_id = p.id
        LEFT JOIN
            deck_cache AS dc ON d.id = dc.deck_id
        {season_join}
        WHERE
            ({where}) AND ({season_query})
        GROUP BY
            p.id
        ORDER BY
            {order_by}
        {limit}
    """
    rs = db().select(sql)
    people = [Person({k: v for k, v in r.items() if k != 'total'}) for r in rs]
    for p in people:
        p.season_id = season_id
    return people, 0 if not rs else rs[0]['total']

def seasons_active(person_id: int) -> list[int]:
    sql = f"""
        SELECT
            DISTINCT season.season_id
        FROM
            deck AS d
        {query.season_join()}
        WHERE
            d.person_id = {person_id}
        ORDER BY
            season.season_id
    """
    return db().values(sql)

def preaggregate() -> None:
    achievements.preaggregate_achievements()
    preaggregate_head_to_head()

def preaggregate_head_to_head() -> None:
    table = '_head_to_head_stats'
    sql = """
        CREATE TABLE IF NOT EXISTS _new{table} (
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
            season.season_id,
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
            season.season_id
    """.format(table=table, season_join=query.season_join())
    preaggregation.preaggregate(table, sql)

@retry_after_calling(achievements.preaggregate_achievements)
def set_achievements(people: list[Person], season_id: int | None = None) -> None:
    people_by_id = {person.id: person for person in people}
    sql = achievements.load_query(people_by_id, season_id)
    results = [Container(r) for r in db().select(sql)]
    for result in results:
        people_by_id[result['id']].num_achievements = len([k for k, v in result.items() if k != 'id' and v > 0])
        people_by_id[result['id']].achievements = result
        people_by_id[result['id']].achievements.pop('id')

@retry_after_calling(preaggregate_head_to_head)
def load_head_to_head(person_id: int, where: str = 'TRUE', order_by: str = 'num_matches DESC, record DESC, win_percent DESC, wins DESC, opp_mtgo_username', limit: str = '', season_id: int | None = None) -> tuple[Sequence[Container], int]:
    season_query = query.season_query(season_id)
    sql = f"""
        SELECT
            hths.person_id AS id,
            LOWER(opp.mtgo_username) AS opp_mtgo_username,
            SUM(num_matches) AS num_matches,
            SUM(wins) - SUM(losses) AS record,
            SUM(wins) AS wins,
            SUM(losses) AS losses,
            SUM(draws) AS draws,
            IFNULL(ROUND((SUM(wins) / NULLIF(SUM(wins + losses), 0)) * 100, 1), '') AS win_percent,
            COUNT(*) OVER () AS total
        FROM
            _head_to_head_stats AS hths
        INNER JOIN
            person AS opp ON hths.opponent_id = opp.id
        WHERE
            ({where}) AND (hths.person_id = {person_id}) AND ({season_query})
        GROUP BY
            hths.person_id,
            hths.opponent_id
        ORDER BY
            {order_by}
        {limit}
    """
    rs = db().select(sql)
    return [Container({k: v for k, v in r.items() if k != 'total'}) for r in rs], 0 if not rs else rs[0]['total']

def associate(d: deck.Deck, discord_id: int) -> int:
    person_id = db().value('SELECT person_id FROM deck WHERE id = %s', [d.id], fail_on_missing=True)
    sql = 'UPDATE person SET discord_id = %s WHERE id = %s'
    return db().execute(sql, [discord_id, person_id])

def is_allowed_to_retire(deck_id: int | None, discord_id: int | None) -> bool:
    if not deck_id:
        return False
    if not discord_id:
        return True
    person = maybe_load_person_by_discord_id(discord_id)
    if person is None:
        return True
    return any(int(deck_id) == deck.id for deck in person.decks)

def get_or_insert_person_id(mtgo_username: str | None, tappedout_username: str | None, mtggoldfish_username: str | None) -> int:
    sql = 'SELECT id FROM person WHERE LOWER(mtgo_username) = LOWER(%s) OR LOWER(tappedout_username) = LOWER(%s) OR LOWER(mtggoldfish_username) = LOWER(%s)'
    person_id = db().value(sql, [mtgo_username, tappedout_username, mtggoldfish_username])
    if person_id:
        return person_id
    sql = 'INSERT INTO person (mtgo_username, tappedout_username, mtggoldfish_username) VALUES (%s, %s, %s)'
    return db().insert(sql, [mtgo_username, tappedout_username, mtggoldfish_username])

def load_aliases() -> list[Container]:
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

def load_notes(person_id: int | None = None) -> list[Container]:
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
        raise AlreadyExistsException(f'Player with mtgo username {mtgo_username} already has discord id {p.discord_id}, cannot add {discord_id}')
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
    logger.warning(f'Squashing {p1id} and {p2id} on {col1} and {col2}')
    db().begin('squash')
    new_value = db().value(f'SELECT {col2} FROM person WHERE id = %s', [p2id])
    db().execute('UPDATE deck SET person_id = %s WHERE person_id = %s', [p1id, p2id])
    db().execute('DELETE FROM person WHERE id = %s', [p2id])
    db().execute(f'UPDATE person SET {col2} = %s WHERE id = %s', [new_value, p1id])
    db().commit('squash')

def set_locale(person_id: int, locale: str) -> None:
    db().execute('UPDATE person SET locale = %s WHERE id = %s', [locale, person_id])

def load_sorters() -> list[Person]:
    sql = f"""
        SELECT
            p.id,
            {query.person_query()} AS name,
            COUNT(DISTINCT deck_id) AS num_decks_sorted,
            MAX(changed_date) AS last_sorted,
            CASE
                WHEN
                    COUNT(*) > 1
                THEN
                    ROUND(COUNT(DISTINCT deck_id) / ((MAX(changed_date) - MIN(changed_date)) / 60 / 60 / 24))
                ELSE
                    0
            END AS sorted_per_day
        FROM
            person AS p
        INNER JOIN
            deck_archetype_change AS dac ON p.id = dac.person_id
        INNER JOIN
            deck AS d ON d.id = dac.deck_id
        GROUP BY
            p.id
        ORDER BY
            COUNT(*) DESC,
            p.mtgo_username
    """
    sorters = []
    for r in db().select(sql):
        sorter = Person(r)
        sorter.last_sorted = dtutil.ts2dt(sorter['last_sorted'])
        sorters.append(sorter)
    return sorters

def ban(person_id: int) -> int:
    sql = 'UPDATE person SET banned = TRUE WHERE id = %s'
    return db().execute(sql, [person_id])

def unban(person_id: int) -> int:
    sql = 'UPDATE person SET banned = FALSE WHERE id = %s'
    return db().execute(sql, [person_id])
