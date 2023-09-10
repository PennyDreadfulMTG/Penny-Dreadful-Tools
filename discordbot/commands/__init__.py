import glob
import importlib
import inspect
import logging
from os import path
from typing import Optional, cast

from interactions import Client, SlashContext
from interactions.models import Extension, InteractionCommand
from interactions.ext.prefixed_commands import PrefixedCommand, PrefixedInjectedClient, PrefixedContext

from discordbot import command
from magic.models import Card


def setup(bot: Client) -> None:
    Card.convert = CardConverter.convert
    modules = glob.glob(path.join(path.dirname(__file__), '*.py'))
    files = [path.basename(f)[:-3] for f in modules if path.isfile(f) and not f.endswith('__init__.py')]

    for mod in files:
        try:
            bot.load_extension(f'.{mod}', __name__)
        except Exception as e:
            if not scaleless_load(bot, mod):
                logging.exception(e)


def scaleless_load(bot: Client, module: str) -> bool:
    n = 0
    try:
        m = importlib.import_module(f'.{module}', package=__name__)
        for _, obj in inspect.getmembers(m):
            if isinstance(obj, InteractionCommand):
                bot.add_interaction(obj)
                n += 1
            elif isinstance(obj, PrefixedCommand):
                botp = cast(PrefixedInjectedClient, bot)
                botp.prefixed.add_command(obj)
                n += 1
            elif isinstance(obj, Extension):
                logging.warning(f'{module} is an Extension, but it doesnt have a setup method')
                obj(bot)  # type: ignore
                n += 1
    except Exception:
        raise
    return n > 0

class CardConverter:
    @classmethod
    async def convert(cls, ctx: PrefixedContext | SlashContext, argument: str) -> Optional[Card]:
        try:
            result, mode, printing = command.results_from_queries([argument])[0]
            if result.has_match() and not result.is_ambiguous():
                return command.cards_from_names_with_mode([result.get_best_match()], mode, printing)[0]
            if result.is_ambiguous():
                message = await ctx.send('{author}: Ambiguous name for {c}. Suggestions: {s}'.format(author=ctx.author.mention, c=ctx.invoke_target, s=command.disambiguation(result.get_ambiguous_matches()[0:5])))
                await command.disambiguation_reactions(message, result.get_ambiguous_matches()[0:5])
            else:
                message = await ctx.send('{author}: No matches.'.format(author=ctx.author.mention))
                await message.add_reaction('❎')
            return None
        except Exception as exc:
            raise Exception('Could not find card') from exc
