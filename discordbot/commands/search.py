from naff.models import CMD_BODY, OptionTypes, prefixed_command
from naff.models.naff.application_commands import auto_defer, slash_command, slash_option

from discordbot.command import MAX_CARDS_SHOWN, MtgContext, MtgMessageContext
from magic import fetcher, oracle
from shared import fetch_tools


@slash_command('scry')  # type: ignore
@slash_option('query', 'A scryfall query', OptionTypes.STRING, required=True)
@auto_defer()
async def search(ctx: MtgContext, query: str) -> None:
    """Card search using Scryfall."""
    how_many, cardnames, _results = fetcher.search_scryfall(query)
    cbn = oracle.cards_by_name()
    cards = [cbn[name] for name in cardnames if cbn.get(name) is not None]
    await ctx.post_cards(cards, ctx.author, more_results_link(query, how_many))

@prefixed_command('scry')
async def m_scry(ctx: MtgMessageContext, args: CMD_BODY) -> None:
    ctx.kwargs['query'] = args
    await search.call_callback(search.callback, ctx)

def more_results_link(args: str, total: int) -> str:
    return 'and {n} more.\n<https://scryfall.com/search/?q={q}>'.format(n=total - 4, q=fetch_tools.escape(args)) if total > MAX_CARDS_SHOWN else ''
