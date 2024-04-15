import logging
import os
import subprocess

from modo_bugs import scrape_announcements, scrape_forum, update, verification
from shared import configuration


def run(argv: tuple[str]) -> None:
    configuration.bugs_webhook_id.get()
    configuration.bugs_webhook_token.get()

    args = list(argv)
    logger = logging.getLogger(__name__)
    wd = configuration.get_str('modo_bugs_dir')
    if not os.path.exists(wd):
        subprocess.run(['git', 'clone', 'https://github.com/PennyDreadfulMTG/modo-bugs.git', wd], check=True)
    os.chdir(wd)
    subprocess.run(['git', 'pull'], check=True)
    if not args:
        args.extend(['scrape_an', 'update', 'scrape_forum', 'verify', 'commit'])
    logger.info('modo_bugs invoked with modes: ' + repr(args))

    changes: list[str] = []

    try:
        if 'scrape_an' in args:
            scrape_announcements.main(changes)
    except Exception as e:
        logging.exception(e)

    if 'update' in args:
        update.main()
    if 'scrape_forum' in args:
        scrape_forum.main()
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
