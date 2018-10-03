from decksite.view import View
from magic import tournaments


# pylint: disable=no-self-use
class TournamentHosting(View):
    def __init__(self) -> None:
        super().__init__()
        hosts = [host for series in tournaments.all_series_info() for host in series['hosts']]
        hosts += ['stash86']
        self.hosts = ', '.join(set(hosts))

    def page_title(self):
        return 'Tournament Hosting'
