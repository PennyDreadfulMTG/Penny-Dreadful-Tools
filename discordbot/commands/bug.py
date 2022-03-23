from typing import Optional

from dis_snek import Scale, Snake
from dis_snek.models import CMD_BODY, OptionTypes, message_command, slash_command, slash_option

from discordbot.command import MtgContext
from shared import repo


class Bug(Scale):
    @slash_command('bug')
    @slash_option('title', 'One sentence description of the issue', OptionTypes.STRING, required=True)
    @slash_option('body', 'More info', OptionTypes.STRING)
    async def bug(self, ctx: MtgContext, title: str, body: Optional[str] = None) -> None:
        """Report a bug/task for the Penny Dreadful Tools team. For Magic Online bugs see `/modobug`."""
        text = title
        if body:
            text += f'\n\n{body}'
        issue = repo.create_issue(text, str(ctx.author))
        if issue is None:
            await ctx.send('Report issues at <https://github.com/PennyDreadfulMTG/Penny-Dreadful-Tools/issues/new>')
        else:
            await ctx.send('Issue has been reported at <{url}>'.format(url=issue.html_url))

    @message_command('gbug')
    async def gatherlingbug(ctx: MtgContext, text: CMD_BODY) -> None:
        """Report a Gatherling bug."""
        issue = repo.create_issue(text, str(ctx.author), 'Discord', 'PennyDreadfulMTG/gatherling')
        if issue is None:
            await ctx.send('Report Gatherling issues at <https://github.com/PennyDreadfulMTG/gatherling/issues/new>')
        else:
            await ctx.send('Issue has been reported at <{url}>'.format(url=issue.html_url))

def setup(bot: Snake) -> None:
    Bug(bot)
