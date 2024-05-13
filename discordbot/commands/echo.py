from interactions import slash_command, Extension, Client, slash_option, OptionType

from discordbot import emoji
from discordbot.command import MtgContext


class Echo(Extension):
    @slash_command()
    @slash_option('message', 'Thing to say', OptionType.STRING, True)
    async def echo(self, ctx: MtgContext, message: str) -> None:
        """Repeat after me…"""
        s = await emoji.replace_emoji(message, ctx.bot)
        if not s:
            s = "I'm afraid I can't do that, Dave"
        await ctx.send(s)

def setup(bot: Client) -> None:
    Echo(bot)
