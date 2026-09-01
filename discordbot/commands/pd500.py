from interactions import Client, Extension
from interactions.models import slash_command

from discordbot.command import MtgContext
from magic import fetcher, tournaments
from shared import dtutil


class PD500(Extension):
    @slash_command()
    async def pd500(self, ctx: MtgContext) -> None:
        """Display information about the PD 500 tournament."""
        url = fetcher.decksite_url('/tournaments/pd500/')
        pd500_date = tournaments.pd500_date()
        prizes = tournaments.pd500_prizes()
        top_prize = next((p['prize'] for p in prizes if p['finish'] == '1st'), None)

        if pd500_date.year == 1970:
            date_info = 'The date is yet to be determined (last Saturday of the season).'
        elif dtutil.now() > pd500_date:
            date_info = 'It is held on the last Saturday of the season.'
        else:
            date_info = f'The next one is on {dtutil.display_date_with_date_and_year(pd500_date)}.'

        prize_info = f'Top prize: {top_prize} tix.' if top_prize else ''

        parts = [
            'The Penny Dreadful 500 is the biggest PD tournament of the season.',
            date_info,
        ]
        if prize_info:
            parts.append(prize_info)
        parts.append(url)

        await ctx.send('\n'.join(parts))

def setup(bot: Client) -> None:
    PD500(bot)
