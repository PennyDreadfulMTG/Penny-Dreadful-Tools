import random

from discord.ext import commands

from discordbot.command import MtgContext, complex_search
from magic import oracle
from magic.models import Card


@commands.command(aliases=['rhino'])
async def rhinos(ctx: MtgContext) -> None:
    """`!rhinos` Anything can be a rhino if you try hard enough"""
    rhino_name = 'Siege Rhino'
    if random.random() < 0.05:
        rhino_name = 'Abundant Maw'
    og_rhino = oracle.cards_by_name()[rhino_name]

    def find_rhino(query: str) -> Card:
        cards = complex_search('f:pd {0}'.format(query))
        if len(cards) == 0:
            cards = complex_search(query)
        return random.choice(cards)
    copy_rhino = find_rhino('o:"copy of target creature"')
    zombie_rhino = find_rhino('o:"return target creature card from your graveyard to the battlefield"')
    tutor_rhino = find_rhino('o:"search your library for a creature"')
    msg = f'\nSo of course we have {og_rhino.name}.'
    msg += f" And we have {copy_rhino.name}. It can become a rhino, so that's a rhino."
    msg += f" Then there's {zombie_rhino.name}. It can get back one of our rhinos, so that's a rhino."
    msg += f" And then we have {tutor_rhino.name}. It's a bit of a stretch, but that's a rhino too."
    await ctx.post_cards([og_rhino, copy_rhino, zombie_rhino, tutor_rhino], additional_text=msg)
