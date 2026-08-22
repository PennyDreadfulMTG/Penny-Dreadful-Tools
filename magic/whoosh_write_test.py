from pathlib import Path

from whoosh.index import create_in

from magic import whoosh_write
from magic.models import Card


def test_update_index_includes_card_aliases(tmp_path: Path) -> None:
    card = Card({
        'id': 1,
        'name': 'Spider-Man Noir',
        'names': 'Spider-Man Noir',
        'flavor_names': 'Kroble, Envoy of the Bog',
        'layout': 'normal',
    })
    index = create_in(tmp_path, whoosh_write.WhooshWriter().schema)
    whoosh_write.update_index(index, [card])
    with index.reader() as reader:
        documents = [fields for _, fields in reader.iter_docs()]
    assert {document['name'] for document in documents} == {
        'Spider-Man Noir',
        'Kroble, Envoy of the Bog',
    }
    assert {document['canonical_name'] for document in documents} == {'Spider-Man Noir'}
