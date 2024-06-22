from interactions import Client, Extension, slash_command

from discordbot.command import MtgMessageContext


class Barbs(Extension):
    @slash_command()
    async def barbs(self, ctx: MtgMessageContext) -> None:
        """Volvary's advice for when to board in Aura Barbs."""
        msg = "Heroic doesn't get that affected by Barbs. Bogles though. Kills their creature, kills their face."
        await ctx.send(msg)


def setup(bot: Client) -> None:
    Barbs(bot)
