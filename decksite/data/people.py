from munch import Munch

from shared.database import sqlescape

from decksite.database import db

def load_person(person_id):
    return load_people('p.id = {id}'.format(id=sqlescape(person_id)))[0]

def load_people(where_clause='1 = 1'):
    sql = """
        SELECT id, {person_query} AS name
        FROM person AS p
        WHERE {where_clause}
        ORDER BY name
    """.format(person_query=person_query(), where_clause=where_clause)
    return [Person(r) for r in db().execute(sql)]

def person_query(table='p'):
    return 'IFNULL(IFNULL({table}.name, LOWER({table}.mtgo_username)), LOWER({table}.tappedout_username))'.format(table=table)

class Person(Munch):
    pass
