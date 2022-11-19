import logging
import os
import subprocess
from typing import List, Tuple

from modo_bugs import scrape_announcements, scrape_bugblog, update, verification
from shared import configuration


def run(argv: Tuple[str]) -> None:
    args = list(argv)
    logger = logging.getLogger(__name__)
    wd = configuration.get_str('modo_bugs_dir')
    if not os.path.exists(wd):
        subprocess.run(['git', 'clone', 'https://github.com/PennyDreadfulMTG/modo-bugs.git', wd], check=True)
    os.chdir(wd)
    subprocess.run(['git', 'pull'], check=True)
    if not args:
        args.extend(['scrape_an', 'update', 'verify', 'commit'])
    logger.info('modo_bugs invoked with modes: ' + repr(args))

    changes: List[str] = []

    try:
        if 'scrape_bb' in args:
            scrape_bugblog.main(changes)
        if 'scrape_an' in args:
            scrape_announcements.main(changes)
    except Exception as e:
        logging.exception(e)

    if 'update' in args:
        update.main()
    if 'verify' in args:
        verification.main()
    if 'commit' in args:
        subprocess.run(['git', 'add', '.'], check=True)
        changestr = '\n'.join(changes)
        try:
            subprocess.run(['git', 'commit', '-m', f'Updated\n\n{changestr}'], check=True)
        except subprocess.CalledProcessError:
            return
        user = configuration.get('github_user')
        pword = configuration.get('github_password')
        subprocess.run(['git', 'push', f'https://{user}:{pword}@github.com/PennyDreadfulMTG/modo-bugs.git'], check=True)
