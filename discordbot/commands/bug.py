import re

from interactions import Client, Extension, Guild
from interactions.models import OptionType, slash_command, slash_option

from discordbot.command import MtgContext
from shared import repo


def normalize_mentions(text: str, guild: Guild | None) -> str:
    def replace_mention(m: re.Match) -> str:  # type: ignore[type-arg]
        sigil, id_str = m.group(1), m.group(2)
        if guild is None:
            return id_str
        if sigil == '#':
            channel = guild.get_channel(int(id_str))
            return f'#{channel.name}' if channel and channel.name else f'#{id_str}'
        if sigil == '@&':
            role = guild.get_role(int(id_str))
            return f'@{role.name}' if role else f'@{id_str}'
        # sigil is '@' or '@!'
        member = guild.get_member(int(id_str))
        return f'@{member.display_name}' if member else f'@{id_str}'
    return re.sub(r'<([@#][!&]?)(\d+)>', replace_mention, text)


class Bug(Extension):
    @slash_command()
    @slash_option('title', 'One sentence description of the issue', OptionType.STRING, required=True)
    @slash_option('body', 'More info', OptionType.STRING)
    async def bug(self, ctx: MtgContext, title: str, body: str | None = None) -> None:
        """Report a bug/task for the Penny Dreadful Tools team. For Magic Online bugs see `/modobug`."""
        text = normalize_mentions(title, ctx.guild)
        if body:
            text += f'\n\n{normalize_mentions(body, ctx.guild)}'
        issue = repo.create_issue(text, str(ctx.author))
        if issue is None:
            msg = f'{ctx.author.mention}: Unable to create an issue. Please report at <https://github.com/PennyDreadfulMTG/Penny-Dreadful-Tools/issues/new>'
            await ctx.send(msg)
        else:
            await ctx.send(f'Issue has been reported at <{issue.html_url}>')

    @slash_command('gbug')
    @slash_option('title', 'One sentence description of the issue', OptionType.STRING, required=True)
    @slash_option('body', 'More info', OptionType.STRING)
    async def gatherlingbug(self, ctx: MtgContext, title: str, body: str | None = None) -> None:
        """Report a Gatherling bug."""
        text = normalize_mentions(title, ctx.guild)
        if body:
            text += f'\n\n{normalize_mentions(body, ctx.guild)}'
        issue = repo.create_issue(text, str(ctx.author), 'Discord', 'PennyDreadfulMTG/gatherling')
        if issue is None:
            await ctx.send('Report Gatherling issues at <https://github.com/PennyDreadfulMTG/gatherling/issues/new>')
        else:
            await ctx.send(f'Issue has been reported at <{issue.html_url}>')

def setup(bot: Client) -> None:
    Bug(bot)
