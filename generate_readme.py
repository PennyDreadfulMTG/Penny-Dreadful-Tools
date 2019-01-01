import subprocess

from discordbot import generate_readme as bot_readme

HEADER = """
# Penny Dreadful Tools
Repository for the tools used by the Penny Dreadful Community.

View individual subdirectories for details

[![Build Status](https://travis-ci.org/PennyDreadfulMTG/Penny-Dreadful-Tools.svg?branch=master)](https://travis-ci.org/PennyDreadfulMTG/Penny-Dreadful-Tools)
[![Codacy Badge](https://api.codacy.com/project/badge/Grade/b4e068a91bd048e9a8e803e8bde29c9d)](https://www.codacy.com/app/clockwork-singularity/Penny-Dreadful-Tools?utm_source=github.com&amp;utm_medium=referral&amp;utm_content=PennyDreadfulMTG/Penny-Dreadful-Tools&amp;utm_campaign=Badge_Grade)
[![Uptime Robot status](https://img.shields.io/uptimerobot/status/m778417564-ebc98d54a784806de06fee4d.svg)](https://status.pennydreadfulmagic.com)

# Modules:

**discordbot** is the Discord chatbot.

**decksite** is the code for [pennydreadfulmagic.com](https://pennydreadfulmagic.com/).

**magic** knows everything about all magic cards and how to fetch that information from the internet and model it.

**logsite**  is the code for [logs.pennydreadfulmagic.com](https://logs.pennydreadfulmagic.com/).

**price_grabber** builds a database of historic prices.

**shared** contains a bunch of general purpose helper classes. Things that could be used in any project.

**shared_web** contains a bunch of web-specific helper classes.

"""

def generate_readme() -> int:
    changed = 0
    readme = ''
    readme += HEADER

    fh = open('README.md')
    old_readme = fh.read()
    fh.close()

    if readme != old_readme:
        fh = open('README.md', mode='w')
        fh.write(readme)
        fh.close()
        print('Readme updated.')
        changed += 1
    changed += bot_readme.generate_readme()

    # if changed:
    #     git_commit()
    return changed

def git_commit() -> None:
    subprocess.call(['git', 'add', 'README.md'])
    subprocess.call(['git', 'commit', '-m', 'Updated README.md'])
    subprocess.call(['git', 'push'])

exit(generate_readme())
