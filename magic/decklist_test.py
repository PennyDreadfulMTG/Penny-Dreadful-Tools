import textwrap

from magic import decklist


def test_parse() -> None:
    s = """
        3 Barter in Blood
        4 Consume Spirit
        4 Demonic Rising
        4 Devour Flesh
        2 Distress
        2 Dread Statuary
        4 Haunted Plate Mail
        3 Homicidal Seclusion
        4 Hymn to Tourach
        2 Infest
        4 Quicksand
        4 Spawning Pool
        14 Swamp
        2 Ultimate Price
        4 Underworld Connections

        Sideboard
        1 Distress
        2 Dystopia
        1 Infest
        4 Memoricide
        2 Nature's Ruin
        1 Pharika's Cure
        4 Scrabbling Claws"""
    s = textwrap.dedent(s)
    d = decklist.parse(s)
    assert sum(d['maindeck'].values()) == 60
    assert len(d['maindeck']) == 15
    assert len(d['sideboard']) == 7


def test_parse2() -> None:
    s = """
        3 Barter in Blood
        4 Consume Spirit
        4 Demonic Rising
        4 Devour Flesh
        2 Distress
        2 Dread Statuary

        4 Haunted Plate Mail
        3 Homicidal Seclusion
        4 Hymn to Tourach
        2 Infest

        4 Quicksand
        4 Spawning Pool
        14 Swamp
        2 Ultimate Price
        4 Underworld Connections

        1 Distress
        2 Dystopia
        1 Infest
        4 Memoricide
        2 Nature's Ruin
        1 Pharika's Cure
        4 Scrabbling Claws"""
    s = textwrap.dedent(s)
    d = decklist.parse(s)
    assert len(d['maindeck']) == 15
    assert len(d['sideboard']) == 7


def test_parse3() -> None:
    s = """
        3 Barter in Blood
        4 Consume Spirit
        4 Demonic Rising
        4 Devour Flesh
        2 Distress
        2 Dread Statuary
        4 Haunted Plate Mail
        3 Homicidal Seclusion
        4 Hymn to Tourach
        2 Infest
        4 Quicksand
        4 Spawning Pool
        14 Swamp
        2 Ultimate Price
        4 Underworld Connections

        1 Distress
        2 Dystopia
        1 Infest
        4 Memoricide
        2 Nature's Ruin
        1 Pharika's Cure
        4 Scrabbling Claws"""
    s = textwrap.dedent(s)
    d = decklist.parse(s)
    assert len(d['maindeck']) == 15
    assert len(d['sideboard']) == 7

def test_parse4() -> None:
    s = """








        3 Barter in Blood
        4 Consume Spirit
        4 Demonic Rising
        4 Devour Flesh
        2 Distress
        2 Dread Statuary
        4 Haunted Plate Mail
        3 Homicidal Seclusion
        4 Hymn to Tourach
        2 Infest
        4 Quicksand
        4 Spawning Pool
        14 Swamp
        2 Ultimate Price
        4 Underworld Connections

        Sideboard
        1 Distress
        2 Dystopia
        1 Infest
        4 Memoricide
        2 Nature's Ruin
        1 Pharika's Cure
        4 Scrabbling Claws





    """
    s = textwrap.dedent(s)
    d = decklist.parse(s)
    assert len(d['maindeck']) == 15
    assert len(d['sideboard']) == 7

def test_parse5() -> None:
    s = """
        4 Animist's Awakening
        4 Copperhorn Scout
        14 Forest
        4 Harvest Season
        4 Jaddi Offshoot
        4 Krosan Wayfarer
        4 Loam Dryad
        4 Nantuko Monastery
        4 Nest Invader
        4 Quest for Renewal
        4 Rofellos, Llanowar Emissary
        2 Sky Skiff
        4 Throne of the God-Pharaoh

        0 Villainous Wealth
    """
    s = textwrap.dedent(s)
    d = decklist.parse(s)
    assert len(d['maindeck']) == 13
    assert len(d['sideboard']) == 0

# Test that a 71 card deck includes the last 15 as sideboard
def test_parse6() -> None:
    s = """
        4 Animist's Awakening
        4 Copperhorn Scout
        15 Forest
        4 Harvest Season
        4 Jaddi Offshoot
        4 Krosan Wayfarer
        4 Loam Dryad
        4 Nantuko Monastery
        4 Nest Invader
        4 Quest for Renewal
        4 Rofellos, Llanowar Emissary
        2 Sky Skiff
        4 Throne of the God-Pharaoh
        1 Distress
        2 Dystopia
        1 Infest
        4 Memoricide
        2 Nature's Ruin
        1 Pharika's Cure
        4 Scrabbling Claws
    """
    s = textwrap.dedent(s)
    d = decklist.parse(s)
    assert sum(d['maindeck'].values()) == 61
    assert len(d['maindeck']) == 13
    assert len(d['sideboard']) == 7

# Test a 63 card deck + 12 sideboard
def test_parse7() -> None:
    s = """
        16 Forest
        4 Animist's Awakening
        4 Copperhorn Scout
        4 Harvest Season
        4 Jaddi Offshoot
        4 Krosan Wayfarer
        4 Loam Dryad
        4 Nantuko Monastery
        4 Nest Invader
        4 Quest for Renewal
        4 Rofellos, Llanowar Emissary
        4 Sky Skiff
        4 Dystopia
        1 Infest
        4 Memoricide
        2 Nature's Ruin
        1 Pharika's Cure
        4 Scrabbling Claws
    """
    s = textwrap.dedent(s)
    d = decklist.parse(s)
    assert sum(d['maindeck'].values()) == 64
    assert sum(d['sideboard'].values()) == 12
    assert len(d['maindeck']) == 13
    assert len(d['sideboard']) == 5

# Test a 61 card deck + 15 sideboard with one-offs around the cut
def test_parse8() -> None:
    s = """
        24 Island
        4 Curious Homunculus
        4 Prism Ring
        4 Anticipate
        4 Take Inventory
        4 Dissolve
        3 Void Shatter
        3 Jace's Sanctum
        3 Whelming Wave
        2 Control Magic
        2 Confirm Suspicions
        2 Counterbore
        1 Rise from the Tides
        1 Cryptic Serpent
        1 Convolute
        1 Lone Revenant
        1 Careful Consideration
        1 Opportunity
        4 Annul
        4 Invasive Surgery
        3 Sentinel Totem
    """
    s = textwrap.dedent(s)
    d = decklist.parse(s)
    assert sum(d['maindeck'].values()) == 61
    assert sum(d['sideboard'].values()) == 15
    assert d['maindeck']['Cryptic Serpent'] == 1
    assert d['sideboard']['Convolute'] == 1

# Test a Gatherling deck with no sideboard
def test_parse9() -> None:
    s = """
        2 Bonded Horncrest
        4 Boros Guildgate
        2 Charging Monstrosaur
        2 Frenzied Raptor
        3 Imperial Lancer
        8 Mountain
        2 Nest Robber
        2 Pious Interdiction
        9 Plains
        1 Pterodon Knight
        2 Rallying Roar
        2 Shining Aerosaur
        3 Sky Terror
        2 Slash of Talons
        4 Stone Quarry
        2 Sure Strike
        2 Swashbuckling
        3 Territorial Hammerskull
        2 Thrash of Raptors
        1 Tilonalli's Skinshifter
        2 Unfriendly Fire

        Sideboard"""
    s = textwrap.dedent(s)
    d = decklist.parse(s)
    assert sum(d['maindeck'].values()) == 60
    assert sum(d['sideboard'].values()) == 0
    assert d['maindeck']['Shining Aerosaur'] == 2

def test_parse10() -> None:
    s = """
        Sideboard"""
    s = textwrap.dedent(s)
    d = decklist.parse(s)
    assert sum(d['maindeck'].values()) == 0
    assert sum(d['sideboard'].values()) == 0

# Test a Commander deck.
def test_parse11() -> None:
    s = """
        1 Groundskeeper
        1 Jaddi Offshoot
        1 Scute Mob
        1 Frontier Guide
        1 Llanowar Scout
        1 Grazing Gladehart
        1 Mwonvuli Beast Tracker
        1 Ranging Raptors
        1 Embodiment of Fury
        1 Grove Rumbler
        1 Mina and Denn, Wildborn
        1 Cultivator of Blades
        1 Embodiment of Insight
        1 Garruk's Packleader
        1 Akoum Hellkite
        1 Baloth Woodcrasher
        1 Oran-Rief Hydra
        1 Rubblehulk
        1 Borborygmos
        1 Skarrg Goliath
        1 Myojin of Infinite Rage
        1 Apocalypse Hydra
        1 Lay of the Land
        1 Blackblade Reforged
        1 Broken Bond
        1 Evolution Charm
        1 Fork in the Road
        1 Ground Assault
        1 Rampant Growth
        1 Signal the Clans
        1 Deep Reconnaissance
        1 Elemental Bond
        1 Fires of Yavimaya
        1 Grow from the Ashes
        1 Hammer of Purphoros
        1 Harrow
        1 Journey of Discovery
        1 Nissa's Pilgrimage
        1 Retreat to Valakut
        1 Ghirapur Orrery
        1 Seek the Horizon
        1 Seer's Sundial
        1 Splendid Reclamation
        1 Overwhelming Stampede
        1 Rude Awakening
        1 Nissa's Renewal
        1 Animist's Awakening
        1 Clan Defiance
        1 Blighted Woodland
        1 Evolving Wilds
        16 Forest
        1 Gruul Guildgate
        1 Kazandu Refuge
        14 Mountain
        1 Mountain Valley
        1 Rogue's Passage
        1 Rugged Highlands
        1 Sylvan Ranger
        1 Vinelasher Kudzu
        1 Viridian Emissary
        1 Zhur-Taa Druid
        1 Tunneling Geopede
        1 World Shaper
        1 Zendikar Incarnate
        1 Verdant Force
        1 Strata Scythe
        1 Sylvan Awakening
        1 The Mending of Dominaria
        1 Zendikar's Roil
        1 Sunbird's Invocation
        1 Zendikar Resurgent
        1 Timber Gorge
        """
    s = textwrap.dedent(s)
    d = decklist.parse(s)
    assert sum(d['maindeck'].values()) == 100
    assert sum(d['sideboard'].values()) == 0
    assert d['maindeck']['Timber Gorge'] == 1

# Test a deck that looks a bit like a Commander deck but isn't one.
def test_parse12() -> None:
    s = """
        1 Felidar Sovereign
        3 Elixir of Immortality
        4 Ivory Tower
        4 Rest for the Weary
        4 Revitalize
        2 Banishing Light
        4 Healing Hands
        4 Renewed Faith
        4 Reviving Dose
        4 Ritual of Rejuvenation
        3 Survival Cache
        4 Faith's Fetters
        2 Boon Reflection
        3 End Hostilities
        4 Planar Outburst
        1 Final Judgment
        2 Sanguine Sacrament
        4 Encroaching Wastes
        2 Kjeldoran Outpost
        19 Plains
        4 Thawing Glaciers
        3 Urza's Factory
        2 Cataclysmic Gearhulk
        1 Felidar Sovereign
        2 Purify the Grave
        4 Scrabbling Claws
        1 Banishing Light
        4 Invoke the Divine
        1 End Hostilities
        """
    s = textwrap.dedent(s)
    d = decklist.parse(s)
    assert sum(d['maindeck'].values()) == 85
    assert sum(d['sideboard'].values()) == 15

# Test some zeroes as are sometimes given to us by mtggoldfish.
def test_parse13() -> None:
    s = """
        0 Feast of Blood
        3 Barter in Blood
        4 Consume Spirit
        4 Demonic Rising
        4 Devour Flesh
        2 Distress
        0 Rhox Faithmender
        2 Dread Statuary
        4 Haunted Plate Mail
        3 Homicidal Seclusion
        4 Hymn to Tourach
        2 Infest
        4 Quicksand
        4 Spawning Pool
        14 Swamp
        2 Ultimate Price
        4 Underworld Connections
        0 Island

        Sideboard
        1 Distress
        2 Dystopia
        1 Infest
        0 Scrabbling Claws
        4 Memoricide
        2 Nature's Ruin
        1 Pharika's Cure
        4 Scrabbling Claws"""
    s = textwrap.dedent(s)
    d = decklist.parse(s)
    assert sum(d['maindeck'].values()) == 60
    assert len(d['maindeck']) == 15
    assert len(d['sideboard']) == 7

def test_parse_tappedout_commander() -> None:
    s = """
        1 Altered Ego
        1 Blighted Woodland
        1 Bloodwater Entity
        1 Bogardan Hellkite
        1 Bounty of the Luxa
        1 Broken Bond
        1 Cackling Counterpart
        1 Chandra's Ignition
        1 Charmbreaker Devils
        1 Chromatic Lantern
        1 Circuitous Route
        1 Clone
        1 Confiscate
        1 Conqueror's Galleon
        1 Cryptoplasm
        1 Crystal Ball
        1 Cultivator's Caravan
        1 Curse of the Swine
        1 Dack's Duplicate
        1 Diluvian Primordial
        1 Elemental Bond
        1 Evolving Wilds
        1 Felhide Spiritbinder
        1 Flameshadow Conjuring
        1 Followed Footsteps
        9 Forest
        1 Gateway Plaza
        1 Gilded Lotus
        1 Grow from the Ashes
        1 Gruul Guildgate
        1 Gruul Signet
        1 Helm of the Host
        1 Highland Lake
        1 Identity Thief
        1 Insidious Will
        1 Intet, the Dreamer
        7 Island
        1 Izzet Guildgate
        1 Journeyer's Kite
        1 Kederekt Leviathan
        1 Memorial to Genius
        1 Memorial to Unity
        1 Memorial to War
        1 Mercurial Pretender
        1 Molten Primordial
        4 Mountain
        1 Ondu Giant
        1 Protean Raider
        1 Pyramid of the Pantheon
        1 Quasiduplicate
        1 Rampant Growth
        1 Rattleclaw Mystic
        1 Rishkar's Expertise
        1 Rogue's Passage
        1 Rugged Highlands
        1 Rupture Spire
        1 Saheeli's Artistry
        1 Salvager of Secrets
        1 Sculpting Steel
        1 Simic Guildgate
        1 Soul Foundry
        1 Spelltwine
        1 Sphinx of Uthuun
        1 Stolen Identity
        1 Sunbird's Invocation
        1 Tatyova, Benthic Druid
        1 Temur Ascendancy
        1 Thawing Glaciers
        1 Transguild Promenade
        1 Treasure Cruise
        1 Trophy Mage
        1 Trygon Predator
        1 Unexpected Results
        1 Urban Evolution
        1 Vesuvan Shapeshifter
        1 Vivid Grove
        1 Whispersilk Cloak
        1 Wildest Dreams
        1 Woodland Stream
        1 Yavimaya Hollow
        1 Zealous Conscripts
        1 Zendikar Resurgent
        1 Zndrsplt's Judgment
    """
    s = textwrap.dedent(s)
    d = decklist.parse(s)
    assert sum(d['maindeck'].values()) == 100
    assert len(d['maindeck']) == 83
    assert len(d['sideboard']) == 0

def test_parse_scryfall() -> None:
    s = """
        4 Deeproot Champion
        2 Quench
        1 Spell Rupture
        3 Terramorphic Expanse
        4 Quirion Dryad
        3 Hooting Mandrills
        1 Snapback
        4 Forest
        1 Unsummon
        4 Gitaxian Probe
        2 Prohibit
        3 Gush
        4 Peek
        2 Censor
        4 Mental Note
        2 Negate
        3 Treasure Cruise
        4 Evolving Wilds
        9 Island

        // Sideboard
        4 Scrabbling Claws
        3 Naturalize
        3 Snapback
        4 Invasive Surgery
        1 Boomerang
    """
    s = textwrap.dedent(s)
    d = decklist.parse(s)
    assert sum(d['maindeck'].values()) == 60
    assert sum(d['sideboard'].values()) == 15
