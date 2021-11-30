from discordbot.command import MtgContext
from magic import fetcher, tournaments
from shared import dtutil
from dis_snek.models.command import message_command


@message_command()
async def burningofxinye(ctx: MtgContext) -> None:
    """Information about Burning of Xinye's rules."""
    await ctx.send('https://katelyngigante.tumblr.com/post/163849688389/why-the-mtgo-bug-that-burning-of-xinye-allows')
