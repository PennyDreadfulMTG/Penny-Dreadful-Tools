from discord.ext import commands

from discordbot.command import MtgContext
from shared import repo


@commands.command()
async def bug(ctx: MtgContext, *, text: str) -> None:
    """Report a bug/task for the Penny Dreadful Tools team. For Magic Online bugs see `!modobug`."""
    issue = repo.create_issue(text, ctx.author)
    if issue is None:
        await ctx.send('Report issues at <https://github.com/PennyDreadfulMTG/Penny-Dreadful-Tools/issues/new>')
    else:
        await ctx.send('Issue has been reported at <{url}>'.format(url=issue.html_url))
