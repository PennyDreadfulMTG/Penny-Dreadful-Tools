from interactions import Extension, Client
from interactions.models import OptionType, auto_defer, slash_command, slash_option

from discordbot.command import MAX_CARDS_SHOWN, MtgContext
from magic import fetcher, oracle
from shared import fetch_tools


class Scry(Extension):
    @slash_command()
    @slash_option('query', 'A scryfall query', OptionType.STRING, required=True)
    @auto_defer()
    async def scry(self, ctx: MtgContext, query: str) -> None:
        """Card search using Scryfall."""
        how_many, cardnames, _results = fetcher.search_scryfall(query)
        cbn = oracle.cards_by_name()
        cards = [cbn[name] for name in cardnames if cbn.get(name) is not None]
        await ctx.post_cards(cards, ctx.author, more_results_link(query, how_many))

def more_results_link(args: str, total: int) -> str:
    return f' and {total - 4} more.\n<https://scryfall.com/search/?q={fetch_tools.escape(args)}>' if total > MAX_CARDS_SHOWN else ''

def setup(bot: Client) -> None:
    Scry(bot)
