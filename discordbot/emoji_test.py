from discordbot import emoji
from shared.container import Container


def test_info_emoji() -> None:
    r = emoji.info_emoji(Container({'name': 'Island', 'bugs': []}), verbose=False, show_legality=True)
    assert r == ':white_check_mark:'
    r = emoji.info_emoji(Container({'name': 'Black Lotus', 'bugs': []}), verbose=True, show_legality=True)
    assert r == ':no_entry_sign: (not legal in PD)'
    r = emoji.info_emoji(Container({'name': 'Ice Cauldron', 'bugs': [{}, {}]}), verbose=False, show_legality=False)
    assert r == ':beetle:'
    r = emoji.info_emoji(Container({'name': 'Mountain', 'bugs': []}), verbose=False, show_legality=False)
    assert r == ''
    r = emoji.info_emoji(Container({'name': 'Plains', 'bugs': [{}]}), verbose=False, show_legality=True)
    assert r == ':white_check_mark::beetle:'
    r = emoji.info_emoji(Container({'name': 'Force of Will', 'bugs': [{}]}), verbose=False, show_legality=True)
    assert r == ':no_entry_sign::beetle:'
