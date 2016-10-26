import os

from discordbot import command

HEADER = """
# Penny-Dreadful-Discord-Bot
Displays info about quoted cards in a discord channel

[![Build Status](http://ci.katelyngigante.com/buildStatus/icon?job=Penny Dreadful/Penny-Dreadful-Discord-Bot/master)](http://ci.katelyngigante.com/job/Penny%20Dreadful/job/Penny-Dreadful-Discord-Bot/job/master/)
"""

USAGE = """
#Usage
Basic bot usage: Include [cardname] in your regular messages.
The bot will search for any quoted cards, and respond with the card details.
"""

FOOTER = """
#Installation
To add this bot to your servers use this <a href='https://discordapp.com/oauth2/authorize?client_id=224755717767299072&scope=bot&permissions=0'>link</a>

#Libraries used

[Discord.py](https://github.com/Rapptz/discord.py)

[mtgjson](http://mtgjson.com/)
"""

def generate_readme():
    readme = ""
    readme += HEADER
    readme += USAGE
    readme += """
#Commands
"""
    readme += command.build_help()
    readme += '\n'
    readme += FOOTER

    fh = open(os.path.join("discordbot", "README.md"))
    old_readme = fh.read()
    fh.close()

    if readme != old_readme:
        fh = open(os.path.join("discordbot", "README.md"), mode='w')
        fh.write(readme)
        fh.close()
        print("Readme updated.")
        return 1
    return 0
