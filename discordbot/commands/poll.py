from discord.ext import commands

from discordbot.command import MtgContext

async def poll(ctx: MtgContext) -> None:
    msg = ctx.message.reference
    if msg is None:
        await ctx.reply('You need to invoke this while replying to a message.')
        return
