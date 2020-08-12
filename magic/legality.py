from typing import Dict, List, Set

from magic import oracle, rotation
from magic.database import db
from magic.models import Card
from shared.container import Container

FORMATS: Set[str] = set()

def legal_in_format(d: Container, f: str) -> bool:
    return f in legal_formats(d, set([f]))

def legal_formats(d: Container, formats_to_check: Set[str] = None, errors: Dict[str, Dict[str, Set[str]]] = None) -> Set[str]:
    init()
    if formats_to_check is None:
        formats_to_check = FORMATS
    if errors is None:
        errors = {}
    formats_to_discard = set()

    # When the formatting of the deck cannot be read, the decklist reader will return an empty deck.
    # When the text box is empty, a different error will pop up.
    # So if the text box is not empty, but no cards are read, it must be a formatting issue.
    if (sum(e['n'] for e in d.maindeck) + sum(e['n'] for e in d.sideboard)) <= 0:
        for f in formats_to_check:
            add_error(errors, f, 'Legality_General', "I'm afraid I don't recognize that decklist format. Try exporting from MTGO.")
            formats_to_discard.add(f)
        # I returned here because I want to skip all other checks.
        return formats_to_check - formats_to_discard

    if sum(e['n'] for e in d.maindeck) < 60:
        for f in formats_to_check:
            add_error(errors, f, 'Legality_General', 'You have less than 60 cards.')
            formats_to_discard.add(f)
    if sum(e['n'] for e in d.sideboard) > 15:
        for f in formats_to_check:
            add_error(errors, f, 'Legality_General', 'You have more than 15 cards in your sideboard.')
            formats_to_discard.add(f)
    if (sum(e['n'] for e in d.maindeck) + sum(e['n'] for e in d.sideboard)) != 100:
        add_error(errors, 'Commander', 'General', 'Incorrect deck size.')
        formats_to_discard.add('Commander')
    card_count: Dict[str, int] = {}
    for c in d.all_cards():
        if not c.type_line.startswith('Basic ') and not 'A deck can have any number of cards named' in c.oracle_text:
            card_count[c.name] = card_count.get(c.name, 0) + 1
    if card_count.values() and max(card_count.values()) > 4:
        affected_cards = []
        for k, v in card_count.items():
            max_allowed = 7 if k == 'Seven Dwarves' else 4
            if v > max_allowed:
                affected_cards.append(k)
        if affected_cards:
            for f in formats_to_check:
                for card in affected_cards:
                    add_error(errors, f, 'Legality_Too_Many', card)
                formats_to_discard.add(f)
    elif card_count.values() and max(card_count.values()) > 1:
        add_error(errors, 'Commander', 'Legality_General', 'Deck is not Singleton.')
        formats_to_discard.add('Commander')
    for c in set(d.all_cards()):
        for f in formats_to_check:
            if f not in c.legalities.keys() or c.legalities[f] == 'Banned':
                illegal = 'Banned' if c.legalities.get(f, None) == 'Banned' else 'Not_Legal'
                add_error(errors, f, 'Legality_' + illegal, c.name)
                formats_to_discard.add(f)
            elif c.legalities[f] == 'Restricted':
                if card_count[c.name] > 1:
                    formats_to_discard.add(f)
                    add_error(errors, f, 'Legality_Restricted', c.name)

    return formats_to_check - formats_to_discard

def add_error(errors: Dict[str, Dict[str, Set[str]]], fmt: str, error_type: str, card: str) -> None:
    if fmt not in errors:
        errors[fmt] = dict()
    if error_type not in errors[fmt]:
        errors[fmt][error_type] = set()
    errors[fmt][error_type].add(card)

def cards_legal_in_format(cardlist: List[Card], f: str) -> List[Card]:
    init()
    results = []
    for c in cardlist:
        if f in c.legalities.keys() and c.legalities[f] != 'Banned':
            results.append(c)
    return results

def order_score(fmt: str) -> int:
    if fmt == 'Penny Dreadful':
        return 1
    if 'Penny Dreadful' in fmt:
        return 1000 - rotation.SEASONS.index(fmt.replace('Penny Dreadful ', ''))
    if fmt == 'Vintage':
        return 10000
    if fmt == 'Legacy':
        return 100000
    if fmt == 'Modern':
        return 1000000
    if fmt == 'Standard':
        return 10000000
    if 'Block' in fmt:
        return 100000000
    if fmt == 'Commander':
        return 1000000000
    return 10000000000

def init() -> None:
    if FORMATS:
        return
    print('Updating Legalities…')
    oracle.legal_cards()

    FORMATS.clear()
    for v in db().values('SELECT name FROM format'):
        FORMATS.add(v)
