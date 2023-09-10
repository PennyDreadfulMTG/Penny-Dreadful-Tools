from interactions.models import slash_command

from discordbot.command import MtgContext
from magic import fetcher
from shared import fetch_tools


@slash_command('random-deck')
async def randomdeck(ctx: MtgContext) -> None:
    """A random deck from the current season."""
    blob = fetch_tools.fetch_json(fetcher.decksite_url('/api/randomlegaldeck'))
    if 'error' in blob or 'url' not in blob:
        await ctx.send(f'{ctx.author.mention}: Error fetching random legal deck (' + blob.get('msg', 'Unknown') + ')')
    else:
        ctn = blob.get('competition_type_name', None)
        if ctn is not None:
            if ctn == 'Gatherling' and blob['finish'] == 1:
                record = 'won'
            elif ctn == 'Gatherling' and blob['finish'] <= blob.get('competition_top_n', 0):
                record = f"made Top {blob['competition_top_n']} of"
            else:
                draws = f"-{blob['draws']}" if blob['draws'] > 0 else ''
                record = f"went {blob['wins']}-{blob['losses']}{draws} in"
            preamble = f"{blob['person']} {record} {blob['competition_name']} with this:\n"
        else:
            preamble = f"{blob['person']} posted this on {blob['source_name']}:\n"
        await ctx.send(preamble + blob['url'])
