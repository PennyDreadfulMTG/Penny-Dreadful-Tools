def person_query(table='p'):
    return 'IFNULL(IFNULL({table}.name, LOWER({table}.mtgo_username)), LOWER({table}.tappedout_username))'.format(table=table)
