from typing import List

import shared.fetcher_internal as internal


def search_scryfall(query):
    """Returns a tuple. First member is an integer indicating how many cards match the query total,
       second member is a list of card names up to the maximum that could be fetched in a timely fashion."""
    if query == '':
        return False, []
    print(f'Searching scryfall for `{query}`')
    result_json = internal.fetch_json('https://api.scryfall.com/cards/search?q=' + internal.escape(query), character_encoding='utf-8')
    if 'code' in result_json.keys(): # The API returned an error
        if result_json['status'] == 404: # No cards found
            return False, []
        print('Error fetching scryfall data:\n', result_json)
        return False, []
    for warning in result_json.get('warnings', []): #scryfall-provided human-readable warnings
        print(warning)
    result_data = result_json['data']
    result_data.sort(key=lambda x: x['legalities']['penny'])

    def get_frontside(scr_card):
        """If card is transform, returns first name. Otherwise, returns name.
        This is to make sure cards are later found in the database"""
        #not sure how to handle meld cards
        if scr_card['layout'] in ['transform', 'flip']:
            return scr_card['card_faces'][0]['name']
        return scr_card['name']
    result_cardnames = [get_frontside(obj) for obj in result_data]
    return result_json['total_cards'], result_cardnames, result_json.get('warnings', [])

def catalog_cardnames() -> List[str]:
    result_json = internal.fetch_json('https://api.scryfall.com/catalog/card-names')
    names: List[str] = result_json['data']
    for n in names:
        if ' // ' in n:
            names.extend(n.split(' // '))
    return names
