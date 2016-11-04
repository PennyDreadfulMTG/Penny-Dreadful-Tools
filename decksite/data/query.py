def date_query():
    return "CASE WHEN c.competition_type_id IN (SELECT id FROM competition_type WHERE name = 'Gatherling') THEN c.end_date ELSE d.created_date END"

def person_query(table='p'):
    return 'IFNULL(IFNULL({table}.name, LOWER({table}.mtgo_username)), LOWER({table}.tappedout_username))'.format(table=table)
