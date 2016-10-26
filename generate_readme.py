import subprocess

from discordbot import generate_readme as bot_readme

HEADER = """
# Penny Dreadful Tools
Repository for a bunch of tools used in and around the Penny Dreadful Discord channel.

View individual subdirectories for details

[![Build Status](http://ci.katelyngigante.com/buildStatus/icon?job=Penny Dreadful/Penny-Dreadful-Discord-Bot/master)](http://ci.katelyngigante.com/job/Penny%20Dreadful/job/Penny-Dreadful-Discord-Bot/job/master/)


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
