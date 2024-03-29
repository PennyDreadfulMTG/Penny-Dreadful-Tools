from decksite.view import View
from magic import tournaments


class TournamentHosting(View):
    def __init__(self) -> None:
        super().__init__()
        self.setup_tournament_rounds()
        hosts = [host for series in tournaments.all_series_info() for host in series['hosts']]
        hosts += ['stash86']
        self.hosts = ', '.join(set(hosts))

    def page_title(self) -> str:
        return 'Tournament Hosting'
