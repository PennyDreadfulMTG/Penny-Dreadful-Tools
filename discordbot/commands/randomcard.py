from discord.ext import commands

from discordbot.command import MtgContext
from magic import oracle


@commands.command(aliases=['r', 'rand', 'random'])
async def random(ctx: MtgContext, number: int = 1) -> None:
    """`!random` A random PD legal card.
`!random X` X random PD legal cards."""
    additional_text = ''
    if number > 10:
        additional_text = "{number}? Tsk. Here's ten.".format(number=number)
        number = 10
    cards = [oracle.cards_by_name()[name] for name in random.sample(oracle.legal_cards(), number)]
    await ctx.post_cards(cards, None, additional_text)
