from interactions.client.client import Client
from interactions.ext.prefixed_commands import prefixed_command
from interactions.models import Extension, slash_command

from discordbot.command import MtgContext, migrate_to_slash_command
from magic import fetcher, tournaments


class Tournament(Extension):

    @slash_command('tournament')
    async def tournament(self, ctx: MtgContext) -> None:
        """Information about the next tournament."""
        t = tournaments.next_tournament_info()
        prev = tournaments.previous_tournament_info()
        if prev['near']:
            started = 'it started '
        else:
            started = ''
        prev_message = 'The last tournament was {name}, {started}{time}'.format(
            name=prev['next_tournament_name'], started=started, time=prev['discord_relative'])
        next_time = t['discord_relative']
        await ctx.send('The next tournament is {name} {next_time} ({full}).\nSign up on <http://gatherling.com/>\nMore information: {url}\n{prev_message}'.format(name=t['next_tournament_name'], next_time=next_time, prev_message=prev_message, url=fetcher.decksite_url('/tournaments/'), full=t['discord_full']))

    m_tournament = migrate_to_slash_command(tournament, True)
    m_to = prefixed_command('to')(m_tournament.callback)

def setup(bot: Client) -> None:
    Tournament(bot)
