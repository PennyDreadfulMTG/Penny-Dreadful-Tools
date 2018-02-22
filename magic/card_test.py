from magic import card


def test_canonicalize():
    assert card.canonicalize('Jötun Grunt') == 'jotun grunt'
    assert card.canonicalize('Séance') == 'seance'
    assert card.canonicalize('Far/Away') == 'far // away'
    assert card.canonicalize('Dark Ritual') == 'dark ritual'
