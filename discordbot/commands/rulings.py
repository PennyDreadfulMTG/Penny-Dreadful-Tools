from interactions.client import Client
from interactions.models import Extension, auto_defer, slash_command

from discordbot.command import MtgContext, slash_card_option
from magic import fetcher
from magic.models import Card
from shared import fetch_tools


class Rulings(Extension):
    @slash_command('rulings')
    @slash_card_option()
    @auto_defer()
    async def rulings(self, ctx: MtgContext, card: Card) -> None:
        """Rulings for a card."""
        await ctx.single_card_text(card, card_rulings)

def card_rulings(c: Card) -> str:
    raw_rulings = fetcher.rulings(c.name)
    comments = [r['comment'] for r in raw_rulings]
    if len(comments) > 3:
        n = len(comments) - 2
        comments = comments[:2]
        comments.append('And {n} others.  See <https://scryfall.com/search?q=%21%22{cardname}%22#rulings>'.format(n=n, cardname=fetch_tools.escape(c.name)))
    return '\n'.join(comments) or 'No rulings available.'

def setup(bot: Client) -> None:
    Rulings(bot)
