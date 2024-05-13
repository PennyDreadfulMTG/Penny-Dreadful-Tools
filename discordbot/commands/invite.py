from interactions import Extension, slash_command, Client

from discordbot.command import MtgContext


class Invite(Extension):
    @slash_command()
    async def invite(self, ctx: MtgContext) -> None:
        """Invite me to your server."""
        await ctx.send('Invite me to your discord server by clicking this link: <https://discordapp.com/oauth2/authorize?client_id=224755717767299072&scope=bot&permissions=268757056>')

def setup(bot: Client) -> None:
    Invite(bot)
