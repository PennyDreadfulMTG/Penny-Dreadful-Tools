from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from interactions.client import Client
from interactions.models import Extension, OptionType, slash_command, slash_option
from interactions.models.discord.enums import MessageFlags

from discordbot import command
from discordbot.command import MtgContext
from shared import configuration


class Google(Extension):
    @slash_command('google')
    @slash_option('query', 'Search terms', OptionType.STRING, required=True)
    async def google(self, ctx: MtgContext, query: str) -> None:
        """Google search"""
        api_key = configuration.cse_api_key.value
        cse_id = configuration.cse_engine_id.value
        if not api_key or not cse_id:
            await ctx.send('The google command has not been configured.', flags=MessageFlags.EPHEMERAL)
            return

        if len(query) == 0:
            await ctx.send(f'{ctx.author.mention}: No search term provided. Please type !google followed by what you would like to search.', flags=MessageFlags.EPHEMERAL)
            return

        try:
            service = build('customsearch', 'v1', developerKey=api_key)
            res = service.cse().list(q=query, cx=cse_id, num=1).execute()
            if 'items' in res:
                r = res['items'][0]
                s = '{title} <{url}> {abstract}'.format(title=r['title'], url=r['link'], abstract=r['snippet'])
            else:
                s = f'{ctx.author.mention}: Nothing found on Google.'
        except HttpError as e:
            if e.resp['status'] == '403':
                s = 'We have reached the allowed limits of Google API'
            else:
                raise

        await ctx.send(s)

    m_google = command.alias_message_command_to_slash_command(google, 'query')

def setup(bot: Client) -> None:
    Google(bot)
