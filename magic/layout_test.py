from magic import layout


def test_front_card_is_not_playable() -> None:
    assert not layout.is_playable_layout('front_card')
    assert 'front_card' not in layout.uses_canonical_namespace()
