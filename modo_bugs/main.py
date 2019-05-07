import os
import subprocess
import sys
from typing import List

from modo_bugs import (scrape_announcements, scrape_bugblog, update,
                       verification)
from shared import configuration


def run() -> None:
    wd = configuration.get_str('modo_bugs_dir')
    if not os.path.exists(wd):
        subprocess.run(['git', 'clone', 'https://github.com/PennyDreadfulMTG/modo-bugs.git', wd])
    os.chdir(wd)
    subprocess.run(['git', 'pull'])
    args = sys.argv[2:]
    if not args:
        args.extend(['scrape', 'update', 'verify', 'commit'])
    print('modo_bugs invoked with modes: ' + repr(args))

    changes: List[str] = []

    if 'scrape' in args:
        args.extend(['scrape_bb', 'scrape_an'])
    if 'scrape_bb' in args:
        scrape_bugblog.main(changes)
    if 'scrape_an' in args:
        scrape_announcements.main(changes)

    if 'update' in args:
        update.main()
    if 'verify' in args:
        verification.main()
    if 'commit' in args:
        subprocess.run(['git', 'add', '.'])
        subprocess.run(['git', 'commit', '-m', 'Updated'])
        user = configuration.get('github_user')
        pword = configuration.get('github_password')
        subprocess.run(['git', 'push', f'https://{user}:{pword}@github.com/PennyDreadfulMTG/modo-bugs.git'])
