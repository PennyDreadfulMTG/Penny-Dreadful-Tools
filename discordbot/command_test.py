from discordbot import command


def test_roughly_matches() -> None:
    assert command.roughly_matches('hello', 'hello')
    assert command.roughly_matches('signup', 'Sign Up')
    assert not command.roughly_matches('elephant', 'Tuba')
    assert command.roughly_matches('jmeka', 'j_meka')
    assert command.roughly_matches('modo bugs', 'modo-bugs')

def test_results_from_queries() -> None:
    result = command.results_from_queries(['bolt'])[0][0]
    assert result.has_match()
    assert not result.is_ambiguous()
    assert result.get_best_match() == 'Lightning Bolt'
    result = command.results_from_queries(['Far/Away'])[0][0]
    assert result.has_match()
    assert not result.is_ambiguous()
    assert result.get_best_match() == 'Far // Away'
    result = command.results_from_queries(['Jötun Grunt'])[0][0]
    assert result.has_match()
    assert not result.is_ambiguous()
    assert result.get_best_match() == 'Jötun Grunt'
    result = command.results_from_queries(['Jotun Grunt'])[0][0]
    assert result.has_match()
    assert not result.is_ambiguous()
    assert result.get_best_match() == 'Jötun Grunt'
    result = command.results_from_queries(['Ready / Willing'])[0][0]
    assert result.has_match()
    assert not result.is_ambiguous()
    assert result.get_best_match() == 'Ready // Willing'
    result = command.results_from_queries(['Fire // Ice'])[0][0]
    assert result.has_match()
    assert not result.is_ambiguous()
    assert result.get_best_match() == 'Fire // Ice'
    result = command.results_from_queries(['Upheaval'])[0][0]
    assert result.has_match()
    assert not result.is_ambiguous()
    assert result.get_best_match() == 'Upheaval'

def test_resources_matching_in_url():
    results = command.resources_resources("github")
    assert results['https://github.com/PennyDreadfulMTG/Penny-Dreadful-Tools/'] == 'Penny Dreadful Tools'

    results = command.resources_resources("starcitygames")
    assert results['https://www.starcitygames.com/article/33860_Penny-Dreadful.html'] == 'Mrs. Mulligan SCG'
