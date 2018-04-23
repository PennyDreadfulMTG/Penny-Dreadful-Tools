from shared import text


def test_sanitize():
    assert text.sanitize("Lim-DÃ»l's High Guard") == "Lim-Dûl's High Guard"
    assert text.sanitize("Lim-Dûl's High Guard") == "Lim-Dûl's High Guard"
    assert text.sanitize('Kongming, &quot;Sleeping Dragon&quot;') == 'Kongming, "Sleeping Dragon"'
