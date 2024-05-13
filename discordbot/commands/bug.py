from interactions import Client, Extension
from interactions.models import OptionType, slash_command, slash_option

from discordbot.command import MtgContext
from shared import repo


class Bug(Extension):
    @slash_command()
    @slash_option('title', 'One sentence description of the issue', OptionType.STRING, required=True)
    @slash_option('body', 'More info', OptionType.STRING)
    async def bug(self, ctx: MtgContext, title: str, body: str | None = None) -> None:
        """Report a bug/task for the Penny Dreadful Tools team. For Magic Online bugs see `/modobug`."""
        text = title
        if body:
            text += f'\n\n{body}'
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
        text = title
        if body:
            text += f'\n\n{body}'
        issue = repo.create_issue(text, str(ctx.author), 'Discord', 'PennyDreadfulMTG/gatherling')
        if issue is None:
            await ctx.send('Report Gatherling issues at <https://github.com/PennyDreadfulMTG/gatherling/issues/new>')
        else:
            await ctx.send(f'Issue has been reported at <{issue.html_url}>')

def setup(bot: Client) -> None:
    Bug(bot)
