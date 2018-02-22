import os

from whoosh.fields import NUMERIC, STORED, TEXT, Schema
from whoosh.index import create_in, open_dir

from shared.whoosh_constants import WhooshConstants


class WhooshWriter():
    def __init__(self):
        self.schema = Schema(id=NUMERIC(unique=True, stored=True), name=STORED(), name_tokenized=TEXT(stored=False, analyzer=WhooshConstants.tokenized_analyzer), name_stemmed=TEXT(stored=False, analyzer=WhooshConstants.stem_analyzer), name_normalized=TEXT(stored=False, analyzer=WhooshConstants.normalized_analyzer, field_boost=100.0))
    def rewrite_index(self, cards):
        print("Rewriting index in {d}".format(d=WhooshConstants.index_dir))
        ensure_dir_exists(WhooshConstants.index_dir)
        ix = create_in(WhooshConstants.index_dir, self.schema)
        update_index(ix, cards)

    # pylint: disable=no-self-use
    def update_card(self, card):
        ix = open_dir(WhooshConstants.index_dir)
        update_index(ix, [card])

def ensure_dir_exists(directory):
    if not os.path.exists(directory):
        os.makedirs(directory)

def update_index(index, cards):
    writer = index.writer()
    cards = [c for c in cards if c['layout'] != 'token' and c['type'] != 'Vanguard']
    for card in cards:
        document = {}
        document['id'] = card['id']
        document['name'] = card['name']
        document['name_tokenized'] = card['name']
        document['name_stemmed'] = card['name']
        document['name_normalized'] = card['name']
        writer.update_document(**document)
    writer.commit()


# If we want to index more things like power, toughness and others
#   keys = ('cmc', 'id', 'name', 'power', 'text', 'toughness', 'type')
#           dict = {k:card[k] for k in keys}
#           to_int(dict, 'power')
#           to_int(dict, 'toughness')

#   def to_int(dict, key):
#       if key in dict and dict[key] is not None:
#           try:
#               p = int(dict[key])
#           except ValueError:
#               p = 0
#           dict[key] = p
