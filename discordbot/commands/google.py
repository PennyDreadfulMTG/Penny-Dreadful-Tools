from discord.ext import commands

from discordbot.command import MtgContext

# from googleapiclient.discovery import build
# from googleapiclient.errors import HttpError

# from shared import configuration


@commands.command(aliases=['g'])
async def google(ctx: MtgContext, *, args: str) -> None:
    """Google search"""
    # api_key = configuration.cse_api_key.value
    # cse_id = configuration.cse_engine_id.value
    # if not api_key or not cse_id:
    #     await ctx.send('The google command has not been configured.')
    #     return
    #
    # if len(args) == 0:
    #     await ctx.send('{author}: No search term provided. Please type !google followed by what you would like to search.'.format(author=ctx.author.mention))
    #     return
    #
    # try:
    #     service = build('customsearch', 'v1', developerKey=api_key)
    #     res = service.cse().list(q=args, cx=cse_id, num=1).execute()  # pylint: disable=no-member
    #     if 'items' in res:
    #         r = res['items'][0]
    #         s = '{title} <{url}> {abstract}'.format(title=r['title'], url=r['link'], abstract=r['snippet'])
    #     else:
    #         s = '{author}: Nothing found on Google.'.format(author=ctx.author.mention)
    # except HttpError as e:
    #     if e.resp['status'] == '403':
    #         s = 'We have reached the allowed limits of Google API'
    #     else:
    #         raise
    #
    # await ctx.send(s)
    await ctx.send('This command is temporarily disabled')
