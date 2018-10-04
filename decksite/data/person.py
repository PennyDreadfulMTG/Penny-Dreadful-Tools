from typing import List, Optional, Sequence, Union

from decksite.data import deck, query
from decksite.database import db
from shared import dtutil, guarantee
from shared.container import Container
from shared.database import sqlescape
from shared.pd_exception import AlreadyExistsException, DatabaseException
from shared_web import logger


class Person(Container):
    __decks = None
    @property
    def decks(self) -> List[deck.Deck]:
        if self.__decks is None:
            self.__decks = deck.load_decks(f'd.person_id = {self.id}', season_id=self.season_id)
        return self.__decks

def load_person(person: Union[int, str], season_id: Optional[int] = None) -> Person:
    try:
        person_id = int(person)
        username = "'{person}'".format(person=person)
    except ValueError:
        person_id = 0
        username = sqlescape(person)
    person = guarantee.exactly_one(load_people('p.id = {person_id} OR p.mtgo_username = {username} OR p.discord_id = {person_id}'.format(person_id=person_id, username=username), season_id=season_id))
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
            person AS p
        LEFT JOIN
            deck AS d ON p.id = d.person_id
        LEFT JOIN
            deck_cache AS dc ON d.id = dc.deck_id
        {season_join}
        WHERE
            ({where}) AND ({season_query})
        GROUP BY
            p.id
        ORDER BY
            {order_by}
    """.format(person_query=query.person_query(), season_join=query.season_join(), where=where, season_query=query.season_query(season_id, 'season.id'), order_by=order_by)
    people = [Person(r) for r in db().select(sql)]
    for p in people:
        p.season_id = season_id
    return people

def set_achievements(people: List[Person], season_id: int = None, retry: bool = False) -> None:
    people_by_id = {person.id: person for person in people}
    sql = """
        SELECT
            person_id AS id,
            season_id,
            tournament_entries,
            tournament_wins,
            league_entries,
            completionist,
            perfect_runs,
            perfect_run_crushes
        FROM
            _achievements AS a
        WHERE
            person_id IN ({ids}) AND ({season_query})
    """.format(ids=', '.join(str(k) for k in people_by_id.keys()), season_query=query.season_query(season_id))
    try:
        results = [Container(r) for r in db().select(sql)]
        for result in results:
            people_by_id[result['id']].num_achievements = len([k for k, v in result.items() if k != 'id' and v > 0])
            people_by_id[result['id']].achievements = result
            people_by_id[result['id']].achievements.pop('id')
    except DatabaseException as e:
        if not retry:
            print(f"Got {e} trying to set_head_to_head so trying to preaggregate. If this is happening on user time that's undesirable.")
            preaggregate_achievements()
            set_achievements(people=people, season_id=season_id, retry=True)
            return
        print(f'Failed to preaggregate. Giving up.')
        raise e

def set_head_to_head(people: List[Person], season_id: int = None, retry: bool = False) -> None:
    people_by_id = {person.id: person for person in people}
    sql = """
        SELECT
            hths.person_id AS id,
            LOWER(opp.mtgo_username) AS opp_mtgo_username,
            hths.num_matches,
            hths.wins,
            hths.losses,
            hths.draws,
            IFNULL(ROUND((wins / NULLIF(wins + losses, 0)) * 100, 1), '') AS win_percent
        FROM
            _head_to_head_stats AS hths
        INNER JOIN
            person AS opp ON hths.opponent_id = opp.id
        WHERE
            hths.person_id IN ({ids}) AND ({season_query})
        ORDER BY
            num_matches DESC,
            wins - losses DESC,
            win_percent DESC,
            wins DESC,
            opp_mtgo_username
    """.format(ids=', '.join(str(k) for k in people_by_id.keys()), season_query=query.season_query(season_id))
    try:
        results = [Container(r) for r in db().select(sql)]
        for result in results:
            people_by_id[result.id].head_to_head = people_by_id[result.id].get('head_to_head', []) + [result]
        for person in people:
            if person.get('head_to_head') is None:
                person.head_to_head = []
    except DatabaseException as e:
        if not retry:
            print(f"Got {e} trying to set_head_to_head so trying to preaggregate. If this is happening on user time that's undesirable.")
            preaggregate_head_to_head()
            set_head_to_head(people=people, season_id=season_id, retry=True)
            return
        print(f'Failed to preaggregate. Giving up.')
        raise e

def associate(d, discord_id):
    person = guarantee.exactly_one(load_people('d.id = {deck_id}'.format(deck_id=sqlescape(d.id))))
    sql = 'UPDATE person SET discord_id = %s WHERE id = %s'
    return db().execute(sql, [discord_id, person.id])

def is_allowed_to_retire(deck_id, discord_id):
    if not deck_id:
        return False
    if not discord_id:
        return True
    person = load_person_by_discord_id(discord_id)
    if person is None:
        return True
    return any(int(deck_id) == deck.id for deck in person.decks)

def load_person_by_discord_id(discord_id: Optional[int]) -> Optional[Person]:
    if discord_id is None:
        return None
    return guarantee.at_most_one(load_people('p.discord_id = {discord_id}'.format(discord_id=sqlescape(discord_id))))

def load_person_by_tappedout_name(username: str) -> Optional[Person]:
    return guarantee.at_most_one(load_people('p.tappedout_username = {username}'.format(username=sqlescape(username))))

def load_person_by_mtggoldfish_name(username: str) -> Optional[Person]:
    return guarantee.at_most_one(load_people('p.mtggoldfish_username = {username}'.format(username=sqlescape(username))))

def get_or_insert_person_id(mtgo_username: Optional[str], tappedout_username: Optional[str], mtggoldfish_username: Optional[str]) -> int:
    sql = 'SELECT id FROM person WHERE LOWER(mtgo_username) = LOWER(%s) OR LOWER(tappedout_username) = LOWER(%s) OR LOWER(mtggoldfish_username) = LOWER(%s)'
    person_id = db().value(sql, [mtgo_username, tappedout_username, mtggoldfish_username])
    if person_id:
        return person_id
    sql = 'INSERT INTO person (mtgo_username, tappedout_username, mtggoldfish_username) VALUES (%s, %s, %s)'
    return db().insert(sql, [mtgo_username, tappedout_username, mtggoldfish_username])

def load_notes() -> List[Container]:
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
        ORDER BY
            s.id,
            pn.created_date DESC
    """.format(creator_query=query.person_query('c'), subject_query=query.person_query('s'))
    notes = [Container(r) for r in db().select(sql)]
    for n in notes:
        n.created_date = dtutil.ts2dt(n.created_date)
    return notes

def add_note(creator_id: int, subject_id: int, note: str) -> None:
    sql = 'INSERT INTO person_note (created_date, creator_id, subject_id, note) VALUES (UNIX_TIMESTAMP(NOW()), %s, %s, %s)'
    db().execute(sql, [creator_id, subject_id, note])

def link_discord(mtgo_username: str, discord_id: int) -> Person:
    person_id = deck.get_or_insert_person_id(mtgo_username, None, None)
    p = load_person(person_id)
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

def is_banned(mtgo_username):
    return db().value('SELECT banned FROM person WHERE mtgo_username = %s', [mtgo_username]) == 1

def squash(p1id: int, p2id: int, col1: str, col2: str) -> None:
    logger.warning('Squashing {p1id} and {p2id} on {col1} and {col2}'.format(p1id=p1id, p2id=p2id, col1=col1, col2=col2))
    db().begin()
    new_value = db().value('SELECT {col2} FROM person WHERE id = %s'.format(col2=col2), [p2id])
    db().execute('UPDATE deck SET person_id = %s WHERE person_id = %s', [p1id, p2id])
    db().execute('DELETE FROM person WHERE id = %s', [p2id])
    db().execute('UPDATE person SET {col2} = %s WHERE id = %s'.format(col2=col2), [new_value, p1id])
    db().commit()

def preaggregate() -> None:
    preaggregate_achievements()
    preaggregate_head_to_head()

def preaggregate_achievements() -> None:
    db().execute('DROP TABLE IF EXISTS _new_achievements')
    sql = """
        CREATE TABLE IF NOT EXISTS _new_achievements (
            person_id INT NOT NULL,
            season_id INT NOT NULL,
            tournament_entries INT NOT NULL,
            tournament_wins INT NOT NULL,
            league_entries INT NOT NULL,
            completionist BOOLEAN NOT NULL,
            perfect_runs INT NOT NULL,
            perfect_run_crushes INT NOT NULL,
            PRIMARY KEY (season_id, person_id),
            FOREIGN KEY (season_id) REFERENCES season (id) ON UPDATE CASCADE ON DELETE CASCADE,
            FOREIGN KEY (person_id) REFERENCES person (id) ON UPDATE CASCADE ON DELETE CASCADE
        ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci AS
        SELECT
            p.id AS person_id,
            season.id AS season_id,
            COUNT(DISTINCT CASE WHEN ct.name = 'Gatherling' THEN d.id ELSE NULL END) AS tournament_entries,
            COUNT(DISTINCT CASE WHEN d.finish = 1 AND ct.name = 'Gatherling' THEN d.id ELSE NULL END) AS tournament_wins,
            COUNT(DISTINCT CASE WHEN ct.name = 'League' THEN d.id ELSE NULL END) AS league_entries,
            CASE WHEN COUNT(CASE WHEN d.retired = 1 THEN 1 ELSE NULL END) = 0 THEN True ELSE False END AS completionist,
            SUM(CASE WHEN ct.name = 'League' AND dc.wins >= 5 AND dc.losses THEN 1 ELSE 0 END) AS perfect_runs,
            SUM(
                CASE WHEN d.id IN
                    (
                        SELECT
                            -- MAX here is just to fool MySQL to give us the id of the deck that crushed the perfect run from an aggregate function. There is only one value to MAX.
                            MAX(CASE WHEN dm.games < odm.games AND dm.match_id IN (SELECT MAX(match_id) FROM deck_match WHERE deck_id = d.id) THEN odm.deck_id ELSE NULL END) AS deck_id
                        FROM
                            deck AS d
                        INNER JOIN
                            deck_match AS dm
                        ON
                            dm.deck_id = d.id
                        INNER JOIN
                            deck_match AS odm
                        ON
                            dm.match_id = odm.match_id AND odm.deck_id <> d.id
                        WHERE
                            d.competition_id IN ({competition_ids_by_type_select})
                        GROUP BY
                            d.id
                        HAVING
                            SUM(CASE WHEN dm.games > odm.games THEN 1 ELSE 0 END) >=4
                        AND
                            SUM(CASE WHEN dm.games < odm.games THEN 1 ELSE 0 END) = 1
                        AND
                            SUM(CASE WHEN dm.games < odm.games AND dm.match_id IN (SELECT MAX(match_id) FROM deck_match WHERE deck_id = d.id) THEN 1 ELSE 0 END) = 1
                    )
                THEN 1 ELSE 0 END
            ) AS perfect_run_crushes
        FROM
            person AS p
        LEFT JOIN
            deck AS d ON d.person_id = p.id
        LEFT JOIN
            deck_cache AS dc ON dc.deck_id = d.id
        {season_join}
        {competition_join}
        GROUP BY
            p.id,
            season.id
        HAVING
            season.id IS NOT NULL
    """.format(competition_ids_by_type_select=query.competition_ids_by_type_select('League'), season_join=query.season_join(), competition_join=query.competition_join())
    db().execute(sql)
    db().execute('DROP TABLE IF EXISTS _old_achievements')
    db().execute('CREATE TABLE IF NOT EXISTS _achievements (_ INT)') # Prevent error in RENAME TABLE below if bootstrapping.
    db().execute('RENAME TABLE _achievements TO _old_achievements, _new_achievements TO _achievements')
    db().execute('DROP TABLE IF EXISTS _old_achievements')

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
