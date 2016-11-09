import subprocess

from discordbot import generate_readme as bot_readme

HEADER = """
# Penny Dreadful Tools
Repository for a bunch of tools used in and around the Penny Dreadful Discord channel.

View individual subdirectories for details

[![Build Status](http://ci.katelyngigante.com/buildStatus/icon?job=Penny Dreadful/Penny-Dreadful-Tools/master)](http://ci.katelyngigante.com/job/Penny%20Dreadful/job/Penny-Dreadful-Tools/job/master/)
[![Codacy Badge](https://api.codacy.com/project/badge/Grade/b4e068a91bd048e9a8e803e8bde29c9d)](https://www.codacy.com/app/clockwork-singularity/Penny-Dreadful-Tools?utm_source=github.com&amp;utm_medium=referral&amp;utm_content=PennyDreadfulMTG/Penny-Dreadful-Tools&amp;utm_campaign=Badge_Grade)
[![Codacy Badge](https://api.codacy.com/project/badge/Coverage/b4e068a91bd048e9a8e803e8bde29c9d)](https://www.codacy.com/app/clockwork-singularity/Penny-Dreadful-Tools?utm_source=github.com&amp;utm_medium=referral&amp;utm_content=PennyDreadfulMTG/Penny-Dreadful-Tools&amp;utm_campaign=Badge_Coverage)

"""

def generate_readme():
    changed = 0
    readme = ""
    readme += HEADER

    fh = open("README.md")
    old_readme = fh.read()
    fh.close()

    if readme != old_readme:
        fh = open("README.md", mode='w')
        fh.write(readme)
        fh.close()
        print("Readme updated.")
        changed += 1
    changed += bot_readme.generate_readme()

    # if changed:
    #     git_commit()
    return changed

def git_commit():
    subprocess.call(["git", "add", "README.md"])
    subprocess.call(["git", "commit", "-m", "Updated README.md"])
    subprocess.call(["git", "push"])

exit(generate_readme())
