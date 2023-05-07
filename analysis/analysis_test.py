from analysis import analysis


def test_process_log() -> None:
    s = """
        bakert99 plays [Island].
        bakert99 casts [Portent].
        silasary casts [Red Elemental Blast] target [Portent].
        bakert99 attacks with [Worldgorger Dragon].
    """
    values = analysis.process_log(s)
    assert values == [('bakert99', 'Island'), ('bakert99', 'Portent'), ('silasary', 'Red Elemental Blast')]
