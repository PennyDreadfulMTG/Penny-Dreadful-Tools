from discord.ext import commands

from discordbot.command import MtgContext
from magic import fetcher
from shared import fetch_tools


@commands.command(aliases=['rd'])
async def randomdeck(ctx: MtgContext) -> None:
    """A random deck from the current season."""
    blob = fetch_tools.fetch_json(fetcher.decksite_url('/api/randomlegaldeck'))
    if 'error' in blob or 'url' not in blob:
        await ctx.send(blob.get('msg', ''))
    else:
        ctn = blob.get('competition_type_name', None)
        if ctn is not None:
            if ctn == 'Gatherling' and blob['finish'] == 1:
                record = 'won'
            elif ctn == 'Gatherling' and blob['finish'] <= blob['competition_top_n']:
                record = f"made Top {blob['competition_top_n']} of"
            else:
                draws = f"-{blob['draws']}" if blob['draws'] > 0 else ''
                record = f"went {blob['wins']}-{blob['losses']}{draws} in"
            preamble = f"{blob['person']} {record} {blob['competition_name']} with this:\n"
        else:
            preamble = f"{blob['person']} posted this on {blob['source_name']}:\n"
        await ctx.send(preamble + blob['url'])
