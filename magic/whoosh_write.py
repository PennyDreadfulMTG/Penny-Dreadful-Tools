import os
from typing import List

from whoosh.fields import NUMERIC, STORED, TEXT, Schema
from whoosh.index import FileIndex, create_in, open_dir

from magic import multiverse, fetcher
from magic.models import Card
from magic.whoosh_constants import WhooshConstants


class WhooshWriter():
    def __init__(self) -> None:
        self.schema = Schema(id=NUMERIC(unique=True, stored=True), canonical_name=STORED(), name=STORED(), name_tokenized=TEXT(stored=False, analyzer=WhooshConstants.tokenized_analyzer), name_stemmed=TEXT(stored=False, analyzer=WhooshConstants.stem_analyzer), name_normalized=TEXT(stored=False, analyzer=WhooshConstants.normalized_analyzer, field_boost=100.0))

    def rewrite_index(self, cards: List[Card]) -> None:
        print('Rewriting index in {d}'.format(d=WhooshConstants.index_dir))
        ensure_dir_exists(WhooshConstants.index_dir)
        ix = create_in(WhooshConstants.index_dir, self.schema)
        update_index(ix, cards)

    # pylint: disable=no-self-use
    def update_card(self, card: Card) -> None:
        ix = open_dir(WhooshConstants.index_dir)
        update_index(ix, [card])

def ensure_dir_exists(directory: str) -> None:
    if not os.path.exists(directory):
        os.makedirs(directory)

def update_index(index: FileIndex, cards: List[Card]) -> None:
    writer = index.writer()
    # We exclude tokens here because they can have the exact same name as cards.
    # We exclude emblems here to stop them showing up as
    cards = [c for c in cards if multiverse.is_playable_layout(c.layout)]
    for card in cards:
        names = card.names
        if card.name not in names:
            names.append(card.name) # Split and aftermath cards
        for name in names:
            document = {}
            document['id'] = card.id
            document['name'] = name
            document['canonical_name'] = card.name
            document['name_tokenized'] = name
            document['name_stemmed'] = name
            document['name_normalized'] = name
            writer.update_document(**document)
    writer.commit()

def reindex() -> None:
    writer = WhooshWriter()
    cs = multiverse.get_all_cards()
    for alias, name in fetcher.card_aliases():
        for c in cs:
            if c.name == name:
                c.names.append(alias)
    writer.rewrite_index(cs)

def reindex_specific_cards(cs: List[Card]) -> None:
    writer = WhooshWriter()
    for c in cs:
        writer.update_card(c)
