import random

from interactions import Client, Extension
from interactions.models import OptionType, slash_command, slash_option

from discordbot.command import MtgContext
from magic import oracle


class RandomCard(Extension):
    @slash_command('random-card')
    @slash_option('number', 'How many cards?', OptionType.INTEGER)
    async def randomcard(self, ctx: MtgContext, number: int = 1) -> None:
        """A random PD legal card.
    `!random X` X random PD legal cards."""
        additional_text = ''
        if number < 1:
            number = 1
        elif number > 10:
            additional_text = f"{number}? Tsk. Here's ten."
            number = 10
        cards = [oracle.cards_by_name()[name] for name in random.sample(oracle.legal_cards(), number)]
        await ctx.post_cards(cards, None, additional_text)

def setup(bot: Client) -> None:
    RandomCard(bot)
