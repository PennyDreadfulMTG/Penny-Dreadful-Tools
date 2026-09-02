from types import SimpleNamespace
from unittest.mock import Mock

from discordbot.commands.bug import normalize_mentions


def make_guild(member_name: str | None = 'silasary', channel_name: str | None = 'penny-dreadful', role_name: str | None = 'Mods') -> Mock:
    guild = Mock()
    guild.get_member.return_value = SimpleNamespace(display_name=member_name) if member_name else None
    guild.get_channel.return_value = SimpleNamespace(name=channel_name) if channel_name else None
    guild.get_role.return_value = SimpleNamespace(name=role_name) if role_name else None
    return guild


def test_normalize_user_mention() -> None:
    guild = make_guild()
    assert normalize_mentions('ping <@123456789>', guild) == 'ping @silasary'


def test_normalize_user_mention_with_bang() -> None:
    guild = make_guild()
    assert normalize_mentions('ping <@!123456789>', guild) == 'ping @silasary'


def test_normalize_channel_mention() -> None:
    guild = make_guild()
    assert normalize_mentions('see <#987654321>', guild) == 'see #penny-dreadful'


def test_normalize_role_mention() -> None:
    guild = make_guild()
    assert normalize_mentions('hey <@&111222333>', guild) == 'hey @Mods'


def test_normalize_unknown_member_falls_back_to_id() -> None:
    guild = make_guild(member_name=None)
    assert normalize_mentions('<@999>', guild) == '@999'


def test_normalize_unknown_channel_falls_back_to_id() -> None:
    guild = make_guild(channel_name=None)
    assert normalize_mentions('<#999>', guild) == '#999'


def test_normalize_unknown_role_falls_back_to_id() -> None:
    guild = make_guild(role_name=None)
    assert normalize_mentions('<@&999>', guild) == '@999'


def test_normalize_no_guild_falls_back_to_id() -> None:
    assert normalize_mentions('<@123> in <#456>', None) == '123 in 456'


def test_normalize_multiple_mentions() -> None:
    guild = make_guild()
    result = normalize_mentions('<@1> reported in <#2>', guild)
    assert result == '@silasary reported in #penny-dreadful'


def test_normalize_plain_text_unchanged() -> None:
    guild = make_guild()
    assert normalize_mentions('no mentions here', guild) == 'no mentions here'
