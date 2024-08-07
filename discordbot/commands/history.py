from interactions import Client
from interactions.models import Extension, slash_command

from discordbot import command
from discordbot.command import MtgContext
from magic import fetcher, seasons
from magic.models import Card
from shared import fetch_tools


class History(Extension):
    @slash_command()
    @command.slash_card_option()
    async def history(self, ctx: MtgContext, card: Card) -> None:
        """Show the legality history of the specified card and a link to its all time page."""
        await ctx.single_card_text(card, card_history)

def card_history(c: Card) -> str:
    data: dict[int, bool] = {}
    for format_name, status in c.legalities.items():
        if 'Penny Dreadful ' in format_name and status == 'Legal':
            season_id = seasons.SEASONS.index(format_name.replace('Penny Dreadful ', '')) + 1
            data[season_id] = True
    if len(data) == 0:
        s = 'Never legal'
    else:
        s = ' '.join(str(i).rjust(2) if data.get(i, False) else '.' for i in range(1, seasons.current_season_num() + 1))
    s += '\n<' + fetcher.decksite_url(f'/seasons/all/cards/{fetch_tools.escape(c.name, skip_double_slash=True)}/') + '>'
    return s

def setup(bot: Client) -> None:
    History(bot)
