import os

from anyascii import anyascii
from whoosh.fields import NUMERIC, STORED, TEXT, Schema
from whoosh.index import FileIndex, create_in, open_dir

from magic import fetcher, layout, multiverse
from magic.models import Card
from magic.whoosh_constants import WhooshConstants


class WhooshWriter:
    def __init__(self) -> None:
        self.schema = Schema(id=NUMERIC(unique=True, stored=True), canonical_name=STORED(), name=STORED(), name_tokenized=TEXT(stored=False, analyzer=WhooshConstants.tokenized_analyzer), name_stemmed=TEXT(stored=False, analyzer=WhooshConstants.stem_analyzer), name_normalized=TEXT(stored=False, analyzer=WhooshConstants.normalized_analyzer, field_boost=100.0), playable=STORED())

    def rewrite_index(self, cards: list[Card]) -> None:
        print(f'Rewriting index in {WhooshConstants.index_dir}')
        ensure_dir_exists(WhooshConstants.index_dir)
        ix = create_in(WhooshConstants.index_dir, self.schema)
        update_index(ix, cards)

    def update_card(self, card: Card) -> None:
        ix = open_dir(WhooshConstants.index_dir)
        update_index(ix, [card])

def ensure_dir_exists(directory: str) -> None:
    if not os.path.exists(directory):
        os.makedirs(directory)

def update_index(index: FileIndex, cards: list[Card]) -> None:
    writer = index.writer()
    # Exclude cards that don't use the canonical card namespace (tokens, art series, etc.)
    # to avoid name conflicts with real cards. Non-playable cards that do use canonical names
    # (vanguard, schemes, etc.) are included and tagged with playable=False so search can
    # fall back to them only when no playable card matches.
    cards = [c for c in cards if layout.LAYOUTS.get(c.layout, layout.Layout()).uses_canonical_namespace]
    for card in cards:
        playable = layout.is_playable_layout(card.layout)
        names = list(card.names)
        if card.flavor_names:
            names.extend(card.flavor_names.split('|'))
        if card.name not in names:
            names.append(card.name)  # Split and aftermath cards
        if card.name.startswith('The '):
            names.append(card.name.replace('The ', ''))
        asciiname = anyascii(card.name)
        if asciiname != card.name:
            names.append(asciiname)
        for name in dict.fromkeys(names):
            document = {}
            document['id'] = card.id
            document['name'] = name
            document['canonical_name'] = card.name
            document['name_tokenized'] = name
            document['name_stemmed'] = name
            document['name_normalized'] = name
            document['playable'] = playable
            writer.update_document(**document)
    writer.commit()

def reindex() -> None:
    writer = WhooshWriter()
    cs = multiverse.get_all_cards()
    for line in fetcher.card_aliases():
        if not line:
            continue
        alias, name = line
        for c in cs:
            if c.name == name:
                c.names.append(alias)
    writer.rewrite_index(cs)

def reindex_specific_cards(cs: list[Card]) -> None:
    writer = WhooshWriter()
    for c in cs:
        writer.update_card(c)
