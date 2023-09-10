from interactions.ext.prefixed_commands import prefixed_command

from discordbot.command import MtgContext


@prefixed_command()
async def burningofxinye(ctx: MtgContext) -> None:
    """Information about Burning of Xinye's rules."""
    await ctx.send('https://katelyngigante.tumblr.com/post/163849688389/why-the-mtgo-bug-that-burning-of-xinye-allows')
