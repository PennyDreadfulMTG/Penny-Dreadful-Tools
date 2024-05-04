from interactions import Client
from interactions.models import Extension, OptionType, slash_command, slash_option
from scipy.stats import hypergeom

from discordbot.command import MtgInteractionContext


class Odds(Extension):
    def __init__(self, bot: Client) -> None:
        self.bot = bot
        super().__init__()

    @slash_command('odds')
    @slash_option(
        name='copies',
        description='How many copies are you running? (Default 4)',
        opt_type=OptionType.INTEGER,
        required=False,
    )
    @slash_option(
        name='drawn',
        description='How many cards have you drawn? (Default 7)',
        opt_type=OptionType.INTEGER,
        required=False,
    )
    @slash_option(
        name='needed',
        description='How many do you need to draw? (Default 1)',
        opt_type=OptionType.INTEGER,
        required=False,
    )
    @slash_option(
        name='deck_size',
        description='How big is your deck? (Default 60)',
        opt_type=OptionType.INTEGER,
        required=False,
    )
    async def odds(self, ctx: MtgInteractionContext, drawn: int = 7, copies: int = 4, needed: int = 1, deck_size: int = 60) -> None:
        """Determine the odds of drawing a card"""
        h = hypergeom(deck_size, copies, drawn)

        def percent(f: float) -> float:
            return round(f * 100, 1)
        card_s = 'card' if drawn == 1 else 'cards'
        copy_s = 'copy' if copies == 1 else 'copies'
        s = f'{percent(1 - h.cdf(needed - 1))}% chance of {needed} or more ({percent(h.pmf(needed))}% of exactly {needed}) in {drawn} {card_s} drawn from a {deck_size} card deck running {copies} {copy_s}'
        await ctx.send(s)

def setup(bot: Client) -> None:
    Odds(bot)
