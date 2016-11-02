import subprocess
from decksite.view import View

# pylint: disable=no-self-use
class About(View):
    def subtitle(self):
        return 'About'

    def commit_id(self):
        return subprocess.check_output(['git', 'rev-parse', 'HEAD'])
