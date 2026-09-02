import asyncio

from interactions.client import Client
from interactions.models import Extension, auto_defer, slash_command

from discordbot.command import MtgContext, slash_card_option
from magic import fetcher
from magic.models import Card
from shared import fetch_tools


class Rulings(Extension):
    @slash_command(description='Rulings for a card.')
    @slash_card_option()
    @auto_defer()
    async def rulings(self, ctx: MtgContext, card: Card) -> None:
        """Rulings for a card."""
        raw_rulings = await asyncio.to_thread(fetcher.rulings, card.name)
        await ctx.single_card_text(card, lambda c: card_rulings(c, raw_rulings))

def card_rulings(c: Card, raw_rulings: list[dict[str, str]]) -> str:
    comments = [r['comment'] for r in raw_rulings]
    if len(comments) > 3:
        n = len(comments) - 2
        comments = comments[:2]
        comments.append(f'And {n} others.  See <https://scryfall.com/search?q=%21%22{fetch_tools.escape(c.name)}%22#rulings>')
    return '\n'.join(comments) or 'No rulings available.'

def setup(bot: Client) -> None:
    Rulings(bot)
