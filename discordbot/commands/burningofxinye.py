from interactions import Client, Extension, slash_command

from discordbot.command import MtgContext


class BurningOfXinye(Extension):
    @slash_command()
    async def burningofxinye(self, ctx: MtgContext) -> None:
        """Information about Burning of Xinye's rules."""
        await ctx.send('https://katelyngigante.tumblr.com/post/163849688389/why-the-mtgo-bug-that-burning-of-xinye-allows')

def setup(bot: Client) -> None:
    BurningOfXinye(bot)
