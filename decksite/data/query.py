def person_query(table='p'):
    return 'LOWER(IFNULL(IFNULL({table}.name, {table}.mtgo_username), {table}.tappedout_username))'.format(table=table)
