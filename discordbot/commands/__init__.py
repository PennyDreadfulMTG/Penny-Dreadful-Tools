import glob
import importlib
from os import path

from discord.ext import commands

ALL_COMMANDS = []

def setup(bot: commands.Bot) -> None:
    modules = glob.glob(path.join(path.dirname(__file__), '*.py'))
    files = [path.basename(f)[:-3] for f in modules if path.isfile(f) and not f.endswith('__init__.py')]

    for mod in files:
        importlib.import_module(f'.{mod}', package=__name__)

