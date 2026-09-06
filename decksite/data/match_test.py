from decksite.data import match
from shared.container import Container


def test_stats_counts_each_player_once_per_period(seeded_db: Container) -> None:
    stats = match.stats()

    assert {
        'num_players_this_week': stats['num_players_this_week'],
        'num_players_this_month': stats['num_players_this_month'],
        'num_players_this_season': stats['num_players_this_season'],
        'num_players_all_time': stats['num_players_all_time'],
    } == {
        'num_players_this_week': seeded_db.num_people,
        'num_players_this_month': seeded_db.num_people,
        'num_players_this_season': seeded_db.num_people,
        'num_players_all_time': seeded_db.num_people,
    }
