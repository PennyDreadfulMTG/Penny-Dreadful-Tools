import pytest

from discordbot import emoji
from magic import oracle, seasons


def emoji_params() -> list[tuple]:
    return [
        ('Island', False, True, False, 'Penny Dreadful', ':white_check_mark:'),
        ('Black Lotus', True, True, False, 'Penny Dreadful', f':no_entry_sign: (not legal in {seasons.current_season_name()})'),
        ('Ice Cauldron', False, False, True, 'Standard', ':lady_beetle:'),
        ('Mountain', False, False, False, 'Penny Dreadful', ''),
        ('Plains', False, True, True, 'Penny Dreadful AER', ':white_check_mark::lady_beetle:'),
        ('Force of Will', False, True, True, 'Penny Dreadful MID', ':no_entry_sign::lady_beetle:'),
    ]


@pytest.mark.parametrize('cardname, verbose, show_legality, bugged, legality_format, expected', emoji_params())
def test_info_emoji(cardname: str, verbose: bool, show_legality: bool, bugged: bool, legality_format: str, expected: str) -> None:
    c = oracle.load_card(cardname)
    if bugged:
        c.bugs = [{}]
    else:
        c.bugs = []

    r = emoji.info_emoji(c, verbose, show_legality, True, legality_format)
    assert r == expected
