TAPPEDOUT = {
    'date_updated': 'created_date', # We'll store this the first time as the closest appromxiation we have to the created date.
    'user': 'tappedout_username',
}

def translate(mappings, data):
    result = data.copy()
    for k, v in data.items():
        our_key = mappings.get(k)
        if our_key:
            result[our_key] = v
    return result
