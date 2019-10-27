from discord.ext import commands

from discordbot.command import MtgContext
from magic import fetcher
from magic.models import Card


@commands.command(aliases=['ru', 'rule'])
async def rulings(ctx: MtgContext, *, c: Card) -> None:
    """Rulings for a card."""
    await ctx.single_card_text(c, card_rulings)


def card_rulings(c: Card) -> str:
    raw_rulings = fetcher.rulings(c.name)
    comments = [r['comment'] for r in raw_rulings]
    if len(comments) > 3:
        n = len(comments) - 2
        comments = comments[:2]
        comments.append('And {n} others.  See <https://scryfall.com/search?q=%21%22{cardname}%22#rulings>'.format(n=n, cardname=fetcher.internal.escape(c.name)))
    return '\n'.join(comments) or 'No rulings available.'
