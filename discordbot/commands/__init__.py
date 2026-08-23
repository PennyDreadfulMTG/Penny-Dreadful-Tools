import glob
import importlib
import inspect
import logging
from os import path

from interactions import Client, SlashContext
from interactions.api.events import Component
from interactions.models import Button, ButtonStyle, InteractionCommand

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
    except Exception:
        raise
    return n > 0

class CardConverter:
    @classmethod
    async def convert(cls, ctx: SlashContext, argument: str) -> Card | None:
        try:
            result, mode, printing = command.results_from_queries([argument])[0]
            if result.has_match() and not result.is_ambiguous():
                return command.cards_from_names_with_mode([result.get_best_match()], mode, printing, argument)[0]
            if result.is_ambiguous():
                matches = result.get_ambiguous_matches()[:5]
                buttons = [Button(style=ButtonStyle.SECONDARY, label=card_name[:80]) for card_name in matches]
                message = await ctx.send(f'{ctx.author.mention}: Ambiguous name for {ctx.invoke_target}. Choose a card:', components=[buttons])

                def chosen_by_author(event: Component) -> bool:
                    return event.ctx.author.id == ctx.author.id

                try:
                    event = await ctx.client.wait_for_component(message, components=buttons, check=chosen_by_author, timeout=60)
                except TimeoutError:
                    await message.edit(content=f'{ctx.author.mention}: Card selection expired.', components=[])
                    return None

                selected = next(i for i, button in enumerate(buttons) if button.custom_id == event.ctx.custom_id)
                await event.ctx.edit_origin(content=f'{ctx.author.mention}: Selected **{matches[selected]}**.', components=[])
                return command.cards_from_names_with_mode([matches[selected]], mode, printing, argument)[0]
            else:
                message = await ctx.send(f'{ctx.author.mention}: No matches.')
                await message.add_reaction('❎')
            return None
        except Exception as exc:
            raise Exception('Could not find card') from exc
