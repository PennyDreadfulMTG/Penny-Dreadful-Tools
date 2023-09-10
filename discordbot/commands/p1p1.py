import random

from interactions.models import Buckets, max_concurrency, slash_command

from discordbot.command import MtgInteractionContext
from magic import image_fetcher, oracle


@slash_command('p1p1')  # type: ignore
@max_concurrency(Buckets.GUILD, 1)
async def p1p1(ctx: MtgInteractionContext) -> None:
    """`!p1p1` Summon a pack 1, pick 1 game."""
    await ctx.defer()
    await ctx.channel.trigger_typing()
    cards = [oracle.cards_by_name()[name] for name in random.sample(oracle.legal_cards(), 15)]
    await image_fetcher.download_image_async(cards)  # Preload the cards to reduce the delay encountered between introduction and the cards.
    await ctx.send("Let's play the pack 1, pick 1 game. The rules are simple. You are drafting and you open this as your first pack. What do you take?")
    await ctx.post_cards(cards[0:5])
    await ctx.post_cards(cards[5:10])
    await ctx.post_cards(cards[10:])
