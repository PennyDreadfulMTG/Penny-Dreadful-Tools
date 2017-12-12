from magic import rotation
from shared.container import Container
from shared.database import sqlescape

from decksite.data import deck, guarantee, query
from decksite.database import db

def load_person(person):
    try:
        person_id = int(person)
        username = "'{person}'".format(person=person)
    except ValueError:
        person_id = 0
        username = sqlescape(person)
    return guarantee.exactly_one(load_people('p.id = {person_id} OR p.mtgo_username = {username}'.format(person_id=person_id, username=username)))

def load_people(where='1 = 1'):
    sql = """
        SELECT p.id, {person_query} AS name,

        COUNT(d.id) AS `all_num_decks`,
        SUM(d.wins) AS `all_wins`,
        SUM(d.losses) AS `all_losses`,
        SUM(d.draws) AS `all_draws`,
        IFNULL(ROUND((SUM(d.wins) / SUM(d.wins + d.losses)) * 100, 1), '') AS `all_win_percent`,
        SUM(CASE WHEN d.competition_id IS NOT NULL THEN 1 ELSE 0 END) AS `all_num_competitions`,

        SUM(CASE WHEN d.created_date >= %s THEN 1 ELSE 0 END) AS `season_num_decks`,
        SUM(CASE WHEN d.created_date >= %s THEN wins ELSE 0 END) AS `season_wins`,
        SUM(CASE WHEN d.created_date >= %s THEN losses ELSE 0 END) AS `season_losses`,
        SUM(CASE WHEN d.created_date >= %s THEN draws ELSE 0 END) AS `season_draws`,
        IFNULL(ROUND((SUM(CASE WHEN d.created_date >= %s THEN wins ELSE 0 END) / SUM(CASE WHEN d.created_date >= %s THEN wins ELSE 0 END + CASE WHEN d.created_date >= %s THEN losses ELSE 0 END)) * 100, 1), '') AS `season_win_percent`,
        SUM(CASE WHEN d.created_date >= %s AND d.competition_id IS NOT NULL THEN 1 ELSE 0 END) AS `season_num_competitions`

        FROM person AS p
        LEFT JOIN deck AS d ON p.id = d.person_id
        WHERE {where}
        GROUP BY p.id
        ORDER BY `season_num_decks` DESC, `all_num_decks` DESC, name
    """.format(person_query=query.person_query(), where=where)
    people = [Person(r) for r in db().execute(sql, [int(rotation.last_rotation().timestamp())] * 8)]
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
            SUM(CASE WHEN ct.name = 'Gatherling' THEN 1 ELSE 0 END) AS tournament_entries,
            SUM(CASE WHEN d.finish = 1 AND ct.name = 'Gatherling' THEN 1 ELSE 0 END) AS tournament_wins,
            SUM(CASE WHEN ct.name = 'League' THEN 1 ELSE 0 END) AS league_entries,
            SUM(CASE WHEN d.wins >= 5 AND d.losses = 0 AND ct.name = 'League' THEN 1 ELSE 0 END) AS perfect_runs
        FROM
            person AS p
        LEFT JOIN
            deck AS d ON d.person_id = p.id
        LEFT JOIN
            competition AS c ON c.id = d.competition_id
        LEFT JOIN
            competition_type AS ct ON ct.id = c.competition_type_id
        WHERE
            p.id IN ({ids})
        GROUP BY
            p.id
    """.format(ids=', '.join(str(k) for k in people_by_id.keys()))
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
            {person_query} AS opp_mtgo_username,
            SUM(CASE WHEN dm.games > opp.games THEN 1 ELSE 0 END) AS wins,
            SUM(CASE WHEN dm.games < opp.games THEN 1 ELSE 0 END) AS losses,
            SUM(CASE WHEN dm.games = opp.games THEN 1 ELSE 0 END) AS draws,
            IFNULL(ROUND((SUM(CASE WHEN dm.games > opp.games THEN 1 ELSE 0 END) / SUM(CASE WHEN dm.games <> opp.games THEN 1 ELSE 0 END)) * 100, 1), '') AS win_percent
        FROM
            person AS p
        INNER JOIN
            deck AS d ON p.id = d.person_id
        INNER JOIN
            deck_match AS dm ON dm.deck_id = d.id
        INNER JOIN
            deck_match AS opp ON dm.match_id = opp.match_id AND dm.deck_id <> opp.deck_id
        INNER JOIN
            deck AS opp_deck ON opp.deck_id = opp_deck.id
        INNER JOIN
            person AS opp_person ON opp_deck.person_id = opp_person.id
        WHERE
            p.id IN ({ids})
        GROUP BY
            p.id, opp_person.id
        ORDER BY
            p.id, num_matches DESC, SUM(d.wins) - SUM(d.losses) DESC, win_percent DESC, SUM(d.wins) DESC
    """.format(person_query=query.person_query('opp_person'), ids=', '.join(str(k) for k in people_by_id.keys()))
    results = [Container(r) for r in db().execute(sql)]
    for result in results:
        people_by_id[result.id].head_to_head = people_by_id[result.id].get('head_to_head', []) + [result]

def associate(d, discord_id):
    person = guarantee.exactly_one(load_people('d.id = {deck_id}'.format(deck_id=sqlescape(d.id))))
    sql = 'UPDATE person SET discord_id = ? WHERE id = ?'
    return db().execute(sql, [discord_id, person.id])

def is_allowed_to_retire(deck_id, discord_id):
    people = load_people('p.discord_id = {discord_id}'.format(discord_id=sqlescape(discord_id)))
    if len(people) == 0:
        return True
    return any(int(deck_id) == deck.id for deck in people[0].decks)

class Person(Container):
    pass
