import re

from interactions import Client, Extension, Guild
from interactions.models import OptionType, slash_command, slash_option

from discordbot.command import MtgContext
from shared import repo


def normalize_mentions(text: str, guild: Guild | None) -> str:
    if guild is None:
        return text

    def replace_mention(match: re.Match[str]) -> str:
        mention_type, snowflake = match.groups()
        discord_id = int(snowflake)
        if mention_type == '#':
            channel = guild.get_channel(discord_id)
            name = getattr(channel, 'name', None)
            prefix = '#'
        elif mention_type == '@&':
            role = guild.get_role(discord_id)
            name = role.name if role else None
            prefix = '@'
        else:
            member = guild.get_member(discord_id)
            name = member.display_name if member else None
            prefix = '@'
        return f'{prefix}{name}' if name else match.group(0)

    return re.sub(r'<(@!?|@&|#)(\d+)>', replace_mention, text)


class Bug(Extension):
    @slash_command(description='Report a bug or task for the Penny Dreadful Tools team.')
    @slash_option('title', 'One sentence description of the issue', OptionType.STRING, required=True)
    @slash_option('body', 'More info', OptionType.STRING)
    async def bug(self, ctx: MtgContext, title: str, body: str | None = None) -> None:
        """Report a bug/task for the Penny Dreadful Tools team. For Magic Online bugs see `/modobug`."""
        text = title
        if body:
            text += f'\n\n{body}'
        text = normalize_mentions(text, ctx.guild)
        issue = repo.create_issue(text, str(ctx.author))
        if issue is None:
            msg = f'{ctx.author.mention}: Unable to create an issue. Please report at <https://github.com/PennyDreadfulMTG/Penny-Dreadful-Tools/issues/new>'
            await ctx.send(msg)
        else:
            await ctx.send(f'Issue has been reported at <{issue.html_url}>')

    @slash_command('gbug', description='Report a Gatherling bug.')
    @slash_option('title', 'One sentence description of the issue', OptionType.STRING, required=True)
    @slash_option('body', 'More info', OptionType.STRING)
    async def gatherlingbug(self, ctx: MtgContext, title: str, body: str | None = None) -> None:
        """Report a Gatherling bug."""
        text = title
        if body:
            text += f'\n\n{body}'
        text = normalize_mentions(text, ctx.guild)
        issue = repo.create_issue(text, str(ctx.author), 'Discord', 'PennyDreadfulMTG/gatherling')
        if issue is None:
            await ctx.send('Report Gatherling issues at <https://github.com/PennyDreadfulMTG/gatherling/issues/new>')
        else:
            await ctx.send(f'Issue has been reported at <{issue.html_url}>')

def setup(bot: Client) -> None:
    Bug(bot)
