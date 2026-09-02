from shared import text


def test_sanitize() -> None:
    assert text.sanitize("Lim-DÃ»l's High Guard") == "Lim-Dûl's High Guard"
    assert text.sanitize("Lim-Dûl's High Guard") == "Lim-Dûl's High Guard"
    assert text.sanitize('Kongming, &quot;Sleeping Dragon&quot;') == 'Kongming, "Sleeping Dragon"'
    assert text.sanitize('Ratonhnhaké꞉ton') == 'Ratonhnhaké꞉ton'

def test_replace_emoji_with_text() -> None:
    assert text.replace_emoji_with_text('Stop That✋') == 'Stop That raised hand'
    assert text.replace_emoji_with_text('🃏🔥') == 'black joker fire'
    assert text.replace_emoji_with_text('Thumb 👍🏾 Test') == 'Thumb thumbsup Test'
    assert text.replace_emoji_with_text('Developer 👩‍💻') == 'Developer woman computer'
    assert text.replace_emoji_with_text('Number 1️⃣') == 'Number 1'
    assert text.replace_emoji_with_text('🇬🇧') == 'GB'
    assert text.replace_emoji_with_text('©') == '(C)'

def test_replace_emoji_with_text_preserves_non_emoji_symbols_and_unicode() -> None:
    assert text.replace_emoji_with_text('Costs $1 + tax = 2*') == 'Costs $1 + tax = 2*'
    assert text.replace_emoji_with_text('日本語 / Ελληνικά / Кириллица') == '日本語 / Ελληνικά / Кириллица'

def test_unambiguous_prefixes() -> None:
    assert text.unambiguous_prefixes(['hello']) == ['h', 'he', 'hel', 'hell']
    assert text.unambiguous_prefixes(['price', 'person', 'prince', 'monkey']) == ['pric', 'pe', 'per', 'pers', 'perso', 'prin', 'princ', 'm', 'mo', 'mon', 'monk', 'monke']
