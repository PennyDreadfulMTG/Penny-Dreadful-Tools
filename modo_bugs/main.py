import os
import subprocess

from modo_bugs import scrape_bugblog, update, verification
from shared import configuration


def run() -> None:
    wd = configuration.get_str('modo_bugs_dir')
    if not os.path.exists(wd):
        subprocess.run(['git', 'clone', 'https://github.com/PennyDreadfulMTG/modo-bugs.git', wd])
    os.chdir(wd)
    scrape_bugblog.main()
    update.main()
    verification.main()
