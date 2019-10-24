import os
from typing import Set

from discordbot import commands
from discordbot.bot import Bot

HEADER = """
# Penny-Dreadful-Discord-Bot
Displays info about quoted cards in a discord channel

"""

USAGE = """
# Usage
Basic bot usage: Include [cardname] in your regular messages.

The bot will search for any quoted cards, and respond with the card details.
"""

FOOTER = """
# Installation
To add this bot to your servers use this <a href='https://discordapp.com/oauth2/authorize?client_id=224755717767299072&scope=bot&permissions=0'>link</a>
"""

def generate_readme() -> int:
    readme = ''
    readme += HEADER
    readme += USAGE
    readme += """
# Commands
"""
    readme += print_commands()

    readme += '\n'
    readme += FOOTER

    fh = open(os.path.join('discordbot', 'README.md'))
    old_readme = fh.read()
    fh.close()

    if readme != old_readme:
        fh = open(os.path.join('discordbot', 'README.md'), mode='w')
        fh.write(readme)
        fh.close()
        print('Readme updated.')
        return 1
    return 0

def print_commands() -> str:
    bot = Bot()
    commands.setup(bot)
    text = ''
    done: Set[str] = set()
    for c in bot.walk_commands():
        if not c.name in done:
            text += f'## {c.name}'
            if c.aliases:
                aliases = ', '.join(c.aliases)
                text += f' ({aliases})'
            done.add(c.name)
            text += f'\n\n{c.help}\n\n'
    return text
