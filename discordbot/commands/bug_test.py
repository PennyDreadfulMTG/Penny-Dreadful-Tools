from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from discordbot.commands import bug


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ('callback', 'repository_args'),
    [
        (bug.Bug.bug.callback, ()),
        (bug.Bug.gatherlingbug.callback, ('Discord', 'PennyDreadfulMTG/gatherling')),
    ],
)
async def test_bug_commands_replace_discord_mentions_with_names(
    monkeypatch: pytest.MonkeyPatch,
    callback: object,
    repository_args: tuple[str, ...],
) -> None:
    guild = SimpleNamespace(
        get_channel=Mock(side_effect=lambda channel_id: SimpleNamespace(name='bot-dev') if channel_id == 123 else None),
        get_member=Mock(side_effect=lambda member_id: SimpleNamespace(display_name='Silas') if member_id == 456 else None),
        get_role=Mock(side_effect=lambda role_id: SimpleNamespace(name='Developers') if role_id == 789 else None),
    )
    author = Mock(mention='<@456>')
    ctx = SimpleNamespace(guild=guild, author=author, send=AsyncMock())
    issue = SimpleNamespace(html_url='https://example.com/issues/1')
    create_issue = Mock(return_value=issue)
    monkeypatch.setattr(bug.repo, 'create_issue', create_issue)

    await callback(  # type: ignore[operator]
        SimpleNamespace(),
        ctx,
        'Failure in <#123> reported by <@456>',
        'Nickname <@!456>, role <@&789>, unknown <@999>.',
    )

    create_issue.assert_called_once_with(
        'Failure in #bot-dev reported by @Silas\n\nNickname @Silas, role @Developers, unknown <@999>.',
        str(author),
        *repository_args,
    )
    ctx.send.assert_awaited_once_with('Issue has been reported at <https://example.com/issues/1>')
