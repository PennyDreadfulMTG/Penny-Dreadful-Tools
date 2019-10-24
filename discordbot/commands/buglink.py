from discord.ext import commands

from discordbot.command import MtgContext
from magic import fetcher
from magic.models import Card


@commands.command(aliases=['bl'])
async def buglink(ctx: MtgContext, *, c: Card) -> None:
    """Link to the modo-bugs page for a card."""
    base_url = 'https://github.com/PennyDreadfulMTG/modo-bugs/issues'
    if c is None:
        await ctx.send(base_url)
        return
    msg = '<{base_url}?utf8=%E2%9C%93&q=is%3Aissue+%22{name}%22>'.format(base_url=base_url, name=fetcher.internal.escape(c.name))
    if not c.bugs or len(c.bugs) == 0:
        msg = "I don't know of a bug for {name} but here's the link: {link}".format(name=c.name, link=msg)
    await ctx.send(msg)
