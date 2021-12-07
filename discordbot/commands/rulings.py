from dis_snek.client import Snake
from dis_snek.models.application_commands import slash_command
from dis_snek.models.scale import Scale

from discordbot.command import MtgContext, autocomplete_card, slash_card_option
from magic import fetcher
from magic.models import Card
from shared import fetch_tools


class Rulings(Scale):
    @slash_command('rulings')
    @slash_card_option()
    async def rulings(self, ctx: MtgContext, card: Card) -> None:
        """Rulings for a card."""
        await ctx.single_card_text(card, card_rulings)

    rulings.autocomplete('card')(autocomplete_card)

def card_rulings(c: Card) -> str:
    raw_rulings = fetcher.rulings(c.name)
    comments = [r['comment'] for r in raw_rulings]
    if len(comments) > 3:
        n = len(comments) - 2
        comments = comments[:2]
        comments.append('And {n} others.  See <https://scryfall.com/search?q=%21%22{cardname}%22#rulings>'.format(n=n, cardname=fetch_tools.escape(c.name)))
    return '\n'.join(comments) or 'No rulings available.'

def setup(bot: Snake) -> None:
    Rulings(bot)
