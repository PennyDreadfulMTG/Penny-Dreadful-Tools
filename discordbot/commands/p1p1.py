import random

from discord.ext import commands

from discordbot.command import MtgContext
from magic import image_fetcher, oracle
from shared import redis_wrapper as redis


@commands.command()
async def p1p1(ctx: MtgContext) -> None:
    """`!p1p1` Summon a pack 1, pick 1 game."""

    if is_p1p1_ready(ctx.channel.id):
        with ctx.typing():
            lock(ctx.channel.id) #Do not allow more than one p1p1 at the same time.
            cards = [oracle.cards_by_name()[name] for name in random.sample(oracle.legal_cards(), 15)]
            await image_fetcher.download_image_async(cards) #Preload the cards to reduce the delay encountered between introduction and the cards.
            await ctx.send("Let's play the pack 1, pick 1 game. The rules are simple. You are drafting and you open this as your first pack. What do you take?")
            await ctx.post_cards(cards[0:5])
            await ctx.post_cards(cards[5:10])
            await ctx.post_cards(cards[10:])
            unlock(ctx.channel.id)
    else:
        print('Pack1Pick1 was denied as it was still processing another one.')  #This command will be heavy enough by itself, make sure the bot doesn't process it too much.

def is_p1p1_ready(channel_id: int) -> bool:
    return not redis.get_bool(f'discordbot:p1p1:{channel_id}')

def lock(channel_id: int) -> None:
    redis.store(f'discordbot:p1p1:{channel_id}', True, ex=300)

def unlock(channel_id: int) -> None:
    redis.clear(f'discordbot:p1p1:{channel_id}')
