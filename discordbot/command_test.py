from discordbot import command
from shared import whoosh_search


def test_roughly_matches():
    assert command.roughly_matches('hello', 'hello')
    assert command.roughly_matches('signup', 'Sign Up')
    assert not command.roughly_matches('elephant', 'Tuba')
    assert command.roughly_matches('jmeka', 'j_meka')
    assert command.roughly_matches('modo bugs', 'modo-bugs')

def test_cards_from_queries2():
    searcher = whoosh_search.WhooshSearcher()
    result = command.cards_from_queries2(['bolt'], searcher)[0]
    assert result.has_match()
    assert not result.is_ambiguous()
    assert result.get_best_match() == 'Lightning Bolt'
    result = command.cards_from_queries2(['Far/Away'], searcher)[0]
    assert result.has_match()
    assert not result.is_ambiguous()
    assert result.get_best_match() == 'Far // Away'
    result = command.cards_from_queries2(['Jötun Grunt'], searcher)[0]
    assert result.has_match()
    assert not result.is_ambiguous()
    assert result.get_best_match() == 'Jötun Grunt'
    result = command.cards_from_queries2(['Jotun Grunt'], searcher)[0]
    assert result.has_match()
    assert not result.is_ambiguous()
    assert result.get_best_match() == 'Jötun Grunt'
    result = command.cards_from_queries2(['Ready / Willing'], searcher)[0]
    assert result.has_match()
    assert not result.is_ambiguous()
    assert result.get_best_match() == 'Ready // Willing'
    result = command.cards_from_queries2(['Fire // Ice'], searcher)[0]
    assert result.has_match()
    assert not result.is_ambiguous()
    assert result.get_best_match() == 'Fire // Ice'
    result = command.cards_from_queries2(['Upheaval'], searcher)[0]
    assert result.has_match()
    assert not result.is_ambiguous()
    assert result.get_best_match() == 'Upheaval'
