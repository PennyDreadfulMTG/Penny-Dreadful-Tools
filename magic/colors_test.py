from magic import colors, oracle

def test_find_colors() -> None:
    delver_of_secrets = oracle.load_card('Delver of Secrets')
    dead_gone = oracle.load_card('Dead // Gone')  # => R
    breaking_entering = oracle.load_card('Breaking // Entering')  # => B
    claim_fame = oracle.load_card('Claim // Fame') # => ? R? Or'  #) nothing?
    fire_ice = oracle.load_card('Fire // Ice')  # => nothing
    bala_ged_recovery = oracle.load_card('Bala Ged Recovery')  # => G (or') nothi  #ng?)
    birgi_god_of_storytelling = oracle.load_card('Birgi, God of Storytelling')  # => R
    valentin_dead_of_the_vein = oracle.load_card('Valentin, Dean of the Vein')  # => nothing
    archangel_avacyn = oracle.load_card('Archangel Avacyn')  # => W
    ravenous_trap = oracle.load_card('Ravenous Trap')  # => nothing
    ricochet_trap = oracle.load_card('Ricochet Trap')  # => R
    damn = oracle.load_card('Damn')  # => nothing
    kellan_daring_traveler = oracle.load_card('Kellan, Daring Traveler')  # => nothing
    kellan_inquisitive_prodigy = oracle.load_card('Kellan, Inquisitive Prodigy')  # => UG
    kitchen_finks = oracle.load_card('Kitchen Finks')  # => nothing
    bedeck_bedazzle = oracle.load_card('Bedeck // Bedazzle')

    assert (['U'], ['U', 'U', 'U', 'U']) == colors.find_colors([delver_of_secrets, delver_of_secrets, delver_of_secrets, delver_of_secrets])
    assert (['R'], ['R']) == colors.find_colors([dead_gone])
    assert (['B'], ['B']) == colors.find_colors([breaking_entering])
    assert ([], []) == colors.find_colors([claim_fame])
    assert ([], []) == colors.find_colors([fire_ice])
    assert ([], []) == colors.find_colors([bala_ged_recovery])
    assert (['R'], ['R']) == colors.find_colors([birgi_god_of_storytelling])
    assert ([], []) == colors.find_colors([valentin_dead_of_the_vein])
    assert (['W'], ['W', 'W']) == colors.find_colors([archangel_avacyn])
    assert ([], []) == colors.find_colors([ravenous_trap])
    assert (['R'], ['R']) == colors.find_colors([ricochet_trap])
    assert ([], []) == colors.find_colors([damn])
    assert ([], []) == colors.find_colors([kellan_daring_traveler])
    assert (['G', 'U'], ['G', 'U']) == colors.find_colors([kellan_inquisitive_prodigy])
    assert ([], []) == colors.find_colors([kitchen_finks])
    assert ([], []) == colors.find_colors([bedeck_bedazzle])

    assert (['W', 'U', 'R'], ['W', 'W', 'U', 'R']) == colors.find_colors([bedeck_bedazzle, bedeck_bedazzle, archangel_avacyn, delver_of_secrets, dead_gone])
