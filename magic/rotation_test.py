from pathlib import Path
from tempfile import TemporaryDirectory, TemporaryFile

import pytest

from magic import rotation
from magic.models import Card
from shared import configuration
from shared.pd_exception import InvalidDataException


def test_last_run_number() -> None:
    # Mess with config so we can test this without relying on local settings
    try:
        real_legality_dir = configuration.get_str('legality_dir')
    except InvalidDataException:
        real_legality_dir = None

    # If the dir doesn't exist we return None
    configuration.CONFIG['legality_dir'] = 'total_gibberish'
    assert rotation.last_run_number() is None

    # If the dir exists, but it is empty, we return None
    with TemporaryDirectory() as tmpdir:
        configuration.CONFIG['legality_dir'] = tmpdir
        assert rotation.last_run_number() is None

        # We ignore files that aren't named Run_xxx.txt
        TemporaryFile(dir=tmpdir)
        assert rotation.last_run_number() is None

        # When there are run files we find the latest
        for i in range(1, 4):
            Path(tmpdir + f'/Run_00{i}.txt').touch()
        assert rotation.last_run_number() == 3

        # If there's an unexpected set of files we just return the highest
        Path(tmpdir + '/Run_101.txt').touch()
        Path(tmpdir + '/Run_020.txt').touch()
        Path(tmpdir + '/Run_019.txt').touch()
        assert rotation.last_run_number() == 101

    # Clean up after ourselves
    if real_legality_dir:
        configuration.CONFIG['legality_dir'] = real_legality_dir


def test_rotation_summary_combines_aliases_and_marks_latest_hit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    first = tmp_path / 'Run_001.txt'
    second = tmp_path / 'Run_002.txt'
    first.write_text('Agent Venom\n', encoding='utf-8')
    second.write_text('Rhilex the Accursed\n', encoding='utf-8')
    card = Card({'name': 'Agent Venom', 'layout': 'normal'}, predetermined_values=True)
    monkeypatch.setattr(rotation, 'files', lambda: [str(first), str(second)])
    monkeypatch.setattr(rotation.oracle, 'canonical_name_or_self', lambda name: 'Agent Venom' if name == 'Rhilex the Accursed' else name)
    monkeypatch.setattr(rotation.oracle, 'cards_by_name', lambda: {'Agent Venom': card})
    monkeypatch.setattr(rotation.redis, 'get_list', lambda _key: None)
    monkeypatch.setattr(rotation.redis, 'store', lambda _key, value, **_kwargs: value)
    monkeypatch.setattr(rotation.redis, 'sadd', lambda *_args, **_kwargs: None)

    runs, _runs_percent, cards = rotation.rotation_redis_store()

    assert runs == 2
    assert len(cards) == 1
    assert cards[0].name == 'Agent Venom'
    assert cards[0].hits == 2
    assert cards[0].hit_in_last_run is True


@pytest.mark.asyncio
async def test_rotation_hype_message_elides_next_confirmation_when_no_cards_are_undecided(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rotation, 'read_rotation_files', lambda: (rotation.TOTAL_RUNS, 100, []))
    monkeypatch.setattr(rotation.fetcher, 'decksite_url', lambda path: path)

    message = await rotation.rotation_hype_message(True)

    assert message is not None
    assert '\nUndecided: 0.\n' in message
    assert 'Next new cards confirmed' not in message


@pytest.mark.asyncio
async def test_rotation_hype_message_includes_next_confirmation_when_cards_are_undecided(monkeypatch: pytest.MonkeyPatch) -> None:
    card = Card({
        'name': 'Still Undecided',
        'hit_in_last_run': False,
        'hits': 80,
        'hits_needed': 4,
        'status': 'Undecided',
    }, predetermined_values=True)
    monkeypatch.setattr(rotation, 'read_rotation_files', lambda: (100, 60, [card]))
    monkeypatch.setattr(rotation.fetcher, 'decksite_url', lambda path: path)

    message = await rotation.rotation_hype_message(True)

    assert message is not None
    assert '\nUndecided: 1.\nNext new cards confirmed in 4 runs time.\n' in message


@pytest.mark.skip('Because CloudFlare sometimes blocks API access from Github workflow this test is flakey')
@pytest.mark.functional
def test_list_of_most_interesting() -> None:
    never_before_legal_cards = [
        Card({'name': 'Mox Jet'}),
        Card({'name': 'Black Lotus'}),
    ]
    super_playable_card = Card({'name': 'Counterspell'})
    somewhat_playable_card = Card({'name': 'Fling'})

    s = rotation.list_of_most_interesting(never_before_legal_cards + [super_playable_card, somewhat_playable_card])
    good_cards = 'Black Lotus • Mox Jet • Counterspell • Fling'
    assert s == good_cards

    garbage_cards = [
        Card({'name': 'Zombie Goliath'}),
        Card({'name': 'Wild Certaok'}),
        Card({'name': 'Moss Monster'}),
        Card({'name': 'Nessian Courser'}),
        Card({'name': 'Nettle Swine'}),
        Card({'name': 'Ogre Resister'}),
        Card({'name': 'Python'}),
        Card({'name': 'Redwood Treefolk'}),
        Card({'name': 'Renegade Demon'}),
        Card({'name': 'Russet Wolves'}),
        Card({'name': 'Spined Wurm'}),
        Card({'name': 'Thraben Purebloods'}),
        Card({'name': 'Vampire Noble'}),
        Card({'name': 'Undead Minotaur'}),
        Card({'name': 'Vastwood Gorger'}),
        Card({'name': 'Warpath Ghoul'}),
        Card({'name': 'Colossodon Yearling'}),
        Card({'name': 'Curio Vendor'}),
        Card({'name': 'Devilthorn Fox'}),
        Card({'name': 'Cyclops of One-Eyed Pass'}),
        Card({'name': 'Fomori Nomad'}),
        Card({'name': 'Hexplate Golem'}),
        Card({'name': 'Jwari Scuttler'}),
        Card({'name': 'Krovikan Scoundrel'}),
    ]

    cs = never_before_legal_cards + [super_playable_card, somewhat_playable_card] + garbage_cards
    s = rotation.list_of_most_interesting(cs)
    assert s.startswith(good_cards)
    excess = len(cs) - 25
    assert s.endswith(f'and {excess} more')
    assert s.count('•') == 24
