from shared import text


def test_sanitize() -> None:
    assert text.sanitize("Lim-DÃ»l's High Guard") == "Lim-Dûl's High Guard"
    assert text.sanitize("Lim-Dûl's High Guard") == "Lim-Dûl's High Guard"
    assert text.sanitize('Kongming, &quot;Sleeping Dragon&quot;') == 'Kongming, "Sleeping Dragon"'

def test_unambiguous_prefixes() -> None:
    assert text.unambiguous_prefixes(['hello']) == ['h', 'he', 'hel', 'hell']
    assert text.unambiguous_prefixes(['price', 'person', 'prince', 'monkey']) == ['pric', 'pe', 'per', 'pers', 'perso', 'prin', 'princ', 'm', 'mo', 'mon', 'monk', 'monke']
