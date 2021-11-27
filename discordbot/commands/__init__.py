import glob
import importlib
import inspect
import logging
from os import path
from typing import List, Optional

from dis_snek import Snake
from dis_snek.models.context import Context
from dis_snek.models.scale import Scale
from dis_snek.models.application_commands import InteractionCommand, SlashCommand
from dis_snek.models.command import MessageCommand

from discordbot import command
from magic.models import Card
from shared import text


def setup(bot: Snake) -> None:
    Card.convert = CardConverter.convert
    modules = glob.glob(path.join(path.dirname(__file__), '*.py'))
    files = [path.basename(f)[:-3] for f in modules if path.isfile(f) and not f.endswith('__init__.py')]

    # commands, interactions, names = [], [], []
    for mod in files:
        try:
            bot.grow_scale(f'.{mod}', __name__)
        except Exception as e:
            logging.exception(e)

class CardConverter:
    @classmethod
    async def convert(cls, ctx: Context, argument: str) -> Optional[Card]:
        try:
            result, mode, printing = command.results_from_queries([argument])[0]
            if result.has_match() and not result.is_ambiguous():
                return command.cards_from_names_with_mode([result.get_best_match()], mode, printing)[0]
            if result.is_ambiguous():
                message = await ctx.send('{author}: Ambiguous name for {c}. Suggestions: {s}'.format(author=ctx.author.mention, c=ctx.command, s=command.disambiguation(result.get_ambiguous_matches()[0:5])))
                await command.disambiguation_reactions(message, result.get_ambiguous_matches()[0:5])
            else:
                message = await ctx.send('{author}: No matches.'.format(author=ctx.author.mention))
                await message.add_reaction('❎')
            return None
        except Exception as exc:
            raise Exception('Could not find card') from exc
