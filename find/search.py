import collections
from typing import Dict, Generator, Iterable, List, Optional, Set, Union

from find.expression import Expression
from find.tokens import BooleanOperator, Criterion, Key, Operator, Regex, String, Token
from magic import card, layout, mana, multiverse, seasons
from magic.colors import COLOR_COMBINATIONS_LOWER
from magic.database import db
from magic.models import Card
from shared.database import concat, sqlescape, sqllikeescape
from shared.pd_exception import ParseException

EXPECT_EXPRESSION = 'expect_expression'
EXPECT_OPERATOR = 'expect_operator'
EXPECT_TERM = 'expect_term'
REGEX = 'regex'
QUOTED_STRING = 'quoted_string'
UNQUOTED_STRING = 'unquoted_string'

VALUE_LOOKUP: Dict[str, Dict[str, int]] = {}

def search(query: str) -> List[Card]:
    query = query.replace('“', '"').replace('”', '"')
    where = parse(tokenize(query))
    sql = """{base_query}
        ORDER BY pd_legal DESC, name
    """.format(base_query=multiverse.cached_base_query(where))
    rs = db().select(sql)
    return [Card(r) for r in rs]

# Cut a query string up into tokens and combine them in an Expression, recursively for subexpressisons. Or raise if string is malformed.
def tokenize(s: str) -> Expression:
    s = s.lower()
    tokens: Dict[int, List[Union[Expression, Token]]] = {0: []}
    chars = list(s)
    chars.append(' ')
    depth = 0
    i = 0
    mode = EXPECT_EXPRESSION
    try:
        while i < len(chars):
            c = chars[i]
            rest = s[i:]
            if mode == EXPECT_EXPRESSION:
                if c == '(':
                    depth += 1
                    tokens[depth] = []
                elif c == ')':
                    expression = Expression(tokens[depth])
                    del tokens[depth]
                    depth -= 1
                    tokens[depth].append(expression)
                elif Criterion.match(rest):
                    tokens[depth].append(Key(rest))
                    mode = EXPECT_OPERATOR
                    i += Key.length(rest) - 1
                elif BooleanOperator.match(rest):
                    tokens[depth].append(BooleanOperator(rest))
                    mode = EXPECT_EXPRESSION
                    i += BooleanOperator.length(rest) - 1
                elif c == '"':
                    string = []
                    mode = QUOTED_STRING
                elif c == ' ':
                    pass  # noop
                elif String.match(c):
                    string = [c]
                    mode = UNQUOTED_STRING
                else:
                    raise InvalidTokenException("Expected expression, got '{c}' at character {i} in {s}".format(c=c, i=i, s=s))
            elif mode == EXPECT_OPERATOR:
                if Operator.match(rest):
                    tokens[depth].append(Operator(rest))
                    mode = EXPECT_TERM
                    i += Operator.length(rest) - 1
                else:
                    raise InvalidTokenException("Expected operator, got '{c}' at character {i} in {s}".format(c=c, i=i, s=s))
            elif mode == EXPECT_TERM:
                if c == '"':
                    string = []
                    mode = QUOTED_STRING
                elif c == '/':
                    string = []
                    mode = REGEX
                else:
                    string = [c]
                    mode = UNQUOTED_STRING
            elif mode == REGEX:
                if c == '/':
                    tokens[depth].append(Regex(''.join(string)))
                    mode = EXPECT_EXPRESSION
                else:
                    string.append(c)
            elif mode == QUOTED_STRING:
                if c == '"':
                    tokens[depth].append(String(''.join(string)))
                    mode = EXPECT_EXPRESSION
                else:
                    string.append(c)
            elif mode == UNQUOTED_STRING:
                if c == ' ':
                    tokens[depth].append(String(''.join(string)))
                    mode = EXPECT_EXPRESSION
                elif c == ')':
                    tokens[depth].append(String(''.join(string)))
                    mode = EXPECT_EXPRESSION
                    i -= 1
                else:
                    string.append(c)
            else:
                raise InvalidModeException("Bad mode '{c}' at character {i} in {s}".format(c=c, i=i, s=s))
            i += 1
    except KeyError as e:
        raise InvalidSearchException(f'Invalid nesting in {s}') from e
    if mode == QUOTED_STRING:
        raise InvalidSearchException('Reached end of expression without finding the end of a quoted string in {s}'.format(s=s))
    if mode == REGEX:
        raise InvalidSearchException(f'Reached end of expression without finding the end of a regular expression in {s}')
    if depth != 0:
        raise InvalidSearchException('Reached end of expression without finding enough closing parentheses in {s}'.format(s=s))
    return Expression(tokens[0])

# Parse an Expression into a SQL WHERE clause or raise if Expression is invalid.
def parse(expression: Expression) -> str:
    s = ''
    i = 0
    tokens = expression.tokens()
    while i < len(tokens):
        token = tokens[i]
        cls = token.__class__
        # We check the type then operate on the token, which mypy doesn't understand, so there are some `type: ignores` here.
        if cls == String:
            s += text_where('name', token)  # type: ignore
        elif cls == Key:
            try:
                s += parse_criterion(token, tokens[i + 1], tokens[i + 2])  # type: ignore
            except IndexError as e:
                raise InvalidSearchException('You cannot provide a key without both an operator and a value') from e
            i += 2
        elif cls == Expression:
            s += '({token})'.format(token=parse(token))  # type: ignore
        elif cls == BooleanOperator and i == 0 and token.value().strip() != 'NOT':  # type: ignore
            raise InvalidSearchException('You cannot start a search expression with a boolean operator')
        elif cls == BooleanOperator and i == len(tokens) - 1:
            raise InvalidSearchException('You cannot end a search expression with a boolean operator')
        elif cls == BooleanOperator:
            pass
        else:
            raise InvalidTokenException("Invalid token '{token}' ({cls}) at character {i}".format(token=token, cls=cls, i=i))
        next_token = tokens[i + 1] if len(tokens) > (i + 1) else None
        next_cls = next_token.__class__
        if cls == BooleanOperator:
            s = s.rstrip(' ')
            s += ' {s} '.format(s=token.value())  # type: ignore
        elif next_cls != BooleanOperator or next_token.value() == 'NOT':  # type: ignore
            s += ' AND '
        i += 1
    return s[:-len(' AND ')].replace('    ', ' ').strip()

# Parse key, operator and term tokens into a SQL boolean or raise if the tokens are invalid in combination.
def parse_criterion(key: Token, operator: Token, term: Token) -> str:
    if key.value() == 'q' or key.value() == 'name':
        return text_where('name', term)
    if key.value() == 'color' or key.value() == 'c':
        return color_where('color', operator.value(), term.value())
    if key.value() in ['coloridentity', 'commander', 'identity', 'ci', 'id', 'cid']:
        return color_where('color_identity', operator.value(), term.value())
    if key.value() in ['text', 'oracle', 'o', 'fulloracle', 'fo']:
        return text_where('text', term)
    if key.value() == 'type' or key.value() == 't':
        return text_where('type_line', term)
    if key.value() == 'power' or key.value() == 'pow':
        return math_where('power', operator.value(), term.value())
    if key.value() == 'toughness' or key.value() == 'tou':
        return math_where('toughness', operator.value(), term.value())
    if key.value() == 'cmc' or key.value() == 'mv':
        return math_where('cmc', operator.value(), term.value())
    if key.value() in ['loy', 'loyalty']:
        return math_where('loyalty', operator.value(), term.value())
    if key.value() == 'supertype' or key.value() == 'super':
        return subtable_where('supertype', term.value())
    if key.value() == 'subtype' or key.value() == 'sub':
        return subtable_where('subtype', term.value())
    if key.value() in ['edition', 'e', 'set', 's']:
        return set_where(term.value())
    if key.value() == 'format' or key.value() == 'f' or key.value() == 'legal':
        return format_where(term.value())
    if key.value() == 'rarity' or key.value() == 'r':
        return rarity_where(operator.value(), term.value())
    if key.value() == 'mana' or key.value() == 'm':
        return mana_where(operator.value(), term.value())
    if key.value() == 'is':
        return is_subquery(term.value())
    if key.value() == 'playable' or key.value() == 'p':
        return playable_where(term.value())
    raise InvalidCriterionException

def text_where(column: str, term: Token) -> str:
    q = term.value()
    if column == 'type_line' and q == 'pw' and not term.is_regex():
        q = 'planeswalker'
    if column.endswith('name'):
        q = card.unaccent(q)
    if column == 'text':
        column = 'oracle_text'
    if term.is_regex():
        operator = 'REGEXP'
        escaped = sqlescape('(?m)' + q)
    else:
        operator = 'LIKE'
        escaped = sqllikeescape(q)
    if column == 'oracle_text' and '~' in escaped:
        parts = ["'{text}'".format(text=text) for text in escaped.strip("'").split('~')]
        escaped = concat(intersperse(parts, 'name'))
    return f'({column} {operator} {escaped})'

def subtable_where(subtable: str, value: str, operator: Optional[str] = None) -> str:
    # Specialcase colorless because it has no entry in the color table.
    if (subtable in ['color', 'color_identity']) and value == 'c':
        return '(c.id NOT IN (SELECT card_id FROM card_{subtable}))'.format(subtable=subtable)
    v = value_lookup(subtable, value)
    if str(v).isdigit():
        column = '{subtable}_id'.format(subtable=subtable).replace('color_identity_id', 'color_id')
        operator = '=' if not operator else operator
    else:
        column = subtable
        v = sqllikeescape(v)  # type: ignore
        operator = 'LIKE' if not operator else operator
    return '(c.id IN (SELECT card_id FROM card_{subtable} WHERE {column} {operator} {value}))'.format(subtable=subtable, column=column, operator=operator, value=v)

def math_where(column: str, operator: str, term: str) -> str:
    if operator == ':':
        operator = '='
    if operator not in ['>', '<', '=', '<=', '>=']:
        return '(1 <> 1)'
    return '({column} IS NOT NULL AND {column} {operator} {term})'.format(column=column, operator=operator, term=sqlescape(term))

def color_where(subtable: str, operator: str, term: str) -> str:
    all_colors = {'w', 'u', 'b', 'r', 'g'}
    if term in COLOR_COMBINATIONS_LOWER.keys():
        colors = set(COLOR_COMBINATIONS_LOWER[term])
    else:
        colors = set(term)
    if 'c' in colors and len(colors) > 1:
        raise InvalidValueException('A card cannot be colorless and colored')
    if 'm' in colors and len(colors) > 1:
        raise InvalidValueException(f"Using 'm' with other colors is not supported, use '{subtable}>{term.replace('m', '')}' instead")
    if operator == ':' and subtable == 'color_identity':
        operator = '<='
    required: Set[str] = set()
    excluded: Set[str] = set()
    min_colors, max_colors = None, None
    if 'm' in colors:
        min_colors = 2
        colors.remove('m')
    if 'c' in colors:
        max_colors = 0
        colors.remove('c')
    if operator in ['=', '!']:
        required = colors
        max_colors = len(colors)
    elif operator == '<=':
        excluded = all_colors - colors
    elif operator in [':', '>=']:
        required = colors
    elif operator == '<':
        excluded = all_colors - colors
        max_colors = len(colors) - 1
    elif operator == '>':
        required = colors
        min_colors = len(colors) + 1
    clauses = []
    for color in sorted(required):
        clauses.append(subtable_where(subtable, color))
    for color in sorted(excluded):
        clauses.append('NOT ' + subtable_where(subtable, color))
    if min_colors:
        clauses.append(f'c.id IN (SELECT card_id FROM card_{subtable} GROUP BY card_id HAVING COUNT(card_id) >= {min_colors})')
    if max_colors:
        clauses.append(f'c.id IN (SELECT card_id FROM card_{subtable} GROUP BY card_id HAVING COUNT(card_id) <= {max_colors})')
    if max_colors == 0:
        clauses.append(f'c.id NOT IN (SELECT card_id FROM card_{subtable})')
    return '(' + ') AND ('.join(clauses) + ')'

def set_where(name: str) -> str:
    return '(c.id IN (SELECT card_id FROM printing WHERE set_id IN (SELECT id FROM `set` WHERE name = {name} OR code = {name})))'.format(name=sqlescape(name))

def format_where(term: str) -> str:
    if term == 'pd' or term.startswith('penny'):
        term = seasons.current_season_name()
    format_id = db().value('SELECT id FROM format WHERE name LIKE %s', ['{term}%%'.format(term=card.unaccent(term))])
    if format_id is None:
        raise InvalidValueException("Invalid format '{term}'".format(term=term))
    return "(c.id IN (SELECT card_id FROM card_legality WHERE format_id = {format_id} AND legality <> 'Banned'))".format(format_id=format_id)

def rarity_where(operator: str, term: str) -> str:
    rarity_id = value_lookup('rarity', term)
    if operator == ':':
        operator = '='
    if operator not in ['>', '<', '=', '<=', '>=']:
        return '(1 <> 1)'
    return '(c.id IN (SELECT card_id FROM printing WHERE rarity_id {operator} {rarity_id}))'.format(operator=operator, rarity_id=rarity_id)

def mana_where(operator: str, term: str) -> str:
    term = term.upper()
    try:
        symbols = mana.parse(term)  # Uppercasing input means you can't search for 1/2 or 1/2 white mana but w should match W.
        symbols = ['{{{symbol}}}'.format(symbol=symbol) for symbol in symbols]
    except mana.InvalidManaCostException:
        symbols = [term]
    if operator == ':':
        d = collections.Counter(symbols)  # Group identical symbols so that UU checks for {U}{U} not just {U} twice.
        clause = ' AND '.join('mana_cost LIKE {symbol}'.format(symbol=sqllikeescape(symbol * n)) for symbol, n in d.items())
    elif operator == '=':
        joined = ''.join('{symbol}'.format(symbol=symbol) for symbol in symbols)
        clause = "mana_cost = '{joined}'".format(joined=joined)
    else:
        raise InvalidTokenException('mana expects `:` or `=` not `{operator}`. Did you want cmc?'.format(operator=operator))
    return '({clause})'.format(clause=clause)

def playable_where(term: str) -> str:
    term = term.upper()
    try:
        colors = set(mana.parse(term))
    except mana.InvalidManaCostException as e:
        raise InvalidTokenException(e) from e
    symbols_without_curlies = colors.copy()
    # Colorless
    symbols_without_curlies.add('C')
    all_colors = ['W', 'U', 'B', 'R', 'G']
    # Phyrexian
    symbols_without_curlies.update(['{c}/P'.format(c=c) for c in all_colors])
    # Twobrid
    symbols_without_curlies.update(['2/{c}'.format(c=c) for c in all_colors])
    for color in colors:
        # Hybrid
        symbols_without_curlies.update(['{color}/{other}'.format(color=color, other=other) for other in all_colors if other != color])
        symbols_without_curlies.update(['{other}/{color}'.format(color=color, other=other) for other in all_colors if other != color])
    where = 'mana_cost'
    for symbol in symbols_without_curlies:
        where = "REPLACE({where}, '{{{symbol}}}', '')".format(where=where, symbol=symbol)
    return "{where} = ''".format(where=where)


# Look up the id of a value if we have a lookup table for it.
# Raise if not found in that table.
# Return 'value' back if we don't have a lookup table for this thing ('subtype', for example).
def value_lookup(table: str, value: str) -> Union[int, str]:
    if not VALUE_LOOKUP:
        init_value_lookup()
    if table in VALUE_LOOKUP and value in VALUE_LOOKUP[table]:
        return VALUE_LOOKUP[table][value]
    if table in VALUE_LOOKUP:
        raise InvalidValueException(f"Invalid value '{value}' for {table}")
    return value

def init_value_lookup() -> None:
    sql = """SELECT
        id,
        LOWER(name) AS name,
        LOWER(SUBSTR(name, 1, 1)) AS initial,
        LOWER(SUBSTR(TRIM(name), 1, INSTR({nameandspace}, ' ') - 1)) AS first_word,
        LOWER(REPLACE(name, ' ', '')) AS spaceless,
        LOWER({initials}) AS initials
    FROM {table}"""
    nameandspace = concat(['TRIM(name)', "' '"])
    second_initial = """CASE WHEN INSTR(name, ' ') > 0 THEN
                SUBSTR(name, INSTR(name, ' ') + 1, 1)
            ELSE
                ''
            END"""
    initials = concat(['SUBSTR(name, 1, 1)', second_initial])
    for table in ['color', 'rarity']:
        rs = db().select(sql.format(nameandspace=nameandspace, initials=initials, table=table))
        d = {}
        for row in rs:
            d[row['name']] = row['id']
            d[row['first_word']] = row['id']
            d[row['spaceless']] = row['id']
            # Special case because 'b' is black and 'u' is blue in colors.
            if table != 'color' or row['name'] != 'blue':
                d[row['initial']] = row['id']
                d[row['initials']] = row['id']
            else:
                d['u'] = row['id']
        VALUE_LOOKUP[table] = d
        if table == 'color':
            VALUE_LOOKUP['color_identity'] = d

def is_subquery(subquery_name: str) -> str:
    if subquery_name in layout.all_layouts():
        return '(c.layout = {layout})'.format(layout=sqlescape(subquery_name))
    if subquery_name == 'spikey':
        # This is a pretty egregious hardcoding of 426 card names but I really don't want to call Scryfall from here.
        return "(name = 'Adun Oakenshield' OR name = 'Arcades Sabboth' OR name = 'Arcbound Ravager' OR name = 'Arcum Dagsson' OR name = 'Arcum''s Astrolabe' OR name = 'Autumn Willow' OR name = 'Axelrod Gunnarson' OR name = 'Balustrade Spy' OR name = 'Barktooth Warbeard' OR name = 'Baron Sengir' OR name = 'Bartel Runeaxe' OR name = 'Biorhythm' OR name = 'Blazing Shoal' OR name = 'Boris Devilboon' OR name = 'Braids, Cabal Minion' OR name = 'Braingeyser' OR name = 'Chromium' OR name = 'Circle of Flame' OR name = 'Cloudpost' OR name = 'Coalition Victory' OR name = 'Cranial Plating' OR name = 'Cursed Scroll' OR name = 'Dakkon Blackblade' OR name = 'Darksteel Citadel' OR name = 'Dingus Egg' OR name = 'Disciple of the Vault' OR name = 'Dread Return' OR name = 'Edric, Spymaster of Trest' OR name = 'Empty the Warrens' OR name = 'Erayo, Soratami Ascendant' OR name = 'Eron the Relentless' OR name = 'Fact or Fiction' OR name = 'Frantic Search' OR name = 'Gabriel Angelfire' OR name = 'Golden Wish' OR name = 'Grandmother Sengir' OR name = 'Grapeshot' OR name = 'Hada Freeblade' OR name = 'Halfdane' OR name = 'Hazezon Tamar' OR name = 'Heartless Hidetsugu' OR name = 'Hypergenesis' OR name = 'Hypnotic Specter' OR name = 'Icy Manipulator' OR name = 'Ihsan''s Shade' OR name = 'Intangible Virtue' OR name = 'Invigorate' OR name = 'Ivory Tower' OR name = 'Jacques le Vert' OR name = 'Jasmine Boreal' OR name = 'Juggernaut' OR name = 'Kird Ape' OR name = 'Kokusho, the Evening Star' OR name = 'Lady Caleria' OR name = 'Lady Evangela' OR name = 'Lady Orca' OR name = 'Limited Resources' OR name = 'Lodestone Golem' OR name = 'Lucky Clover' OR name = 'Lutri, the Spellchaser' OR name = 'Marhault Elsdragon' OR name = 'Márton Stromgald' OR name = 'Merieke Ri Berit' OR name = 'Nicol Bolas' OR name = 'Niv-Mizzet, the Firemind' OR name = 'Orcish Oriflamme' OR name = 'Palladia-Mors' OR name = 'Panoptic Mirror' OR name = 'Pavel Maliki' OR name = 'Ponder' OR name = 'Prophet of Kruphix' OR name = 'Protean Hulk' OR name = 'Punishing Fire' OR name = 'Ramses Overdark' OR name = 'Reflector Mage' OR name = 'Regrowth' OR name = 'Riftsweeper' OR name = 'Riven Turnbull' OR name = 'Rofellos, Llanowar Emissary' OR name = 'Rohgahh of Kher Keep' OR name = 'Rubinia Soulsinger' OR name = 'Rukh Egg' OR name = 'Runed Halo' OR name = 'Second Sunrise' OR name = 'Seething Song' OR name = 'Serendib Efreet' OR name = 'Simian Spirit Guide' OR name = 'Skeleton Ship' OR name = 'Sol''kanar the Swamp King' OR name = 'Sorcerous Spyglass' OR name = 'Spatial Contortion' OR name = 'Stangg' OR name = 'Summer Bloom' OR name = 'Sunastian Falconer' OR name = 'Sway of the Stars' OR name = 'Sword of the Ages' OR name = 'Sylvan Library' OR name = 'Sylvan Primordial' OR name = 'Temporal Fissure' OR name = 'Tetsuo Umezawa' OR name = 'Thawing Glaciers' OR name = 'Thirst for Knowledge' OR name = 'Tobias Andrion' OR name = 'Tor Wauki' OR name = 'Trade Secrets' OR name = 'Treasure Cruise' OR name = 'Undercity Informer' OR name = 'Underworld Dreams' OR name = 'Vaevictis Asmadi' OR name = 'Voltaic Key' OR name = 'Wild Nacatl' OR name = 'Worldfire' OR name = 'Worldgorger Dragon' OR name = 'Xira Arien' OR name = 'Yisan, the Wanderer Bard' OR name = 'Zirda, the Dawnwaker' OR name = 'Zur the Enchanter' OR name = 'Adriana''s Valor' OR name = 'Advantageous Proclamation' OR name = 'Aether Vial' OR name = 'Aetherworks Marvel' OR name = 'Agent of Treachery' OR name = 'Ali from Cairo' OR name = 'Amulet of Quoz' OR name = 'Ancestral Recall' OR name = 'Ancestral Vision' OR name = 'Ancient Den' OR name = 'Ancient Tomb' OR name = 'Angus Mackenzie' OR name = 'Ashnod''s Coupon' OR name = 'Assemble the Rank and Vile' OR name = 'Attune with Aether' OR name = 'Ayesha Tanaka' OR name = 'Back to Basics' OR name = 'Backup Plan' OR name = 'Balance' OR name = 'Baral, Chief of Compliance' OR name = 'Bazaar of Baghdad' OR name = 'Berserk' OR name = 'Birthing Pod' OR name = 'Bitterblossom' OR name = 'Black Lotus' OR name = 'Black Vise' OR name = 'Bloodbraid Elf' OR name = 'Bloodstained Mire' OR name = 'Brago''s Favor' OR name = 'Brainstorm' OR name = 'Bridge from Below' OR name = 'Bronze Tablet' OR name = 'Burning-Tree Emissary' OR name = 'Burning Wish' OR name = 'Candelabra of Tawnos' OR name = 'Cauldron Familiar' OR name = 'Chalice of the Void' OR name = 'Chandler' OR name = 'Channel' OR name = 'Chaos Orb' OR name = 'Chrome Mox' OR name = 'Cloud of Faeries' OR name = 'Contract from Below' OR name = 'Copy Artifact' OR name = 'Counterspell' OR name = 'Crop Rotation' OR name = 'Crucible of Worlds' OR name = 'Cunning Wish' OR name = 'Dark Depths' OR name = 'Darkpact' OR name = 'Dark Ritual' OR name = 'Daughter of Autumn' OR name = 'Daze' OR name = 'Deathrite Shaman' OR name = 'Death Wish' OR name = 'Demonic Attorney' OR name = 'Demonic Consultation' OR name = 'Demonic Tutor' OR name = 'Derevi, Empyrial Tactician' OR name = 'Dig Through Time' OR name = 'Divine Intervention' OR name = 'Doomsday' OR name = 'Double Cross' OR name = 'Double Deal' OR name = 'Double Dip' OR name = 'Double Play' OR name = 'Double Stroke' OR name = 'Double Take' OR name = 'Drannith Magistrate' OR name = 'Dreadhorde Arcanist' OR name = 'Dream Halls' OR name = 'Earthcraft' OR name = 'Echoing Boon' OR name = 'Edgar Markov' OR name = 'Emissary''s Ploy' OR name = 'Emrakul, the Aeons Torn' OR name = 'Emrakul, the Promised End' OR name = 'Enlightened Tutor' OR name = 'Enter the Dungeon' OR name = 'Entomb' OR name = 'Escape to the Wilds' OR name = 'Expedition Map' OR name = 'Eye of Ugin' OR name = 'Faithless Looting' OR name = 'Fall from Favor' OR name = 'Falling Star' OR name = 'Fastbond' OR name = 'Feldon''s Cane' OR name = 'Felidar Guardian' OR name = 'Field of the Dead' OR name = 'Fires of Invention' OR name = 'Flash' OR name = 'Flooded Strand' OR name = 'Fluctuator' OR name = 'Food Chain' OR name = 'Fork' OR name = 'Gaea''s Cradle' OR name = 'Gauntlet of Might' OR name = 'General Jarkeld' OR name = 'Gifts Ungiven' OR name = 'Gitaxian Probe' OR name = 'Glimpse of Nature' OR name = 'Goblin Lackey' OR name = 'Goblin Recruiter' OR name = 'Golgari Grave-Troll' OR name = 'Golos, Tireless Pilgrim' OR name = 'Gosta Dirk' OR name = 'Great Furnace' OR name = 'Green Sun''s Zenith' OR name = 'Grim Monolith' OR name = 'Grindstone' OR name = 'Griselbrand' OR name = 'Growth Spiral' OR name = 'Gush' OR name = 'Gwendlyn Di Corci' OR name = 'Hammerheim' OR name = 'Hazduhr the Abbot' OR name = 'Hermit Druid' OR name = 'High Tide' OR name = 'Hired Heist' OR name = 'Hogaak, Arisen Necropolis' OR name = 'Hold the Perimeter' OR name = 'Hullbreacher' OR name = 'Humility' OR name = 'Hunding Gjornersen' OR name = 'Hurkyl''s Recall' OR name = 'Hymn of the Wilds' OR name = 'Hymn to Tourach' OR name = 'Illusionary Mask' OR name = 'Immediate Action' OR name = 'Imperial Seal' OR name = 'Incendiary Dissent' OR name = 'Inverter of Truth' OR name = 'Iona, Shield of Emeria' OR name = 'Irini Sengir' OR name = 'Iterative Analysis' OR name = 'Jace, the Mind Sculptor' OR name = 'Jedit Ojanen' OR name = 'Jerrard of the Closed Fist' OR name = 'Jeweled Bird' OR name = 'Johan' OR name = 'Joven' OR name = 'Karakas' OR name = 'Karn, the Great Creator' OR name = 'Kasimir the Lone Wolf' OR name = 'Kei Takahashi' OR name = 'Kethis, the Hidden Hand' OR name = 'Krark-Clan Ironworks' OR name = 'Land Tax' OR name = 'Leovold, Emissary of Trest' OR name = 'Leyline of Abundance' OR name = 'Library of Alexandria' OR name = 'Lightning Bolt' OR name = 'Lingering Souls' OR name = 'Lin Sivvi, Defiant Hero' OR name = 'Lion''s Eye Diamond' OR name = 'Living Wish' OR name = 'Livonya Silone' OR name = 'Lord Magnus' OR name = 'Lotus Petal' OR name = 'Lurrus of the Dream-Den' OR name = 'Magical Hacker' OR name = 'Mana Crypt' OR name = 'Mana Drain' OR name = 'Mana Vault' OR name = 'Maze of Ith' OR name = 'Memory Jar' OR name = 'Mental Misstep' OR name = 'Merchant Scroll' OR name = 'Metalworker' OR name = 'Mind Over Matter' OR name = 'Mind''s Desire' OR name = 'Mind Twist' OR name = 'Mirror Universe' OR name = 'Mishra''s Workshop' OR name = 'Moat' OR name = 'Monastery Mentor' OR name = 'Mox Diamond' OR name = 'Mox Emerald' OR name = 'Mox Jet' OR name = 'Mox Lotus' OR name = 'Mox Opal' OR name = 'Mox Pearl' OR name = 'Mox Ruby' OR name = 'Mox Sapphire' OR name = 'Muzzio''s Preparations' OR name = 'Mycosynth Lattice' OR name = 'Mystical Tutor' OR name = 'Mystic Forge' OR name = 'Mystic Sanctuary' OR name = 'Narset, Parter of Veils' OR name = 'Natural Order' OR name = 'Natural Unity' OR name = 'Nebuchadnezzar' OR name = 'Necropotence' OR name = 'Nexus of Fate' OR name = 'Oath of Druids' OR name = 'Oath of Nissa' OR name = 'Oko, Thief of Crowns' OR name = 'Omnath, Locus of Creation' OR name = 'Once More with Feeling' OR name = 'Once Upon a Time' OR name = 'Painter''s Servant' OR name = 'Paradox Engine' OR name = 'Pendelhaven' OR name = 'Peregrine Drake' OR name = 'Personal Tutor' OR name = 'Polluted Delta' OR name = 'Power Play' OR name = 'Preordain' OR name = 'Primeval Titan' OR name = 'Princess Lucrezia' OR name = 'Ragnar' OR name = 'Ramirez DePietro' OR name = 'Rampaging Ferocidon' OR name = 'Ramunap Ruins' OR name = 'Rashka the Slayer' OR name = 'Rasputin Dreamweaver' OR name = 'R&D''s Secret Lair' OR name = 'Rebirth' OR name = 'Recall' OR name = 'Recurring Nightmare' OR name = 'Replenish' OR name = 'Reveka, Wizard Savant' OR name = 'Richard Garfield, Ph.D.' OR name = 'Rishadan Port' OR name = 'Rite of Flame' OR name = 'Rogue Refiner' OR name = 'Seat of the Synod' OR name = 'Secrets of Paradise' OR name = 'Secret Summoning' OR name = 'Sensei''s Divining Top' OR name = 'Sentinel Dispatch' OR name = 'Serra Ascendant' OR name = 'Serra''s Sanctum' OR name = 'Shahrazad' OR name = 'Sinkhole' OR name = 'Sir Shandlar of Eberyn' OR name = 'Sivitri Scarzam' OR name = 'Skullclamp' OR name = 'Smuggler''s Copter' OR name = 'Sol Ring' OR name = 'Soraya the Falconer' OR name = 'Sovereign''s Realm' OR name = 'Splinter Twin' OR name = 'Squandered Resources' OR name = 'Staff of Domination' OR name = 'Staying Power' OR name = 'Stoneforge Mystic' OR name = 'Strip Mine' OR name = 'Stroke of Genius' OR name = 'Summoner''s Bond' OR name = 'Sundering Titan' OR name = 'Survival of the Fittest' OR name = 'Sword of the Meek' OR name = 'Swords to Plowshares' OR name = 'Sylvan Tutor' OR name = 'Tainted Pact' OR name = 'Teferi, Time Raveler' OR name = 'Tempest Efreet' OR name = 'Test of Endurance' OR name = 'Thassa''s Oracle' OR name = 'The Lady of the Mountain' OR name = 'The Tabernacle at Pendrell Vale' OR name = 'Thorn of Amethyst' OR name = 'Tibalt''s Trickery' OR name = 'Time Machine' OR name = 'Time Spiral' OR name = 'Timetwister' OR name = 'Time Vault' OR name = 'Time Walk' OR name = 'Time Warp' OR name = 'Timmerian Fiends' OR name = 'Tinker' OR name = 'Tolaria' OR name = 'Tolarian Academy' OR name = 'Torsten Von Ursus' OR name = 'Treachery' OR name = 'Tree of Tales' OR name = 'Trinisphere' OR name = 'Tuknir Deathlock' OR name = 'Umezawa''s Jitte' OR name = 'Underworld Breach' OR name = 'Unexpected Potential' OR name = 'Upheaval' OR name = 'Urborg' OR name = 'Ur-Drago' OR name = 'Uro, Titan of Nature''s Wrath' OR name = 'Valakut, the Molten Pinnacle' OR name = 'Vampiric Tutor' OR name = 'Vault of Whispers' OR name = 'Veil of Summer' OR name = 'Veldrane of Sengir' OR name = 'Vial Smasher the Fierce' OR name = 'Walking Ballista' OR name = 'Weight Advantage' OR name = 'Wheel of Fortune' OR name = 'Wilderness Reclamation' OR name = 'Windfall' OR name = 'Windswept Heath' OR name = 'Winota, Joiner of Forces' OR name = 'Winter Orb' OR name = 'Wooded Foothills' OR name = 'Worldknit' OR name = 'Worldly Tutor' OR name = 'Wrenn and Six' OR name = 'Yawgmoth''s Bargain' OR name = 'Yawgmoth''s Will' OR name = 'Zuran Orb')"
    if subquery_name == 'vanilla':
        return "(oracle_text = '')"
    if subquery_name == 'hybrid':
        return "((mana_cost LIKE '%%/2%%') OR (mana_cost LIKE '%%/W%%') OR (mana_cost LIKE '%%/U%%') OR (mana_cost LIKE '%%/B%%') OR (mana_cost LIKE '%%/R%%') OR (mana_cost LIKE '%%/G%%'))"
    subqueries = {
        'commander': 't:legendary (t:creature OR o:"~ can be your commander") f:commander',
        'checkland': 't:land fo:"unless you control a" fo:"} or {"',
        'creatureland': 't:land o:"becomes a"',
        'fetchland': 't:land o:"Search your library for a " (o:"land card" or o:"plains card" or o:"island card" or o:"swamp card" or o:"mountain card" or o:"forest card" or o:"gate card")',
        'gainland': 't:land o:"When ~ enters the battlefield, you gain 1 life"',
        'painland': 't:land o:"~ deals 1 damage to you."',
        'permanent': 't:artifact OR t:creature OR t:enchantment OR t:land OR t:planeswalker',
        'slowland': """t:land o:"~ doesn't untap during your next untap step." """,
        # 205.2a The card types are artifact, battle, conspiracy, creature, dungeon, enchantment, instant, land, phenomenon, plane, planeswalker, scheme, sorcery, tribal, and vanguard. See section 3, “Card Types.”
        'spell': 't:artifact OR t:battle OR t:creature OR t:enchantment OR t:instant OR t:planeswalker OR t:sorcery',
        'storageland': 'o:"storage counter"',
        'triland': 't:land fo:": Add {" fo:"}, {" fo:"}, or {" fo:"enters the battlefield tapped" -fo:cycling',
    }
    for k in list(subqueries.keys()):
        if k.endswith('land'):
            subqueries[k.replace('land', '')] = subqueries[k]
    subqueries['refuge'] = subqueries['gainland']
    subqueries['manland'] = subqueries['creatureland']
    query = subqueries.get(subquery_name, '')
    if query == '':
        raise InvalidSearchException('Did not recognize `{subquery_name}` as a value for `is:`'.format(subquery_name=subquery_name))
    query = parse(tokenize(query))
    query = '({0})'.format(query)
    return query

def intersperse(iterable: Iterable, delimiter: str) -> Generator:
    it = iter(iterable)
    yield next(it)
    for x in it:
        yield delimiter
        yield x

class InvalidSearchException(ParseException):
    pass

class InvalidTokenException(InvalidSearchException):
    pass

class InvalidModeException(InvalidSearchException):
    pass

class InvalidValueException(InvalidSearchException):
    pass

class InvalidCriterionException(InvalidSearchException):
    pass
