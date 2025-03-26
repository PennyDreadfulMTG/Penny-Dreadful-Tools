import collections
import re
from collections.abc import Generator, Iterable

from find.expression import Expression
from find.tokens import BooleanOperator, Criterion, Key, Operator, Regex, String, Token
from magic import card, layout, mana, multiverse, seasons
from magic.colors import COLOR_COMBINATIONS_LOWER
from magic.database import db
from shared import configuration
from shared.database import concat, sqlescape, sqllikeescape
from shared.pd_exception import DoesNotExistException, ParseException

EXPECT_EXPRESSION = 'expect_expression'
EXPECT_OPERATOR = 'expect_operator'
EXPECT_TERM = 'expect_term'
REGEX = 'regex'
QUOTED_STRING = 'quoted_string'
UNQUOTED_STRING = 'unquoted_string'

VALUE_LOOKUP: dict[str, dict[str, int]] = {}

def search(query: str) -> set[str]:
    query = query.replace('“', '"').replace('”', '"')
    where = parse(tokenize(query))
    base_query = multiverse.cached_base_query(where)
    sql = f'{base_query} ORDER BY NULL'
    return {r['name'] for r in db().select(sql)}

# Cut a query string up into tokens and combine them in an Expression, recursively for subexpressisons. Or raise if string is malformed.
def tokenize(s: str) -> Expression:
    s = s.lower()
    tokens: dict[int, list[Expression | Token]] = {0: []}
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
                    raise InvalidTokenException(f"Expected expression, got '{c}' at character {i} in {s}")
            elif mode == EXPECT_OPERATOR:
                if Operator.match(rest):
                    tokens[depth].append(Operator(rest))
                    mode = EXPECT_TERM
                    i += Operator.length(rest) - 1
                else:
                    raise InvalidTokenException(f"Expected operator, got '{c}' at character {i} in {s}")
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
                raise InvalidModeException(f"Bad mode '{c}' at character {i} in {s}")
            i += 1
    except KeyError as e:
        raise InvalidSearchException(f'Invalid nesting in {s}') from e
    if mode == QUOTED_STRING:
        raise InvalidSearchException(f'Reached end of expression without finding the end of a quoted string in {s}')
    if mode == REGEX:
        raise InvalidSearchException(f'Reached end of expression without finding the end of a regular expression in {s}')
    if depth != 0:
        raise InvalidSearchException(f'Reached end of expression without finding enough closing parentheses in {s}')
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
            s += f'({parse(token)})'  # type: ignore
        elif cls == BooleanOperator and i == 0 and token.value().strip() != 'NOT':  # type: ignore
            raise InvalidSearchException('You cannot start a search expression with a boolean operator')
        elif cls == BooleanOperator and i == len(tokens) - 1:
            raise InvalidSearchException('You cannot end a search expression with a boolean operator')
        elif cls == BooleanOperator:
            pass
        else:
            raise InvalidTokenException(f"Invalid token '{token}' ({cls}) at character {i}")
        next_token = tokens[i + 1] if len(tokens) > (i + 1) else None
        next_cls = next_token.__class__
        if cls == BooleanOperator:
            s = s.rstrip(' ')
            s += f' {token.value()} '  # type: ignore
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
    if key.value() == 'produces':
        return color_where('produced_mana', operator.value(), term.value())
    if key.value() in ['oracle', 'o']:
        return text_where('text', term, exclude_parenthetical=True)
    if key.value() in ['fulloracle', 'fo']:
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
    if key.value() == 'is' or key.value() == 'has':
        return is_subquery(term.value())
    if key.value() == 'not':
        return f'NOT ({is_subquery(term.value())})'
    if key.value() == 'playable' or key.value() == 'p':
        return playable_where(term.value())
    raise InvalidCriterionException

def text_where(column: str, term: Token, exclude_parenthetical: bool = False) -> str:
    q = term.value()
    if column == 'type_line' and q == 'pw' and not term.is_regex():
        q = 'planeswalker'
    if column.endswith('name'):
        q = card.unaccent(q)
    if column == 'text':
        column = 'oracle_text'
    if term.is_regex():
        operator = 'REGEXP'
        q = replace_scryfall_regex_extensions(q)
        escaped = sqlescape('(?m)' + q)
    else:
        operator = 'LIKE'
        escaped = sqllikeescape(q)
    if column == 'oracle_text' and '~' in escaped:
        parts = [f"'{text}'" for text in escaped.strip("'").split('~')]
        escaped = concat(intersperse(parts, 'name'))
    if exclude_parenthetical:
        column = f"REGEXP_REPLACE({column}, '\\\\([^)]*\\\\)', '')"
    return f'({column} {operator} {escaped})'

def subtable_where(subtable: str, value: str, operator: str | None = None) -> str:
    # Specialcase colorless for color and coloridentity because they have no entries (but not true for produced_mana).
    if (subtable in ['color', 'color_identity']) and value == 'c':
        return f'(c.id NOT IN (SELECT card_id FROM card_{subtable}))'
    v = value_lookup(subtable, value)
    if str(v).isdigit():
        column = f'{subtable}_id'.replace('color_identity_id', 'color_id').replace('produced_mana_id', 'color_id')
        operator = '=' if not operator else operator
    else:
        column = subtable
        v = sqllikeescape(v)  # type: ignore
        operator = 'LIKE' if not operator else operator
    return f'(c.id IN (SELECT card_id FROM card_{subtable} WHERE {column} {operator} {v}))'

def math_where(column: str, operator: str, term: str) -> str:
    if operator == ':':
        operator = '='
    if operator not in ['>', '<', '=', '<=', '>=']:
        return '(1 <> 1)'
    if term in ['odd', 'even']:
        val = 1 if term == 'odd' else 0
        return f'({column} IS NOT NULL AND FLOOR({column}) AND MOD(FLOOR({column}), 2) = {val})'
    return f'({column} IS NOT NULL AND {column} {operator} {sqlescape(term)})'

def color_where(subtable: str, operator: str, term: str) -> str:
    all_colors = {'w', 'u', 'b', 'r', 'g'}
    try:
        season_id = int(term)
        return f'c.id IN (SELECT card_id FROM card_{subtable} GROUP BY card_id HAVING COUNT(card_id) {operator} {season_id})'
    except ValueError:
        pass
    if term in COLOR_COMBINATIONS_LOWER.keys():
        colors = set(COLOR_COMBINATIONS_LOWER[term])
    else:
        colors = set(term)
    if 'c' in colors and len(colors) > 1 and subtable != 'produced_mana':
        raise InvalidValueException('A card cannot be colorless and colored')
    if 'm' in colors and len(colors) > 1:
        raise InvalidValueException(f"Using 'm' with other colors is not supported, use '{subtable}>{term.replace('m', '')}' instead")
    if operator == ':' and subtable == 'color_identity':
        operator = '<='
    required: set[str] = set()
    excluded: set[str] = set()
    min_colors, max_colors = None, None
    if 'm' in colors:
        min_colors = 2
        colors.remove('m')
    if 'c' in colors and subtable != 'produced_mana':
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
    season_code = parse_season(term) if term.startswith('pd') or term.startswith('penny') else None
    if season_code == seasons.ALL:
        format_ids = db().values("SELECT id FROM format WHERE name LIKE 'Penny Dreadful%%'")
    else:
        t = f'Penny Dreadful {season_code}' if season_code else term
        format_ids = db().values('SELECT id FROM format WHERE name LIKE %s', [f'{card.unaccent(t)}%%'])
    if not format_ids:
        raise InvalidValueException(f"Invalid format '{term}'")
    return f"(c.id IN (SELECT card_id FROM card_legality WHERE format_id IN ({', '.join(str(id) for id in format_ids)}) AND legality <> 'Banned'))"

def rarity_where(operator: str, term: str) -> str:
    rarity_id = value_lookup('rarity', term)
    if operator == ':':
        operator = '='
    if operator not in ['>', '<', '=', '<=', '>=']:
        return '(1 <> 1)'
    return f'(c.id IN (SELECT card_id FROM printing WHERE rarity_id {operator} {rarity_id}))'

def mana_where(operator: str, term: str) -> str:
    term = term.upper()
    try:
        symbols = mana.parse(term)  # Uppercasing input means you can't search for 1/2 or 1/2 white mana but w should match W.
        symbols = [f'{{{symbol}}}' for symbol in symbols]
    except mana.InvalidManaCostException:
        symbols = [term]
    if operator == ':':
        d = collections.Counter(symbols)  # Group identical symbols so that UU checks for {U}{U} not just {U} twice.
        clause = ' AND '.join(f'mana_cost LIKE {sqllikeescape(symbol * n)}' for symbol, n in d.items())
    elif operator == '=':
        joined = ''.join(f'{symbol}' for symbol in symbols)
        clause = f"mana_cost = '{joined}'"
    else:
        raise InvalidTokenException(f'mana expects `:` or `=` not `{operator}`. Did you want cmc?')
    return f'({clause})'

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
    symbols_without_curlies.update([f'{c}/P' for c in all_colors])
    # Twobrid
    symbols_without_curlies.update([f'2/{c}' for c in all_colors])
    for color in colors:
        # Hybrid
        symbols_without_curlies.update([f'{color}/{other}' for other in all_colors if other != color])
        symbols_without_curlies.update([f'{other}/{color}' for other in all_colors if other != color])
    where = 'mana_cost'
    for symbol in symbols_without_curlies:
        where = f"REPLACE({where}, '{{{symbol}}}', '')"
    return f"{where} = ''"


# Look up the id of a value if we have a lookup table for it.
# Raise if not found in that table.
# Return 'value' back if we don't have a lookup table for this thing ('subtype', for example).
def value_lookup(table: str, value: str) -> int | str:
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
            VALUE_LOOKUP['produced_mana'] = d

def is_subquery(subquery_name: str) -> str:
    if subquery_name == 'dfc':
        return "(c.layout IN ('transform', 'modal_dfc'))"
    if subquery_name == 'mdfc':
        subquery_name = 'modal_dfc'
    if subquery_name in layout.all_layouts():
        return f'(c.layout = {sqlescape(subquery_name)})'
    if subquery_name == 'spikey':
        names = spikey_names()
        return '(name = ' + ' OR name = '.join(sqlescape(name) for name in names) + ')'
    if subquery_name == 'vanilla':
        return "(oracle_text = '')"
    if subquery_name == 'hybrid':
        return "((mana_cost LIKE '%%/2%%') OR (mana_cost LIKE '%%/W%%') OR (mana_cost LIKE '%%/U%%') OR (mana_cost LIKE '%%/B%%') OR (mana_cost LIKE '%%/R%%') OR (mana_cost LIKE '%%/G%%'))"
    subqueries = {
        'bikeland': 't:land o:"Cycling {2}" ci=2',
        'bounceland': 't:land (o:"When this land enters, return a land you control to its owner\'s hand" OR o:/When this land enters, sacrifice it unless you return an untapped .* you control to its owner\'s hand/)',
        'canopyland': 'o:"{T}, Pay 1 life: Add {" o:"{1}, {T}, Sacrifice this land: Draw a card."',
        'commander': 't:legendary (t:creature OR o:"~ can be your commander") f:commander',
        'checkland': 't:land ci=2 fo:/unless you control an? (Plains|Island|Swamp|Mountain|Forest)/',
        'companion': 'o:"Companion — "',
        'creatureland': 't:land -t:creature o:/becomes? a.* creature/ -"Argoth, Sanctum of Nature" -o:/target .* becomes/',
        'dual': 't:land ci=2 -o:/./',
        'fastland': 't:land o:"enters tapped unless you control two or fewer other lands." -t:gate',
        'fetchland': 't:land o:/{T}, Pay 1 life, Sacrifice this land: Search your library for an? [a-z]+ or [a-z]+ card, put it onto the battlefield, then shuffle./',
        'filterland': r't:land (o:/\sm, {T}: Add \sc\sc/ OR o:/\sm, {T}: Add five mana in any combination of colors./)',
        'gainland': 't:land o:"When this land enters, you gain 1 life."',
        'historic': 't:artifact OR t:legendary OR t:saga',
        'outlaw': 't:Assassin OR t:Mercenary OR t:Pirate OR t:Rogue OR t:Warlock',
        'painland': r't:land o:/Add \{.\} or \{.\}. this land deals 1 damage to you./ -o:"this land enters tapped"',
        'permanent': 't:artifact OR t:creature OR t:enchantment OR t:land OR t:planeswalker',
        'scryland': 't:land "Temple of" o:"When this land enters, scry 1"',
        'shadowland': "t:land o:/As this land enters, you may reveal an? [a-z]+ or [a-z]+ card from your hand. If you don't, this land enters tapped./",
        'shockland': 't:land o:"As this land enters, you may pay 2 life. If you don\'t, it enters tapped."',
        'slowland': 't:land o:"this land enters tapped unless you control two or more other lands."',
        # 205.2a The card types are artifact, battle, conspiracy, creature, dungeon, enchantment, instant, land, phenomenon, plane, planeswalker, scheme, sorcery, tribal, and vanguard. See section 3, “Card Types.”
        'spell': 't:artifact OR t:battle OR t:creature OR t:enchantment OR t:instant OR t:planeswalker OR t:sorcery',
        'storageland': 't:land o:"storage counter" (o:"You may choose not to untap this land during your untap step." OR o:"{1}, {T}: Put a storage counter on this land")',
        'tangoland': 't:land o:"this land enters tapped unless you control two or more basic lands."',
        'triland': 't:land fo:": Add {" fo:"}, {" fo:"}, or {" fo:"enters tapped" -fo:cycling',
    }
    subqueries['refuge'] = subqueries['gainland']
    subqueries['manland'] = subqueries['creatureland']
    subqueries['bicycleland'] = subqueries['bikeland']
    subqueries['cycleland'] = subqueries['bikeland']
    subqueries['karoo'] = subqueries['bounceland']
    subqueries['canland'] = subqueries['canopyland']
    subqueries['battleland'] = subqueries['tangoland']
    subqueries['snarl'] = subqueries['shadowland']
    query = subqueries.get(subquery_name, '')
    if query == '':
        raise InvalidSearchException(f'Did not recognize `{subquery_name}` as a value for `is:`')
    query = parse(tokenize(query))
    query = f'({query})'
    return query

def spikey_names() -> list[str]:
    try:
        with open(configuration.is_spikey_file.get()) as f:
            names = [name.strip() for name in f.readlines()]
            if len(names) >= 426:
                return names
    except FileNotFoundError:
        pass
    # Hardcoded list from 2021 as backup in case the file is missing or corrupt.
    return ['Adun Oakenshield', 'Arcades Sabboth', 'Arcbound Ravager', 'Arcum Dagsson', "Arcum's Astrolabe", 'Autumn Willow', 'Axelrod Gunnarson', 'Balustrade Spy', 'Barktooth Warbeard', 'Baron Sengir', 'Bartel Runeaxe', 'Biorhythm', 'Blazing Shoal', 'Boris Devilboon', 'Braids, Cabal Minion', 'Braingeyser', 'Chromium', 'Circle of Flame', 'Cloudpost', 'Coalition Victory', 'Cranial Plating', 'Cursed Scroll', 'Dakkon Blackblade', 'Darksteel Citadel', 'Dingus Egg', 'Disciple of the Vault', 'Dread Return', 'Edric, Spymaster of Trest', 'Empty the Warrens', 'Erayo, Soratami Ascendant', 'Eron the Relentless', 'Fact or Fiction', 'Frantic Search', 'Gabriel Angelfire', 'Golden Wish', 'Grandmother Sengir', 'Grapeshot', 'Hada Freeblade', 'Halfdane', 'Hazezon Tamar', 'Heartless Hidetsugu', 'Hypergenesis', 'Hypnotic Specter', 'Icy Manipulator', "Ihsan's Shade", 'Intangible Virtue', 'Invigorate', 'Ivory Tower', 'Jacques le Vert', 'Jasmine Boreal', 'Juggernaut', 'Kird Ape', 'Kokusho, the Evening Star', 'Lady Caleria', 'Lady Evangela', 'Lady Orca', 'Limited Resources', 'Lodestone Golem', 'Lucky Clover', 'Lutri, the Spellchaser', 'Marhault Elsdragon', 'Márton Stromgald', 'Merieke Ri Berit', 'Nicol Bolas', 'Niv-Mizzet, the Firemind', 'Orcish Oriflamme', 'Palladia-Mors', 'Panoptic Mirror', 'Pavel Maliki', 'Ponder', 'Prophet of Kruphix', 'Protean Hulk', 'Punishing Fire', 'Ramses Overdark', 'Reflector Mage', 'Regrowth', 'Riftsweeper', 'Riven Turnbull', 'Rofellos, Llanowar Emissary', 'Rohgahh of Kher Keep', 'Rubinia Soulsinger', 'Rukh Egg', 'Runed Halo', 'Second Sunrise', 'Seething Song', 'Serendib Efreet', 'Simian Spirit Guide', 'Skeleton Ship', "Sol'kanar the Swamp King", 'Sorcerous Spyglass', 'Spatial Contortion', 'Stangg', 'Summer Bloom', 'Sunastian Falconer', 'Sway of the Stars', 'Sword of the Ages', 'Sylvan Library', 'Sylvan Primordial', 'Temporal Fissure', 'Tetsuo Umezawa', 'Thawing Glaciers', 'Thirst for Knowledge', 'Tobias Andrion', 'Tor Wauki', 'Trade Secrets', 'Treasure Cruise', 'Undercity Informer', 'Underworld Dreams', 'Vaevictis Asmadi', 'Voltaic Key', 'Wild Nacatl', 'Worldfire', 'Worldgorger Dragon', 'Xira Arien', 'Yisan, the Wanderer Bard', 'Zirda, the Dawnwaker', 'Zur the Enchanter', "Adriana's Valor", 'Advantageous Proclamation', 'Aether Vial', 'Aetherworks Marvel', 'Agent of Treachery', 'Ali from Cairo', 'Amulet of Quoz', 'Ancestral Recall', 'Ancestral Vision', 'Ancient Den', 'Ancient Tomb', 'Angus Mackenzie', "Ashnod's Coupon", 'Assemble the Rank and Vile', 'Attune with Aether', 'Ayesha Tanaka', 'Back to Basics', 'Backup Plan', 'Balance', 'Baral, Chief of Compliance', 'Bazaar of Baghdad', 'Berserk', 'Birthing Pod', 'Bitterblossom', 'Black Lotus', 'Black Vise', 'Bloodbraid Elf', 'Bloodstained Mire', "Brago's Favor", 'Brainstorm', 'Bridge from Below', 'Bronze Tablet', 'Burning-Tree Emissary', 'Burning Wish', 'Candelabra of Tawnos', 'Cauldron Familiar', 'Chalice of the Void', 'Chandler', 'Channel', 'Chaos Orb', 'Chrome Mox', 'Cloud of Faeries', 'Contract from Below', 'Copy Artifact', 'Counterspell', 'Crop Rotation', 'Crucible of Worlds', 'Cunning Wish', 'Dark Depths', 'Darkpact', 'Dark Ritual', 'Daughter of Autumn', 'Daze', 'Deathrite Shaman', 'Death Wish', 'Demonic Attorney', 'Demonic Consultation', 'Demonic Tutor', 'Derevi, Empyrial Tactician', 'Dig Through Time', 'Divine Intervention', 'Doomsday', 'Double Cross', 'Double Deal', 'Double Dip', 'Double Play', 'Double Stroke', 'Double Take', 'Drannith Magistrate', 'Dreadhorde Arcanist', 'Dream Halls', 'Earthcraft', 'Echoing Boon', 'Edgar Markov', "Emissary's Ploy", 'Emrakul, the Aeons Torn', 'Emrakul, the Promised End', 'Enlightened Tutor', 'Enter the Dungeon', 'Entomb', 'Escape to the Wilds', 'Expedition Map', 'Eye of Ugin', 'Faithless Looting', 'Fall from Favor', 'Falling Star', 'Fastbond', "Feldon's Cane", 'Felidar Guardian', 'Field of the Dead', 'Fires of Invention', 'Flash', 'Flooded Strand', 'Fluctuator', 'Food Chain', 'Fork', "Gaea's Cradle", 'Gauntlet of Might', 'General Jarkeld', 'Gifts Ungiven', 'Gitaxian Probe', 'Glimpse of Nature', 'Goblin Lackey', 'Goblin Recruiter', 'Golgari Grave-Troll', 'Golos, Tireless Pilgrim', 'Gosta Dirk', 'Great Furnace', "Green Sun's Zenith", 'Grim Monolith', 'Grindstone', 'Griselbrand', 'Growth Spiral', 'Gush', 'Gwendlyn Di Corci', 'Hammerheim', 'Hazduhr the Abbot', 'Hermit Druid', 'High Tide', 'Hired Heist', 'Hogaak, Arisen Necropolis', 'Hold the Perimeter', 'Hullbreacher', 'Humility', 'Hunding Gjornersen', "Hurkyl's Recall", 'Hymn of the Wilds', 'Hymn to Tourach', 'Illusionary Mask', 'Immediate Action', 'Imperial Seal', 'Incendiary Dissent', 'Inverter of Truth', 'Iona, Shield of Emeria', 'Irini Sengir', 'Iterative Analysis', 'Jace, the Mind Sculptor', 'Jedit Ojanen', 'Jerrard of the Closed Fist', 'Jeweled Bird', 'Johan', 'Joven', 'Karakas', 'Karn, the Great Creator', 'Kasimir the Lone Wolf', 'Kei Takahashi', 'Kethis, the Hidden Hand', 'Krark-Clan Ironworks', 'Land Tax', 'Leovold, Emissary of Trest', 'Leyline of Abundance', 'Library of Alexandria', 'Lightning Bolt', 'Lingering Souls', 'Lin Sivvi, Defiant Hero', "Lion's Eye Diamond", 'Living Wish', 'Livonya Silone', 'Lord Magnus', 'Lotus Petal', 'Lurrus of the Dream-Den', 'Magical Hacker', 'Mana Crypt', 'Mana Drain', 'Mana Vault', 'Maze of Ith', 'Memory Jar', 'Mental Misstep', 'Merchant Scroll', 'Metalworker', 'Mind Over Matter', "Mind's Desire", 'Mind Twist', 'Mirror Universe', "Mishra's Workshop", 'Moat', 'Monastery Mentor', 'Mox Diamond', 'Mox Emerald', 'Mox Jet', 'Mox Lotus', 'Mox Opal', 'Mox Pearl', 'Mox Ruby', 'Mox Sapphire', "Muzzio's Preparations", 'Mycosynth Lattice', 'Mystical Tutor', 'Mystic Forge', 'Mystic Sanctuary', 'Narset, Parter of Veils', 'Natural Order', 'Natural Unity', 'Nebuchadnezzar', 'Necropotence', 'Nexus of Fate', 'Oath of Druids', 'Oath of Nissa', 'Oko, Thief of Crowns', 'Omnath, Locus of Creation', 'Once More with Feeling', 'Once Upon a Time', "Painter's Servant", 'Paradox Engine', 'Pendelhaven', 'Peregrine Drake', 'Personal Tutor', 'Polluted Delta', 'Power Play', 'Preordain', 'Primeval Titan', 'Princess Lucrezia', 'Ragnar', 'Ramirez DePietro', 'Rampaging Ferocidon', 'Ramunap Ruins', 'Rashka the Slayer', 'Rasputin Dreamweaver', "R&D's Secret Lair", 'Rebirth', 'Recall', 'Recurring Nightmare', 'Replenish', 'Reveka, Wizard Savant', 'Richard Garfield, Ph.D.', 'Rishadan Port', 'Rite of Flame', 'Rogue Refiner', 'Seat of the Synod', 'Secrets of Paradise', 'Secret Summoning', "Sensei's Divining Top", 'Sentinel Dispatch', 'Serra Ascendant', "Serra's Sanctum", 'Shahrazad', 'Sinkhole', 'Sir Shandlar of Eberyn', 'Sivitri Scarzam', 'Skullclamp', "Smuggler's Copter", 'Sol Ring', 'Soraya the Falconer', "Sovereign's Realm", 'Splinter Twin', 'Squandered Resources', 'Staff of Domination', 'Staying Power', 'Stoneforge Mystic', 'Strip Mine', 'Stroke of Genius', "Summoner's Bond", 'Sundering Titan', 'Survival of the Fittest', 'Sword of the Meek', 'Swords to Plowshares', 'Sylvan Tutor', 'Tainted Pact', 'Teferi, Time Raveler', 'Tempest Efreet', 'Test of Endurance', "Thassa's Oracle", 'The Lady of the Mountain', 'The Tabernacle at Pendrell Vale', 'Thorn of Amethyst', "Tibalt's Trickery", 'Time Machine', 'Time Spiral', 'Timetwister', 'Time Vault', 'Time Walk', 'Time Warp', 'Timmerian Fiends', 'Tinker', 'Tolaria', 'Tolarian Academy', 'Torsten Von Ursus', 'Treachery', 'Tree of Tales', 'Trinisphere', 'Tuknir Deathlock', "Umezawa's Jitte", 'Underworld Breach', 'Unexpected Potential', 'Upheaval', 'Urborg', 'Ur-Drago', "Uro, Titan of Nature's Wrath", 'Valakut, the Molten Pinnacle', 'Vampiric Tutor', 'Vault of Whispers', 'Veil of Summer', 'Veldrane of Sengir', 'Vial Smasher the Fierce', 'Walking Ballista', 'Weight Advantage', 'Wheel of Fortune', 'Wilderness Reclamation', 'Windfall', 'Windswept Heath', 'Winota, Joiner of Forces', 'Winter Orb', 'Wooded Foothills', 'Worldknit', 'Worldly Tutor', 'Wrenn and Six', "Yawgmoth's Bargain", "Yawgmoth's Will", 'Zuran Orb']

def intersperse(iterable: Iterable, delimiter: str) -> Generator:
    it = iter(iterable)
    yield next(it)
    for x in it:
        yield delimiter
        yield x

def parse_season(term: str) -> str:
    spaceless = term.replace(' ', '')
    try:
        m = re.match(r'(pd|penny)(dreadful)?(s|season)?(...|\d+)?$', spaceless)
        if not m:
            raise ValueError
        if m.group(3) is m.group(4) is None:
            return seasons.current_season_code()
        if m.group(3) is not None and m.group(4) is None:
            raise InvalidValueException('Missing Penny Dreadful season identifier')
        code = m.group(4)
        try:
            return seasons.season_code(code)
        except DoesNotExistException as e:
            raise InvalidValueException(str(e)) from e
    except (AttributeError, IndexError, ValueError, DoesNotExistException):
        pass
    raise InvalidValueException(f"Could not get a Penny Dreadful season from '{term}'")

def replace_scryfall_regex_extensions(q: str) -> str:
    # Three char classes first because the other may be substrings of these …

    # \smr Short-hand for any repeated mana symbol. For example, {G}{G} matches \smr
    # q = q.replace(r'\smr', rf'({mana_symbol_pattern})\1')  # This \1 would mean neither we nor callers could ever use parens (for grouping, say) without noncapturing prefix before \smr. Might have to hardcode enumerate every combination?
    # \smh Short-hand for any hybrid card symbol. Note that monocolor Phyrexian symbols aren’t considered hybrid.
    q = q.replace(r'\smh', r'{[WUBRGP0-9]/[^P]}')
    # \smp Short-hand for any Phyrexian card symbol, e.g. {P}, {W/P}, or {G/W/P}.
    q = q.replace(r'\smp', r'{[WUBRGC/]*P}')
    # \spt Short-hand for a X/X power/toughness expression
    pt_pattern = r'([0-9]+|X)'
    q = q.replace(r'\spt', f'{pt_pattern}/{pt_pattern}')
    # \spp Short-hand for a +X/+X power/toughness expression
    q = q.replace(r'\spp', rf'\+{pt_pattern}/\+{pt_pattern}')
    # \smm Short-hand for a -X/-X power/toughness expression
    q = q.replace(r'\smm', rf'-{pt_pattern}/-{pt_pattern}')

    # … and then two char classes
    # \sm # Short-hand for any mana symbol
    mana_symbol_pattern = r'{([SWUBRGPCP0-9/]+)}'
    q = q.replace(r'\sm', mana_symbol_pattern)
    # \sc Short-hand for any colored mana symbol
    q = q.replace(r'\sc', r'{[WUBRGP/]+}')
    # \ss Short-hand for any card symbol
    # q = q.replace(r'\ss', r'{[^}]+}')
    return q

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
