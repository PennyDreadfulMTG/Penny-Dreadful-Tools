from discord.ext import commands

from discordbot.command import MAX_CARDS_SHOWN, MtgContext
from magic import fetcher, oracle


@commands.command(aliases=['s', 'scry', 'scryfall', 'se'])
async def search(ctx: MtgContext, *, args: str) -> None:
    """`!search {query}` Card search using Scryfall."""
    how_many, cardnames = fetcher.search_scryfall(args)
    cbn = oracle.cards_by_name()
    cards = [cbn[name] for name in cardnames if cbn.get(name) is not None]
    await ctx.post_cards(cards, ctx.author, more_results_link(args, how_many))

def more_results_link(args: str, total: int) -> str:
    return 'and {n} more.\n<https://scryfall.com/search/?q={q}>'.format(n=total - 4, q=fetcher.internal.escape(args)) if total > MAX_CARDS_SHOWN else ''
