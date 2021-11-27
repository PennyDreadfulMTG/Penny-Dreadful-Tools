
from dis_snek.models.command import message_command
from discordbot.command import MtgMessageContext

from dis_snek.models.scale import Scale
from dis_snek import Snake

class Barbs(Scale):
    @message_command()
    async def barbs(self, ctx: MtgMessageContext) -> None:
        """Volvary's advice for when to board in Aura Barbs."""
        msg = "Heroic doesn't get that affected by Barbs. Bogles though. Kills their creature, kills their face."
        await ctx.send(msg)

def setup(bot: Snake) -> None:
    Barbs(bot)
