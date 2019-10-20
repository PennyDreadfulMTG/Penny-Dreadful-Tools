from discord.ext import commands

from magic import fetcher, tournaments
from shared import dtutil
from discordbot.command import MtgContext


@commands.command('Commands', aliases=['tournaments'])
async def tournament(ctx: MtgContext) -> None:
    """`!tournament` Information about the next tournament."""
    t = tournaments.next_tournament_info()
    prev = tournaments.previous_tournament_info()
    if prev['near']:
        started = 'it started '
    else:
        started = ''
    prev_message = 'The last tournament was {name}, {started}{time} ago'.format(
        name=prev['next_tournament_name'], started=started, time=prev['next_tournament_time'])
    next_time = 'in ' + t['next_tournament_time'] if t['next_tournament_time'] != dtutil.display_time(
        0, 0) else t['next_tournament_time']
    await ctx.send('The next tournament is {name} {next_time}.\nSign up on <http://gatherling.com/>\nMore information: {url}\n{prev_message}'.format(name=t['next_tournament_name'], next_time=next_time, prev_message=prev_message, url=fetcher.decksite_url('/tournaments/')))
