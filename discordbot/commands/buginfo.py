from dis_snek.client import Snake
from dis_snek.models.application_commands import slash_command
from discordbot import command
from shared import fetch_tools

from discordbot.command import MtgContext
from magic.models import Card

from dis_snek.models.scale import Scale


class BugInfo(Scale):
    @slash_command('buginfo')
    @command.slash_card_option()
    async def buglink(ctx: MtgContext, card: Card) -> None:
        """Link to the modo-bugs page for a card."""
        base_url = 'https://github.com/PennyDreadfulMTG/modo-bugs/issues'
        if card is None:
            await ctx.send(base_url)
            return
        msg = '<{base_url}?utf8=%E2%9C%93&q=is%3Aissue+%22{name}%22>'.format(base_url=base_url, name=fetch_tools.escape(card.name))
        await ctx.send(msg)

def setup(bot: Snake) -> None:
    BugInfo(bot)
