from decksite import translation
from decksite.data.deck import RawDeckDescription

def test_translate() -> None:
    d: RawDeckDescription = {'score': 100, 'user': 'myusername'}
    t = translation.translate(translation.TAPPEDOUT, d)
    assert t['score'] == 100
    assert t['tappedout_username'] == 'myusername'
