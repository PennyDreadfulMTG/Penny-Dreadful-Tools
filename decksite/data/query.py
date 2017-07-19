def person_query(table='p'):
    return 'LOWER(IFNULL(IFNULL(IFNULL({table}.name, {table}.mtgo_username), {table}.mtggoldfish_username), {table}.tappedout_username))'.format(table=table)
