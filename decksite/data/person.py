from typing import Union

from decksite.data import deck, guarantee, query
from decksite.database import db
from magic import rotation
from shared.container import Container
from shared.database import sqlescape


class Person(Container):
    pass


def load_person(person: Union[int, str]) -> Person:
    try:
        person_id = int(person)
        username = "'{person}'".format(person=person)
    except ValueError:
        person_id = 0
        username = sqlescape(person)
    return guarantee.exactly_one(load_people('p.id = {person_id} OR p.mtgo_username = {username}'.format(person_id=person_id, username=username)))

def load_people(where='1 = 1'):
    sql = """
        SELECT
            p.id,
            {person_query} AS name,
            p.mtgo_username,
            p.tappedout_username,
            p.mtggoldfish_username,
            p.discord_id,
            p.elo,
            {all_select},
            SUM(DISTINCT CASE WHEN d.competition_id IS NOT NULL THEN 1 ELSE 0 END) AS `all_num_competitions`,
            {season_select},
            SUM(DISTINCT CASE WHEN d.created_date >= %s AND d.competition_id IS NOT NULL THEN 1 ELSE 0 END) AS `season_num_competitions`
        FROM
            person AS p
        LEFT JOIN
            deck AS d ON p.id = d.person_id
        {nwdl_join}
        WHERE
            {where}
        GROUP BY
            p.id
        ORDER BY
            `season_num_decks` DESC,
            `all_num_decks` DESC,
            name
    """.format(person_query=query.person_query(), all_select=deck.nwdl_all_select(), season_select=deck.nwdl_season_select(), nwdl_join=deck.nwdl_join(), where=where)
    people = [Person(r) for r in db().execute(sql, [int(rotation.last_rotation().timestamp())])]
    if len(people) > 0:
        set_decks(people)
        set_achievements(people)
        set_head_to_head(people)
    return people

def set_decks(people):
    people_by_id = {person.id: person for person in people}
    where = 'd.person_id IN ({ids})'.format(ids=', '.join(str(k) for k in people_by_id.keys()))
    decks = deck.load_decks(where)
    for p in people:
        p.decks = []
    for d in decks:
        people_by_id[d.person_id].decks.append(d)

def set_achievements(people):
    people_by_id = {person.id: person for person in people}
    sql = """
        SELECT
            p.id,
            COUNT(DISTINCT CASE WHEN ct.name = 'Gatherling' THEN d.id ELSE NULL END) AS tournament_entries,
            COUNT(DISTINCT CASE WHEN d.finish = 1 AND ct.name = 'Gatherling' THEN d.id ELSE NULL END) AS tournament_wins,
            COUNT(DISTINCT CASE WHEN ct.name = 'League' THEN d.id ELSE NULL END) AS league_entries,
            SUM(
                CASE WHEN d.id IN
                    (
                        SELECT
                            d.id
                        FROM
                            deck AS d
                        {competition_join}
                        LEFT JOIN
                            deck_match AS dm ON dm.deck_id = d.id
                        LEFT JOIN
                            deck_match AS odm ON odm.match_id = dm.match_id AND odm.deck_id <> d.id
                        WHERE
                            ct.name = 'League'
                        GROUP BY
                            d.id
                        HAVING
                            SUM(CASE WHEN dm.games > odm.games THEN 1 ELSE 0 END) >= 5
                        AND
                            SUM(CASE WHEN dm.games < odm.games THEN 1 ELSE 0 END) = 0
                    )
                THEN 1 ELSE 0 END
            ) AS perfect_runs,
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
                        GROUP BY d.id
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
        {competition_join}
        WHERE
            p.id IN ({ids})
        GROUP BY
            p.id
    """.format(competition_join=query.competition_join(), competition_ids_by_type_select=query.competition_ids_by_type_select('League'), ids=', '.join(str(k) for k in people_by_id.keys()))
    results = [Container(r) for r in db().execute(sql)]
    for result in results:
        people_by_id[result['id']].update(result)
        people_by_id[result['id']].achievements = len([k for k, v in result.items() if k != 'id' and v > 0])

def set_head_to_head(people):
    people_by_id = {person.id: person for person in people}
    sql = """
        SELECT
            p.id,
            COUNT(p.id) AS num_matches,
            LOWER(opp.mtgo_username) AS opp_mtgo_username,
            SUM(CASE WHEN dm.games > odm.games THEN 1 ELSE 0 END) AS wins,
            SUM(CASE WHEN dm.games < odm.games THEN 1 ELSE 0 END) AS losses,
            SUM(CASE WHEN dm.games = odm.games THEN 1 ELSE 0 END) AS draws,
            IFNULL(ROUND((SUM(CASE WHEN dm.games > odm.games THEN 1 ELSE 0 END) / NULLIF(SUM(CASE WHEN dm.games <> IFNULL(odm.games, 0) THEN 1 ELSE 0 END), 0)) * 100, 1), '') AS win_percent
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
        WHERE
            p.id IN ({ids})
        GROUP BY
            p.id, opp.id
        ORDER BY
            p.id,
            num_matches DESC,
            SUM(CASE WHEN dm.games > odm.games THEN 1 ELSE 0 END) - SUM(CASE WHEN dm.games < odm.games THEN 1 ELSE 0 END) DESC,
            win_percent DESC,
            SUM(CASE WHEN dm.games > odm.games THEN 1 ELSE 0 END) DESC,
            opp_mtgo_username
    """.format(ids=', '.join(str(k) for k in people_by_id.keys()))
    results = [Container(r) for r in db().execute(sql)]
    for result in results:
        people_by_id[result.id].head_to_head = people_by_id[result.id].get('head_to_head', []) + [result]
    for person in people:
        if person.get('head_to_head') is None:
            person.head_to_head = []

def associate(d, discord_id):
    person = guarantee.exactly_one(load_people('d.id = {deck_id}'.format(deck_id=sqlescape(d.id))))
    sql = 'UPDATE person SET discord_id = ? WHERE id = ?'
    return db().execute(sql, [discord_id, person.id])

def is_allowed_to_retire(deck_id, discord_id):
    person = load_person_by_discord_id(discord_id)
    if person is None:
        return True
    return any(int(deck_id) == deck.id for deck in person.decks)

def load_person_by_discord_id(discord_id):
    return guarantee.at_most_one(load_people('p.discord_id = {discord_id}'.format(discord_id=sqlescape(discord_id))))

def load_person_by_tappedout_name(username):
    return guarantee.at_most_one(load_people('p.tappedout_username = {username}'.format(username=sqlescape(username))))

def load_person_by_mtggoldfish_name(username):
    return guarantee.at_most_one(load_people('p.mtggoldfish_username = {username}'.format(username=sqlescape(username))))

def get_or_insert_person_id(mtgo_username, tappedout_username, mtggoldfish_username):
    sql = 'SELECT id FROM person WHERE LOWER(mtgo_username) = LOWER(%s) OR LOWER(tappedout_username) = LOWER(%s) OR LOWER(mtggoldfish_username) = LOWER(%s)'
    person_id = db().value(sql, [mtgo_username, tappedout_username, mtggoldfish_username])
    if person_id:
        return person_id
    sql = 'INSERT INTO person (mtgo_username, tappedout_username, mtggoldfish_username) VALUES (%s, %s, %s)'
    return db().insert(sql, [mtgo_username, tappedout_username, mtggoldfish_username])
