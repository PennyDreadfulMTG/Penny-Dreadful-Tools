import translation

def test_translate():
    d = { 'x': 100, 'user': 'bakert99' }
    t = translation.translate(translation.TAPPED_OUT, d)
    assert(t['x'] == 100)
    assert(t['user'] == 'bakert99')
    assert(t['person'] == 'bakert99')
