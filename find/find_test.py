import pytest

from find import search
from magic import seasons, fetcher
from magic.database import db

# Some of these tests only work hooked up to a cards db, and are thus marked functional. They are fast, though, and you should run them if editing card search.
# $ python3 dev.py test find

def test_match() -> None:
    assert search.Key.match('c')
    assert search.Key.match('mana')
    assert not search.Key.match('z')
    assert not search.Key.match('')
    assert not search.Key.match(' ')
    assert not search.Criterion.match('magic:2uu')
    assert search.Criterion.match('tou>2')

# START Tests from https://scryfall.com/docs/syntax

@pytest.mark.functional
def test_colors_and_color_identity() -> None:
    s = 'c:rg'
    do_functional_test(s, ['Animar, Soul of Elements', 'Boggart Ram-Gang', 'Progenitus'], ['About Face', 'Cinder Glade', 'Lupine Prototype', 'Sylvan Library'])
    s = 'color>=uw -c:red'
    do_functional_test(s, ['Absorb', 'Arcades Sabboth', 'Bant Sureblade', 'Worldpurge'], ['Brainstorm', 'Mantis Rider', 'Karn Liberated'])
    s = 'id<=esper t:instant'
    do_functional_test(s, ['Abeyance', 'Abjure', 'Absorb', 'Ad Nauseam', 'Batwing Brume', 'Warping Wail'], ['Act of Aggression', 'Inside Out', 'Jilt'])
    s = 'id<=ESPER t:instant'
    do_functional_test(s, ['Abeyance', 'Abjure', 'Absorb', 'Ad Nauseam', 'Batwing Brume', 'Warping Wail'], ['Act of Aggression', 'Inside Out', 'Jilt'])
    s = 'c:m'
    do_functional_test(s, ['Bant Charm', 'Murderous Redcap'], ['Izzet Signet', 'Lightning Bolt', 'Spectral Procession'])
    s = 'c=br'
    do_functional_test(s, ['Murderous Redcap', 'Terminate'], ['Cruel Ultimatum', 'Fires of Undeath', 'Hymn to Tourach', 'Lightning Bolt', 'Rakdos Signet'])
    s = 'id:c t:land'
    do_functional_test(s, ['Ancient Tomb', 'Wastes'], ['Academy Ruins', 'Island', 'Nihil Spellbomb'])
    s = 'c:colorless'
    do_functional_test(s, ['Plains', "Tormod's Crypt"], ['Master of Etherium'])
    # "the four-color nicknames chaos, aggression, altruism, growth, artifice are supported"

@pytest.mark.functional
def test_types() -> None:
    s = 't:merfolk t:legend'
    do_functional_test(s, ['Emry, Lurker of the Loch', 'Sygg, River Cutthroat'], ['Hullbreacher', 'Ragavan, Nimble Pilferer'])
    s = 't:goblin -t:creature'
    do_functional_test(s, ['Tarfire', 'Warren Weirding'], ['Goblin Bombardment', 'Lightning Bolt', 'Skirk Prospector'])

    s = 't:pw'
    do_functional_test(s, ['Ugin, the Spirit Dragon', 'Kaya, Ghost Assassin'], ["Bloodchief's Thirst", 'Invasion of Azgol'])
    s = 't:/pw/'
    do_functional_test(s, [], ['Ugin, the Spirit Dragon'])

@pytest.mark.functional
def test_card_text() -> None:
    s = 'o:draw o:creature'
    do_functional_test(s, ['Edric, Spymaster of Trest', 'Grim Backwoods', 'Mystic Remora'], ['Ancestral Recall', 'Honor of the Pure'])
    s = 'o:"~ enters the battlefield tapped"'
    do_functional_test(s, ['Arcane Sanctum', 'Diregraf Ghoul', 'Golgari Guildgate'], ['Tarmogoyf'])

    s = 'fo:/sacrifice ~ .* all/'
    do_functional_test(s, ['Coercive Portal', 'Planar Collapse'], ['Tomb of Urami', 'Viscera Seer'])

@pytest.mark.functional
def test_mana_costs() -> None:
    s = 'mana:{G}{U}'
    do_functional_test(s, ['Omnath, Locus of Creation', 'Ice-Fang Coatl'], ['Breeding Pool', 'Slippery Bogle'])

    # https://github.com/PennyDreadfulMTG/Penny-Dreadful-Tools/issues/8969
    # s = 'm:2WW'
    # do_functional_test(s, ["Emeria's Call", 'Solitude'], ['Karoo', 'Spectral Procession'])
    # s = 'm>3WU'
    # do_functional_test(s, ['Drogskol Reaver', 'Sphinx of the Steel Wind'], ['Angel of the Dire Hour', 'Fractured Identity'])

    s = 'm:{R/P}'
    do_functional_test(s, ['Gut Shot', 'Slash Panther'], ['Dismember', 'Lightning Bolt'])
    s = 'c:u cmc=5'
    do_functional_test(s, ['Force of Will', 'Fractured Identity'], ['Goldspan Dragon', 'Omnath, Locus of Creation'])

    # https://github.com/PennyDreadfulMTG/Penny-Dreadful-Tools/issues/8968
    # s = 'devotion:{u/b}{u/b}{u/b}'
    # do_functional_test(s, ['Ashemnoor Gouger', 'Niv-Mizzet Parun', 'Omniscience', 'Phrexian Obliterator', 'Progenitus'], ['Cunning Nightbonger', 'Watery Grave'])

    # s = 'produces=wu'
    # do_functional_test(s, ['Azorius Signet', 'Celestial Colonnade'], ['Birds of Paradise', 'Teferi, Time Raveler'])

    # s = 'produces:rc'
    # do_functional_test(s, ['Aether Hub', 'Ramunap Ruins', 'The Seedcore', 'Talisman of Creativity', 'Grinning Ignus', 'Lithoform Blight'], ["Arcum's Astrolabe", 'Sulfur Falls', 'Birds of Paradise', 'Simian Spirit Guide', 'Pentad Prism'])
    # s = 'produces:c'
    # do_functional_test(s, ['Aether Hub', 'Channel', 'Talisman of Creativity', 'Thaumatic Compass', 'Worn Powerstone', 'Boreal Druid', 'Catacomb Sifter', 'Grand Architect'], ['Thran Portal', "Arcum's Astrolabe", 'Burst Lightning', 'Chromatic Star'])
    # s = 'produces>g'
    # do_functional_test(s, ['Aether Hub', "Arcum's Astrolabe", 'Birds of Paradise', "Llanowar Wastes", 'Lotus Bloom', 'Pentad Prism', 'Opulent Palace', 'Vivid Marsh', 'Servant of the Conduit', 'Song of Freyalise', "Mirari's Wake", 'Gruul Signet'], ['Thran Portal', 'Ramunap Ruins', 'Rofellos, Llanowar Emissary'])
    # s = 'produces>'
    # do_functional_test(s, [], ['Forest'])

@pytest.mark.functional
def test_power_toughness_and_loyalty() -> None:
    s = 'pow>=8'
    do_functional_test(s, ["Death's Shadow", 'Dragonlord Atarka', 'Emrakul, the Aeons Torn'], ['Mortivore', 'Swamp', 'Tarmogoyf', 'Wild Nacatl'])

    # https://github.com/PennyDreadfulMTG/Penny-Dreadful-Tools/issues/8970
    # s = 'pow>tou c:w t:creature'
    # do_functional_test(s, ["Kataki, War's Wage", 'Knight of Autumn'], ['Bonecrusher Giant', 'Hullbreacher', 'Swamp'])

    s = 't:planeswalker loy=3'
    do_functional_test(s, ['Jace, the Mind Sculptor', 'Liliana of the Veil'], ['Karn, the Great Creator', 'Mountain', 'Progenitus'])

@pytest.mark.functional
def test_multi_faced_cards() -> None:
    s = 'is:meld'
    do_functional_test(s, ['Hanweir Battlements', 'Hanweir Garrison'], ['Hanweir, the Writhing Township'])
    s = 'is:split'
    do_functional_test(s, ['Driven // Despair', 'Fire // Ice', 'Wear // Tear'], ['Budoka Gardener', 'Hanweir Garrison'])
    s = 'is:flip'
    do_functional_test(s, ['Budoka Gardener'], ['Hanweir Garrison', 'Fire // Ice'])
    s = 'is:transform'
    do_functional_test(s, ['Delver of Secrets', "Jace, Vryn's Prodigy"], ['Budoka Gardener', 'Hanweir Garrison', 'Fire // Ice'])
    s = 'is:meld'
    do_functional_test(s, ['Hanweir Garrison', 'Phyrexian Dragon Engine'], ['Budoka Gardener', 'Fire // Ice'])
    s = 'is:leveler'
    do_functional_test(s, ['Hexdrinker', 'Joraga Treespeaker'], ['Budoka Gardener', 'Fire // Ice'])
    s = 'is:dfc'
    do_functional_test(s, ['Delver of Secrets', 'Barkchannel Pathway'], ['Budoka Gardener', 'Fire // Ice'])
    s = 'is:dfc -is:mdfc'
    do_functional_test(s, ['Delver of Secrets'], ['Barkchannel Pathway'])
    s = 'is:mdfc'
    do_functional_test(s, ["Agadeem's Awakening", 'Bala Ged Recovery', 'Barkchannel Pathway'], ['Delver of Secrets', 'Budoka Gardener', 'Fire // Ice'])
    s = 'is:mdfc AND is:dfc'
    do_functional_test(s, ["Agadeem's Awakening", 'Bala Ged Recovery', 'Barkchannel Pathway'], ['Delver of Secrets', 'Budoka Gardener', 'Fire // Ice'])

@pytest.mark.functional
def test_spells_permanents_and_effects() -> None:
    s = 'c>=br is:spell f:duel'
    do_functional_test(s, ["Kolaghan's Command", 'Sliver Queen'], ['Cat Dragon', 'Badlands'])
    s = 'is:permanent t:rebel'
    do_functional_test(s, ['Aven Riftwatcher', 'Bound in Silence'], ['Brutal Suppression', 'Mirror Entity'])
    s = 'is:vanilla'
    do_functional_test(s, ['Grizzly Bears', 'Isamaru, Hound of Konda'], ['Giant Spider', 'Lightning Bolt', 'Tarmogoyf'])
    s = 'is:spell'
    do_functional_test(s, ['Brainstorm', 'Invasion of Alara', 'Necropotence', 'Grizzly Bears'], ['Dungeon of the Mad Mage', 'Thran Portal', "Adriana's Valor"])

# … Extra Cards and Funny Cards …

@pytest.mark.functional
def test_rarity() -> None:
    s = 'r:common t:artifact'
    do_functional_test(s, ['Court Homunculus', 'Prophetic Prism', "Tormod's Crypt"], ['Lightning Bolt', 'Master of Etherium'])
    s = 'r>=r'
    do_functional_test(s, ['Black Lotus', "Elspeth, Sun's Champion", 'Lotus Cobra'], ['Abbey Griffin', 'Tattermunge Maniac'])

    # We don't currently support `new:rarity`
    # s = 'rarity:common e:ima new:rarity'
    # do_functional_test(s, ['Darksteel Axe', 'Seeker of the Way'], ['Balustrade Spy', 'Bladewing the Risen'])

@pytest.mark.functional
def test_sets_and_blocks() -> None:
    s = 'e:war'
    do_functional_test(s, ['Blast Zone', 'Finale of Devastation', 'Tezzeret, Master of the Bridge'], ['Lightning Helix', 'Wastes'])
    # s = 'e:war is:booster'
    # do_functional_test(s, ['Blast Zone', 'Finale of Devastation'], ['Lightning Helix', 'Tezzeret, Master of the Bridge', 'Wastes'])
    # s = 'b:wwk'
    # do_functional_test(s, ['Inquisition of Kozilek', 'Jace, the Mind Sculptor', 'Misty Rainforest', 'Stoneforge Mystic'], [])
    # s = 'in:lea in:m15'
    # do_functional_test(s, ['Plains', 'Shivan Dragon'], ['Ancestral Recall', 'Chord of Calling', 'Lightning Bolt'])
    # s = 't:legendary -in:booster'
    # do_functional_test(s, ['Animatou, the Fateshifter', 'Korvold, Fae-Cursed King'], ['Retrofitter Foundry', 'Swamp', 'Wrenn and Six'])
    # s = 'is:datestamped is:prerelease'
    # do_functional_test(s, ['Mox Amber', 'Ulamog, the Ceaseless Hunger'], ['Mayor of Avabruck', 'Valakut, the Molten Pinnacle'])

# … Cubes …

@pytest.mark.functional
def test_format_legality() -> None:
    s = 'c:g t:creature f:pauper'
    do_functional_test(s, ['Nettle Sentinel', 'Rhox Brute', 'Slippery Bogle'], ['Ninja of the Deep Hours', 'Noble Hierarch', 'Utopia Sprawl'])
    # s = 'banned:legacy'
    # do_functional_test(s, ['Flash', 'Frantic Search', 'Mox Jet', 'Necropotence'], ['Delver of Secrets', 'Force of Will'])
    s = 'is:commander'
    do_functional_test(s, ['Progenitus', 'Teferi, Temporal Archmage'], ['Forest', 'Nettle Sentinel', 'Rofellos, Llanowar Emissary'])
    # s = 'is:reserved'
    # do_functional_test(s, [], [])
    # s = 'is:brawler'
    # do_functional_test(s, [], [])
    s = 'is:companion'
    do_functional_test(s, ['Lurrus of the Dream-Den', 'Treizeci, Sun of Serra'], ["Bear's Companion", 'K-9, Mark 1'])

# USD/EUR/TIX prices
# Artist, Flavor Text and Watermark
# Border, Frame, Foil and Resolution
# Games, Promos and Spotlights
# Year
# Tagger tags
# Reprints
# Languages

# Shortcuts and Nicknames
@pytest.mark.functional
def test_shortcuts_and_nicknames() -> None:
    # do_functional_test('is:colorshifted', [], [])
    do_functional_test('is:bikeland', ['Canyon Slough'], ['Barren Moor', 'Savai Triome', 'Savai Crystal'], True)
    do_functional_test('is:cycleland', ['Canyon Slough'], ['Barren Moor', 'Savai Triome', 'Savai Crystal'])
    do_functional_test('is:bicycleland', ['Canyon Slough'], ['Barren Moor', 'Savai Triome', 'Savai Crystal'])
    do_functional_test('is:bounceland', ['Dimir Aqueduct', 'Arid Archway', 'Dormant Volcano'], ['Mystic Gate'], True)
    do_functional_test('is:karoo', ['Dimir Aqueduct', 'Arid Archway', 'Dormant Volcano'], ['Mystic Gate'])
    do_functional_test('is:canopyland', ['Horizon Canopy', 'Fiery Islet'], ['City of Brass', 'Botanical Plaza', 'Scene of the Crime'], True)
    do_functional_test('is:canland', ['Horizon Canopy', 'Fiery Islet'], ['City of Brass', 'Botanical Plaza', 'Scene of the Crime'])
    do_functional_test('is:checkland', ['Drowned Catacomb', 'Hinterland Harbor'], ['Savage Lands'], True)
    do_functional_test('is:dual', ['Plateau', 'Underground Sea'], ['Island', 'Overgrown Tomb'], True)
    do_functional_test('is:fastland', ['Darkslick Shores'], ['Plains'], True)
    do_functional_test('is:fetchland', ['Scalding Tarn', 'Flooded Strand'], ['City of Brass', 'Fiery Islet', 'Prismatic Vista'])
    do_functional_test('is:filterland', ['Cascade Bluffs', 'Desolate Mire', 'Cascading Cataracts'], ['Tainted Wood'], True)
    do_functional_test('is:gainland', ['Akoum Refuge', 'Dismal Backwater'], ['City of Brass', 'Glimmerpost'])
    do_functional_test('is:painland', ['Brushland', 'Llanowar Wastes'], ['Cabal Pit', 'Elves of Deep Shadow', 'Caldera Lake'], True)
    do_functional_test('is:scryland', ['Temple of Malady'], ['Fading Hope', 'Zhalfrin Void'], True)
    do_functional_test('is:shadowland', ['Choked Estuary', 'Vineglimmer Snarl'], ['Secluded Glen', 'Counterbalance'], True)
    do_functional_test('is:snarl', ['Choked Estuary', 'Vineglimmer Snarl'], ['Secluded Glen', 'Counterbalance'])
    do_functional_test('is:shockland', ['Overgrown Tomb'], ['Boseiju, Who Shelters All', 'Tenacious Underdog'], True)
    do_functional_test('is:slowland', ['Deathcap Glade', 'Shipwreck Marsh'], ['Lantern-Lit Cavern'], True)
    do_functional_test('is:storageland', ['Bottomless Vault', 'Calciform Pools', 'Mage-Ring Network'], ['City of Shadows', 'Mercadian Bazaar', 'Storage Matrix'])
    do_functional_test('is:creatureland', ['Treetop Village', 'Creeping Tar Pit', 'Restless Bivouac', "Mishra's Factory", 'Crawling Barrens'], ["Urza's Factory", "Thespian's Stage"], True)
    do_functional_test('is:triland', ['Savage Lands'], ['Bant Charm', "Spara's Headquarters"])
    do_functional_test('is:tangoland', ['Canopy Vista'], ['Glacial Fortress', 'Thran Portal', 'Blood Moon'], True)
    do_functional_test('is:battleland', ['Canopy Vista'], ['Glacial Fortress', 'Thran Portal', 'Blood Moon'])
    # do_functional_test('is:masterpiece, [], [])

@pytest.mark.functional
def test_negating_conditions() -> None:
    s = '-fire c:r t:instant'
    do_functional_test(s, ['Abrade'], ['Cast Into the Fire'])
    s = 'o:changeling -t:creature'
    do_functional_test(s, ['Nameless Inversion'], ['Chameleon Colossus'])
    # s = 'not:reprint e:c16'
    # do_functional_test(s, [], [])
    s = 'not:permanent c:b cmc=1 Dark'
    do_functional_test(s, ['Darkness', 'Dark Ritual'], ['Darkest Hour'])

# Regular Expressions

def test_regular_expressions() -> None:
    s = 'fo:/unclosed'
    with pytest.raises(search.InvalidSearchException):
        do_test(s, '')

@pytest.mark.functional
def test_regular_expressions_functional() -> None:
    # Creatures that tap with no other payment
    s = r't:creature o:/^{T}:/'
    # Blackbloom Rogue here is dubious, but it is in Scryfall results.
    do_functional_test(s, ['Birds of Paradise', 'Mother of Runes', 'Blackbloom Rogue', 'Kazandu Tuskcaller'], ['Sunken Ruins', 'Monastery Swiftspear', 'Timeless Dragon', 'Ponder', "Arcum's Astrolabe"])

    # We don't support scryfall regx extensions yet. See https://scryfall.com/docs/regular-expressions
    # Instants that provide +X/+X effects
    # s = r't:instant o:/\spp/'
    # do_functional_test(s, ['Slip Out the Back', 'Invigorate', 'Status // Statue', 'Rites of Initiation'], ['Counterspell', "Mishra's Factory", 'Dream Trawler', 'Cranial Plating', 'Rise and Shine'])

    # Card names with “izzet” but not words like “mizzet”
    s = r'name:/\bizzet\b/'
    do_functional_test(s, ['Izzet Boilerworks', 'Ral, Izzet Viceroy'], ['Niv-Mizzet, Parun', 'Gitaxian Probe'])

    # https://scryfall.com/docs/regular-expressions

    # We don't currently support 'ft'
    # Cards that mention orcs, but not other words like sORCery or ORChard
    # s = r'o:/\b(orc|orcs)\b/ or name:/\b(orc|orcs)\b/ or ft:/\b(orc|orcs)\b/'
    # do_functional_test(s, ['Icatian Scout', 'Dire Fleet Captain', 'Orcish Captain'], ['Simic Guildgate', 'Foul Orchard', 'Knight of the White Orchid', 'Black Lotus'])
    s = r'o:/\b(orc|orcs)\b/ or name:/\b(orc|orcs)\b/'
    do_functional_test(s, ['Orcish Captain', 'Dwarven Soldier'], ['Icatian Scout', 'Dire Fleet Captain', 'Simic Guildgate', 'Foul Orchard', 'Knight of the White Orchid', 'Black Lotus'])

    # The Thingling cycle
    s = r'name:/^[^\s]+ling$/ t:shapeshifter'
    do_functional_test(s, ['Aetherling', 'Thornling'], ['Nameless Inversion', 'Changeling Outcast', 'Fling', 'Quickling'])

    # You can use forward slashes // instead of quotes with the type://, t:// oracle://, o://, flavor://, ft://, and name:// keywords to match those parts of a card using regular expressions.
    # ~ An automatic alias for the current card name or “this spell” if the card mentions itself.
    # \sm Short-hand for any mana symbol
    do_functional_test(r'o:/\sm, {T}: Add/', ['Cascade Bluffs', "Arcum's Astrolabe", 'Azorius Signet'], ['Abundant Growth', 'Ancient Den'])
    # \sc Short-hand for any colored mana symbol
    do_functional_test(r'o:/\sc, {T}: Add/', ['Cascade Bluffs'], ['Abundant Growth', 'Ancient Den', "Arcum's Astrolabe", 'Azorius Signet'])
    # \ss Short-hand for any card symbol
    # do_functional_test(r'o:/\ss, {T}: Add/', ['Cascade Bluffs'],['Abundant Growth', 'Ancient Den', "Arcum's Astrolabe", 'Azorius Signet'])
    # \smr Short-hand for any repeated mana symbol. For example, {G}{G} matches \smr
    # do_functional_test(r'o:Add /\smr/', ['Joraga Treespeaker'], ['Burning-Tree Emissary', 'Allosaurus Shepherd'])
    # \spt Short-hand for a X/X power/toughness expression
    do_functional_test(r'o:/create an? \spt black and green/', ['Kin-Tree Invocation', 'Grakmaw, Skyclave Ravager', 'Creakwood Liege'], ['Restless Cottage', 'Pharika, God of Affliction'])
    # \spp  Short-hand for a +X/+X power/toughness expression
    do_functional_test(r't:instant c<=gb cmc<=2 o:/gets \spp/', ['Giant Growth'], ['Nameless Inversion', 'Bile Blight'])
    # \smm  Short-hand for a -X/-X power/toughness expression
    do_functional_test(r't:instant c<=gb cmc<=2 o:/gets \smm/', ['Darkblast'], ['Nameless Inversion', 'Giant Growth', 'Bile Blight'])
    # \smp Short-hand for any Phyrexian card symbol, e.g. {P}, {W/P}, or {G/W/P}.
    do_functional_test(r'rage fo:/\smp/', ['Rage Extractor'], ["Dragon's Rage Channeler", 'Rage Reflection'])


# Exact Names

@pytest.mark.functional
def test_using_or() -> None:
    s = 't:fish or t:bird'
    do_functional_test(s, [], [])
    s = 't:land (a:titus or a:avon)'
    do_functional_test(s, [], [])

@pytest.mark.functional
def test_nesting_conditions() -> None:
    s = 't:legenday (t:goblin or t:elf)'
    do_functional_test(s, [], [])
    s = 'through (depths or sands or mists)'
    do_functional_test(s, ['Peer Through Depths', 'Reach Through Mists', 'Sift Through Sands'], ['Dig Through Time', 'Through the Breach'])

# Display Keywords


# END Tests from https://scryfall.com/docs/syntax

@pytest.mark.function
def test_colors_with_ints() -> None:
    do_functional_test('ci=5 t:legendary -t:creature', ['Genju of the Realm', 'Legacy Weapon'], ['Coalition Victory', 'Garth One-Eye'])
    do_functional_test('c=5 t:legendary -t:creature', ['Genju of the Realm'], ['Coalition Victory', 'Garth One-Eye', 'Legacy Weapon'])
    do_functional_test('ci<4 ci>1 t:instant cmc=2', ['Abrupt Decay', "Assassin's Trophy", 'Agony Warp', 'Ancient Grudge', 'Resounding Roar'], ['Abeyance'])
    do_functional_test('c<4 c>1 t:instant cmc=2', ['Abrupt Decay', "Assassin's Trophy", 'Agony Warp'], ['Abeyance', 'Ancient Grudge', 'Resounding Roar'])

@pytest.mark.functional
def test_past_seasons() -> None:
    do_functional_test('f:pds1', ['Mother of Runes'], ['Necropotence'])
    do_functional_test('f:pds5', ['Necropotence'], ['Mother of Runes'])
    do_functional_test('f:pds1 OR f:pds31', ['Mother of Runes', 'Necropotence'], [])
    do_functional_test('(f:pds1 OR f:pds31) -f:pds5', ['Mother of Runes'], ['Necropotence'])
    do_functional_test('f:"penny dreadful all"', ['Mother of Runes', 'Necropotence'], ['Black Lotus'])
    do_functional_test('f:"pdsall"', ['Mother of Runes', 'Necropotence'], ['Black Lotus'])

@pytest.mark.functional
def test_oracle_and_fulloracle() -> None:
    do_functional_test('o:"clue token"', ['Fae Offering'], ['Briarbridge Tracker', 'Black Lotus'])
    do_functional_test('fo:"clue token"', ['Fae Offering', 'Briarbridge Tracker'], ['Black Lotus'])
    do_functional_test('o:"That enchantment gains"', ['Balduvian Shaman'], ['Echoing Calm', 'Plains'])
    do_functional_test('fo:"That enchantment gains"', ['Balduvian Shaman'], ['Echoing Calm', 'Plains'])

@pytest.mark.functional
def test_parentheses_functional() -> None:
    with pytest.raises(search.InvalidSearchException):
        do_functional_test('(', [], [])
    do_functional_test('"("', ["Erase (Not the Urza's Legacy One)"], ['Fae Offering'])

@pytest.mark.functional
def test_edition_functional() -> None:
    do_functional_test('e:ktk', ['Flooded Strand', 'Treasure Cruise', 'Zurgo Helmsmasher'], ['Life from the Loam', 'Scalding Tarn', 'Zurgo Bellstriker'])

def test_edition() -> None:
    do_test('e:ktk', "(c.id IN (SELECT card_id FROM printing WHERE set_id IN (SELECT id FROM `set` WHERE name = 'ktk' OR code = 'ktk')))")

def test_special_chars() -> None:
    do_test('o:a_c%', "(REGEXP_REPLACE(oracle_text, '\\\\([^)]*\\\\)', '') LIKE '%%a\\_c\\%%%%')")


@pytest.mark.functional
def test_tilde_functional() -> None:
    do_functional_test('o:"sacrifice ~"', ['Abandoned Outpost', 'Black Lotus'], ['Cartel Aristocrat', 'Life from the Loam'])

def test_tilde() -> None:
    expected = "(REGEXP_REPLACE(oracle_text, '\\\\([^)]*\\\\)', '') LIKE CONCAT('%%sacrifice ', name, '%%'))"
    do_test('o:"sacrifice ~"', expected)

@pytest.mark.functional
def test_double_tilde_functional() -> None:
    do_functional_test('o:"sacrifice ~: ~ deals 2 damage to any target"', ['Blazing Torch', 'Inferno Fist'], ['Black Lotus', 'Cartel Aristocrat'])

def test_double_tilde() -> None:
    expected = "(REGEXP_REPLACE(oracle_text, '\\\\([^)]*\\\\)', '') LIKE CONCAT('%%sacrifice ', name, ': ', name, ' deals 2 damage to any target%%'))"
    do_test('o:"sacrifice ~: ~ deals 2 damage to any target"', expected)

@pytest.mark.functional
def test_color() -> None:
    do_functional_test('c<=w t:creature', ['Icehide Golem', 'Thalia, Guardian of Thraben'], ['Delver of Secrets', 'Duskwatch Recruiter', 'Enlightened Tutor', 'Mantis Rider'])

@pytest.mark.functional
def test_only_multicolored_functional() -> None:
    do_functional_test('c:m', ['Bant Charm', 'Murderous Redcap'], ['Door to Nothingness', 'Fires of Undeath', 'Lightning Bolt'])

def test_only_multicolored() -> None:
    do_test('c:m', '(c.id IN (SELECT card_id FROM card_color GROUP BY card_id HAVING COUNT(card_id) >= 2))')

def test_multicolored_with_other_colors() -> None:
    with pytest.raises(search.InvalidValueException):
        do_test('c:bm', '')

@pytest.mark.functional
def test_multicolored_coloridentity_functional() -> None:
    do_functional_test('ci>=b', ['Dark Ritual', 'Golos, Tireless Pilgrim', 'Murderous Redcap', 'Swamp'], ['Black Lotus', 'Daze', 'Plains'])

def test_multicolored_coloridentity() -> None:
    do_test('ci>=b', '((c.id IN (SELECT card_id FROM card_color_identity WHERE color_id = 3)))')

@pytest.mark.functional
def test_exclusivemulitcolored_same_functional() -> None:
    do_functional_test('ci!b', ['Dark Ritual', 'Swamp'], ['Black Lotus', 'Golos, Tireless Pilgrim', 'Muderous Redcap'])

def test_exclusivemulitcolored_same() -> None:
    do_test('ci!b', '((c.id IN (SELECT card_id FROM card_color_identity WHERE color_id = 3))) AND (c.id IN (SELECT card_id FROM card_color_identity GROUP BY card_id HAVING COUNT(card_id) <= 1))')

def test_mulitcolored_multiple() -> None:
    do_test('c=br', '((c.id IN (SELECT card_id FROM card_color WHERE color_id = 3))) AND ((c.id IN (SELECT card_id FROM card_color WHERE color_id = 4))) AND (c.id IN (SELECT card_id FROM card_color GROUP BY card_id HAVING COUNT(card_id) <= 2))')

@pytest.mark.functional
def test_multicolored_exclusive_functional() -> None:
    do_functional_test('c!br', ["Kroxa, Titan of Death's Hunger", 'Fulminator Mage', 'Murderous Redcap'], ['Bosh, Iron Golem', 'Dark Ritual', 'Fires of Undeath'])

def test_multicolored_exclusive() -> None:
    do_test('c!br', '((c.id IN (SELECT card_id FROM card_color WHERE color_id = 3))) AND ((c.id IN (SELECT card_id FROM card_color WHERE color_id = 4))) AND (c.id IN (SELECT card_id FROM card_color GROUP BY card_id HAVING COUNT(card_id) <= 2))')

@pytest.mark.functional
def test_color_identity_functional() -> None:
    yes = ['Brainstorm', 'Force of Will', 'Mystic Sanctuary', 'Venser, Shaper Savant']
    no = ['Electrolyze', 'Swamp', 'Underground Sea']
    do_functional_test('ci=u', yes, no)
    do_functional_test('cid=u', yes, no)
    do_functional_test('id=u', yes, no)

def test_color_identity() -> None:
    where = '((c.id IN (SELECT card_id FROM card_color_identity WHERE color_id = 2))) AND (c.id IN (SELECT card_id FROM card_color_identity GROUP BY card_id HAVING COUNT(card_id) <= 1))'
    do_test('ci=u', where)
    do_test('cid=u', where)
    do_test('id=u', where)
    do_test('commander=u', where)

@pytest.mark.functional
def test_color_identity_two_colors() -> None:
    do_functional_test('id:uw', ['Brainstorm', 'Dream Trawler', 'Island', 'Wastes'], ['Forbidden Alchemy', 'Lightning Bolt', 'Watery Grave'])

@pytest.mark.functional
def test_color_identity_colorless_functional() -> None:
    do_functional_test('ci:c', ['Lodestone Golem', 'Wastes'], ['Academy Ruins', 'Bosh, Iron Golem', 'Lightning Bolt', 'Plains'])

def test_color_identity_colorless() -> None:
    do_test('ci:c', '(NOT (c.id IN (SELECT card_id FROM card_color_identity WHERE color_id = 3))) AND (NOT (c.id IN (SELECT card_id FROM card_color_identity WHERE color_id = 5))) AND (NOT (c.id IN (SELECT card_id FROM card_color_identity WHERE color_id = 4))) AND (NOT (c.id IN (SELECT card_id FROM card_color_identity WHERE color_id = 2))) AND (NOT (c.id IN (SELECT card_id FROM card_color_identity WHERE color_id = 1))) AND (c.id NOT IN (SELECT card_id FROM card_color_identity))')

@pytest.mark.functional
def test_color_exclusively_functional() -> None:
    do_functional_test('c!r', ['Gut Shot', 'Lightning Bolt'], ['Bosh, Iron Golem', 'Lightning Helix', 'Mountain', 'Mox Ruby'])

def test_color_exclusively() -> None:
    do_test('c!r', '((c.id IN (SELECT card_id FROM card_color WHERE color_id = 4))) AND (c.id IN (SELECT card_id FROM card_color GROUP BY card_id HAVING COUNT(card_id) <= 1))')

@pytest.mark.functional
def test_color_exclusively2_functional() -> None:
    do_functional_test('c!rg', ['Assault // Battery', 'Destructive Revelry', 'Tattermunge Maniac'], ['Ancient Grudge', 'Lightning Bolt', 'Taiga'])

def test_color_exclusively2() -> None:
    do_test('c!rg', '((c.id IN (SELECT card_id FROM card_color WHERE color_id = 5))) AND ((c.id IN (SELECT card_id FROM card_color WHERE color_id = 4))) AND (c.id IN (SELECT card_id FROM card_color GROUP BY card_id HAVING COUNT(card_id) <= 2))')

def test_colorless_with_color() -> None:
    with pytest.raises(search.InvalidValueException):
        do_test('c:cr', '')

def test_colorless_exclusivity() -> None:
    do_test('c!c', '(c.id NOT IN (SELECT card_id FROM card_color))')

def test_colorless_exclusivity2() -> None:
    with pytest.raises(search.InvalidValueException):
        do_test('c!cr', '')

@pytest.mark.functional
def test_multiple_colors_functional() -> None:
    do_functional_test('c:rgw', ['Naya Charm', 'Progenitus', 'Reaper King', 'Transguild Courier'], ["Atarka's Command", 'Jegantha, the Wellspring'])

def test_multiple_colors() -> None:
    do_test('c:rgw', '((c.id IN (SELECT card_id FROM card_color WHERE color_id = 5))) AND ((c.id IN (SELECT card_id FROM card_color WHERE color_id = 4))) AND ((c.id IN (SELECT card_id FROM card_color WHERE color_id = 1)))')

def test_mana() -> None:
    do_test('mana=2WW', "(mana_cost = '{2}{W}{W}')")

def test_mana2() -> None:
    do_test('mana=X2/W2/WRB', "(mana_cost = '{X}{2/W}{2/W}{R}{B}')")

def test_mana3() -> None:
    do_test('mana=XRB', "(mana_cost = '{X}{R}{B}')")

def test_mana4() -> None:
    do_test('mana=15', "(mana_cost = '{15}')")

def test_mana5() -> None:
    do_test('mana=U/P', "(mana_cost = '{U/P}')")

def test_mana6() -> None:
    do_test('mana:c', "(mana_cost LIKE '%%{C}%%')")

def test_mana7() -> None:
    do_test('mana:uu', "(mana_cost LIKE '%%{U}{U}%%')")

def test_mana8() -> None:
    do_test('mana:g/u/p', "(mana_cost LIKE '%%{G/U/P}%%')")

@pytest.mark.functional
def test_hybrid_phyrexian_mana() -> None:
    do_functional_test('mana:g/u/p', ['Tamiyo, Compleated Sage'], ['Corrosive Gale', 'Gitaxian Probe'])

# https://github.com/PennyDreadfulMTG/Penny-Dreadful-Tools/issues/8975
# def test_mana8() -> None:
#     assert search.parse(search.tokenize('mana=2ww')) == search.parse(search.tokenize('mana=ww2'))

def test_uppercase() -> None:
    pd_id = db().value('SELECT id FROM format WHERE name LIKE %s', [f'{seasons.current_season_name()}%%'])
    do_test('F:pd', f"(c.id IN (SELECT card_id FROM card_legality WHERE format_id IN ({pd_id}) AND legality <> 'Banned'))")

def test_subtype() -> None:
    do_test('subtype:warrior', "(c.id IN (SELECT card_id FROM card_subtype WHERE subtype LIKE '%%warrior%%'))")

def test_not() -> None:
    do_test('t:creature -t:artifact t:legendary', "(type_line LIKE '%%creature%%') AND NOT (type_line LIKE '%%artifact%%') AND (type_line LIKE '%%legendary%%')")

def test_not_cmc() -> None:
    do_test('-cmc=2', 'NOT (cmc IS NOT NULL AND cmc = 2)')

def test_cmc() -> None:
    do_test('cmc>2', '(cmc IS NOT NULL AND cmc > 2)')
    do_test('cmc=0', '(cmc IS NOT NULL AND cmc = 0)')

def test_not_text() -> None:
    do_test('o:haste -o:deathtouch o:trample NOT o:"first strike" o:lifelink', "(REGEXP_REPLACE(oracle_text, '\\\\([^)]*\\\\)', '') LIKE '%%haste%%') AND NOT (REGEXP_REPLACE(oracle_text, '\\\\([^)]*\\\\)', '') LIKE '%%deathtouch%%') AND (REGEXP_REPLACE(oracle_text, '\\\\([^)]*\\\\)', '') LIKE '%%trample%%') AND NOT (REGEXP_REPLACE(oracle_text, '\\\\([^)]*\\\\)', '') LIKE '%%first strike%%') AND (REGEXP_REPLACE(oracle_text, '\\\\([^)]*\\\\)', '') LIKE '%%lifelink%%')")

@pytest.mark.functional
def test_color_not_text_functional() -> None:
    do_functional_test('c:b -c:r o:trample', ['Abyssal Persecutor', 'Driven // Despair'], ['Child of Alara', 'Chromanticore'])

def test_color_not_text() -> None:
    do_test('c:b -c:r o:trample', "((c.id IN (SELECT card_id FROM card_color WHERE color_id = 3))) AND NOT ((c.id IN (SELECT card_id FROM card_color WHERE color_id = 4))) AND (REGEXP_REPLACE(oracle_text, '\\\\([^)]*\\\\)', '') LIKE '%%trample%%')")

@pytest.mark.functional
def test_color_functional() -> None:
    do_functional_test('c:g', ['Destructive Revelry', 'Rofellos, Llanowar Emissary', 'Tattermunge Maniac'], ['Ancient Grudge', 'Forest', 'Lightning Bolt'])

def test_color_green() -> None:
    do_test('c:g', '((c.id IN (SELECT card_id FROM card_color WHERE color_id = 5)))')

def test_or() -> None:
    do_test('a OR b', "(name LIKE '%%a%%') OR (name LIKE '%%b%%')")

def test_bad_or() -> None:
    do_test('orgg', "(name LIKE '%%orgg%%')")

def test_or_without_args() -> None:
    with pytest.raises(search.InvalidSearchException):
        do_test('or GG', '')

def test_not_without_args() -> None:
    with pytest.raises(search.InvalidSearchException):
        do_test('c:r NOT', '')

def test_or_with_args() -> None:
    do_test('AA or GG', "(name LIKE '%%aa%%') OR (name LIKE '%%gg%%')")

def test_text() -> None:
    do_test('o:"target attacking"', "(REGEXP_REPLACE(oracle_text, '\\\\([^)]*\\\\)', '') LIKE '%%target attacking%%')")
    do_test('fulloracle:"target attacking"', "(oracle_text LIKE '%%target attacking%%')")

def test_name() -> None:
    do_test('tension turtle', "(name LIKE '%%tension%%') AND (name LIKE '%%turtle%%')")

def test_parentheses() -> None:
    do_test('x OR (a OR (b AND c))', "(name LIKE '%%x%%') OR ((name LIKE '%%a%%') OR ((name LIKE '%%b%%') AND (name LIKE '%%c%%')))")

@pytest.mark.functional
def test_toughness_functional() -> None:
    do_functional_test('c:r tou>2', ['Bonecrusher Giant', "Kroxa, Titan of Death's Hunger"], ['Endurance', 'Ragavan, Nimble Pilferer', 'Wurmcoil Engine'])

def test_toughness() -> None:
    do_test('c:r tou>2', '((c.id IN (SELECT card_id FROM card_color WHERE color_id = 4))) AND (toughness IS NOT NULL AND toughness > 2)')

def test_type() -> None:
    do_test('t:"human wizard"', "(type_line LIKE '%%human wizard%%')")

def test_power() -> None:
    do_test('t:wizard pow<2', "(type_line LIKE '%%wizard%%') AND (power IS NOT NULL AND power < 2)")

def test_mana_with_other() -> None:
    do_test('t:creature mana=WW o:lifelink', "(type_line LIKE '%%creature%%') AND (mana_cost = '{W}{W}') AND (REGEXP_REPLACE(oracle_text, '\\\\([^)]*\\\\)', '') LIKE '%%lifelink%%')")

def test_mana_alone() -> None:
    do_test('mana=2uu', "(mana_cost = '{2}{U}{U}')")

def test_or_and_parentheses() -> None:
    do_test('o:"target attacking" OR (mana=2uu AND (tou>2 OR pow>2))', "(REGEXP_REPLACE(oracle_text, '\\\\([^)]*\\\\)', '') LIKE '%%target attacking%%') OR ((mana_cost = '{2}{U}{U}') AND ((toughness IS NOT NULL AND toughness > 2) OR (power IS NOT NULL AND power > 2)))")

@pytest.mark.functional
def test_not_color_functional() -> None:
    do_functional_test('c:r -c:u', ['Lightning Bolt', 'Lightning Helix'], ['Bosh, Iron Golem', 'Electrolyze'])

def test_not_color() -> None:
    do_test('c:r -c:u', '((c.id IN (SELECT card_id FROM card_color WHERE color_id = 4))) AND NOT ((c.id IN (SELECT card_id FROM card_color WHERE color_id = 2)))')

@pytest.mark.functional
def test_complex_functional() -> None:
    do_functional_test('c:u OR (c:g tou>3)', ['Dragonlord Atarka', 'Endurance', 'Force of Negation', 'Teferi, Time Raveler', 'Venser, Shaper Savant'], ['Acidic Slime', 'Black Lotus', 'Giant Growth', 'Lightning Bolt', 'Wrenn and Six'])

def test_complex() -> None:
    do_test('c:u OR (c:g tou>3)', '((c.id IN (SELECT card_id FROM card_color WHERE color_id = 2))) OR (((c.id IN (SELECT card_id FROM card_color WHERE color_id = 5))) AND (toughness IS NOT NULL AND toughness > 3))')

def test_is_hybrid() -> None:
    do_test('is:hybrid', "((mana_cost LIKE '%%/2%%') OR (mana_cost LIKE '%%/W%%') OR (mana_cost LIKE '%%/U%%') OR (mana_cost LIKE '%%/B%%') OR (mana_cost LIKE '%%/R%%') OR (mana_cost LIKE '%%/G%%'))")

def test_is_hybrid_functional() -> None:
    do_functional_test('is:hybrid c:w', ['Spectral Procession', 'Figure of Destiny'], ['Shadow of Doubt', 'Isamaru, Hound of Konda'])

def test_is_commander() -> None:
    do_test('is:commander', "((type_line LIKE '%%legendary%%') AND ((type_line LIKE '%%creature%%') OR (REGEXP_REPLACE(oracle_text, '\\\\([^)]*\\\\)', '') LIKE CONCAT('%%', name, ' can be your commander%%'))) AND (c.id IN (SELECT card_id FROM card_legality WHERE format_id IN (4) AND legality <> 'Banned')))")

@pytest.mark.functional()
def test_smart_quotes() -> None:
    do_functional_test('o:“Art rampage”', ['Our Market Research Shows That Players Like Really Long Card Names So We Made this Card to Have the Absolute Longest Card Name Ever Elemental'], [])

@pytest.mark.functional
def test_format_functional() -> None:
    legal = ['Plains']
    not_legal = ['Black Lotus']
    do_functional_test('f:penny', legal, not_legal)
    do_functional_test('f:pd', legal, not_legal)
    do_functional_test('-f:penny', not_legal, legal)
    do_functional_test('-f:pd', not_legal, legal)
    do_functional_test('format:pd', legal, not_legal)
    do_functional_test('legal:pd', legal, not_legal)

@pytest.mark.functional
def test_is_commander_illegal_commander_functional() -> None:
    do_functional_test('c:g cmc=2 is:commander', ['Ayula, Queen Among Bears', 'Gaddock Teeg'], ['Fblthp, the Lost', 'Rofellos, Llanowar Emissary'])

def test_is_spikey() -> None:
    where = search.parse(search.tokenize('is:spikey'))
    assert 'Attune with Aether' in where
    assert 'Balance' in where
    assert "name = 'Yawgmoth''s Will'" in where

def test_parse_season() -> None:
    assert search.parse_season('pdsall') == 'ALL'
    with pytest.raises(search.InvalidValueException):
        search.parse_season('pd nonsense')
    assert search.parse_season('pd') == seasons.current_season_code()
    assert search.parse_season('penny') == seasons.current_season_code()
    with pytest.raises(search.InvalidValueException):
        assert search.parse_season('pennyd') == seasons.current_season_code()
    assert search.parse_season('pennydreadful') == seasons.current_season_code()
    assert search.parse_season('penny dreadful') == seasons.current_season_code()
    assert search.parse_season('pd0') == 'ALL'
    assert search.parse_season('pds1') == 'EMN'
    assert search.parse_season('pd 32') == 'MKM'
    assert search.parse_season('penny dreadful season 32') == 'MKM'
    with pytest.raises(search.InvalidValueException):
        search.parse_season('pds999')
    with pytest.raises(search.InvalidValueException):
        search.parse_season('penny dreadful season -1')
    with pytest.raises(search.InvalidValueException):
        search.parse_season('pd s-999')
    with pytest.raises(search.InvalidValueException):
        search.parse_season('pdXXX')
    with pytest.raises(search.InvalidValueException):
        search.parse_season('foo')
    with pytest.raises(search.InvalidValueException):
        search.parse_season('foopd1')
    assert search.parse_season('pd1') == 'EMN'

def do_functional_test(query: str, yes: list[str], no: list[str], check_scryfall: bool = False) -> None:
    results = search.search(query)
    found = [c.name for c in results]
    for name in yes:
        assert name in found
    for name in no:
        assert name not in found
    if check_scryfall:
        _, scryfall_names, _ = fetcher.search_scryfall(query)
        print(scryfall_names)
        print([c.name for c in results[:len(scryfall_names)]])
        assert [c.name for c in results[:len(scryfall_names)]] == scryfall_names

def do_test(query: str, expected: str) -> None:
    where = search.parse(search.tokenize(query))
    if where != expected:
        print(f'\nQuery: {query}\nExpected: {expected}\n  Actual: {where}')
    assert expected == where
