from discord.ext import commands

from discordbot.command import MtgContext
from shared import repo


@commands.command(aliases=['gbug'], hidden=True)
async def gatherlingbug(ctx: MtgContext, *, text: str) -> None:
    """Report a Gatherling bug."""
    issue = repo.create_issue(text, str(ctx.author), 'Discord', 'PennyDreadfulMTG/gatherling')
    if issue is None:
        await ctx.send('Report Gatherling issues at <https://github.com/PennyDreadfulMTG/gatherling/issues/new>')
    else:
        await ctx.send('Issue has been reported at <{url}>'.format(url=issue.html_url))
