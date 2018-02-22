from decksite import translation


def test_translate():
    d = {'x': 100, 'user': 'myusername'}
    t = translation.translate(translation.TAPPEDOUT, d)
    assert t['x'] == 100
    assert t['tappedout_username'] == 'myusername'
