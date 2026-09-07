import pytest

from shared import configuration


@pytest.mark.parametrize(
    ('test_guild_id', 'expected'),
    [
        (0, [456]),
        (123, [123]),
    ],
)
def test_discord_command_scopes_use_test_guild_when_configured(monkeypatch: pytest.MonkeyPatch, test_guild_id: int, expected: list[int]) -> None:
    monkeypatch.setattr(configuration.discord_test_guild_id, 'get', lambda: test_guild_id)

    assert configuration.discord_command_scopes(456) == expected
