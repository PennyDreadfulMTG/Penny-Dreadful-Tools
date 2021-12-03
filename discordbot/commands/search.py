from dis_snek.models.application_commands import slash_command

from discordbot.command import MAX_CARDS_SHOWN, MtgContext
from magic import fetcher, oracle
from shared import fetch_tools


@slash_command('scry')
async def search(ctx: MtgContext, query: str) -> None:
    """Card search using Scryfall."""
    how_many, cardnames = fetcher.search_scryfall(query)
    cbn = oracle.cards_by_name()
    cards = [cbn[name] for name in cardnames if cbn.get(name) is not None]
    await ctx.post_cards(cards, ctx.author, more_results_link(query, how_many))

def more_results_link(args: str, total: int) -> str:
    return 'and {n} more.\n<https://scryfall.com/search/?q={q}>'.format(n=total - 4, q=fetch_tools.escape(args)) if total > MAX_CARDS_SHOWN else ''
