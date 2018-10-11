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

def test_do_not_choke_on_unicode() -> None:
    s = '①②④⑧⇅⊕█↑▪🐞🚫🏆⏩⏪︎📰💻▾'
    # As a whole …
    result = command.results_from_queries([s])[0][0]
    assert not result.has_match()
    # … and for each char individually.
    for result, _ in command.results_from_queries(list(s)):
        assert not result.has_match()

def test_resources_matching_in_url() -> None:
    results = command.resources_resources('github')
    assert results['https://github.com/PennyDreadfulMTG/Penny-Dreadful-Tools/'] == 'Penny Dreadful Tools'

    results = command.resources_resources('starcitygames')
    assert results['https://www.starcitygames.com/article/33860_Penny-Dreadful.html'] == 'Mrs. Mulligan SCG'

def test_escape_underscores() -> None:
    r = command.escape_underscores('simple_test')
    assert(r == 'simple\\_test')
    r = command.escape_underscores('<simple_test>')
    assert(r == '<simple_test>')
    r = command.escape_underscores('people gimmick_: <https://pennydreadfulmagic.com/people/gimmick_/>')
    assert(r == 'people gimmick\\_: <https://pennydreadfulmagic.com/people/gimmick_/>')
