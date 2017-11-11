import textwrap

import markdown

from shared.pd_exception import InvalidArgumentException

# Canonical tournament and other rules information for PD that needs to be shared to multiple sources.
# Written in Markdown to make emitting in HTML or text reasonable.

SHORT = 'short'
LONG = 'long'

HTML = 'html'
TEXT = 'text'

def bugs(version=LONG, fmt=TEXT):
    s = """
            We allow the playing of cards with known bugs in Penny Dreadful with specific conditions.

    """
    if version == SHORT:
        s += """
            See <https://pennydreadfulmagic.com/tournaments/> for more information.

        """
    elif version == LONG:
        s += """
            * Cards with game-breaking bugs should not be played.

            * Cards with disadvantageous bugs can be played and no extra rules apply. The opposing player is under no obligation to treat the card as if it worked properly.

            * Cards with advantageous bugs can be played but accruing advantage intentionally will result in disqualification.

            * Accruing advantage any other way with a card with an advantageous bug is a game loss for the owner of the bugged card.

            **Example of Game Loss**: Playing Living Lore with two cards in graveyard and opponent removes one at instant speed with a card from their hand forcing the Living Lore player to imprint a split card.

            **Second example of Game Loss**: Playing Profane Command using the mode that targets an opponent. Opponent plays Gilded Light in response.

            **Example of Disqualification**: Playing Living Lore and intentionally choosing a split card from a stocked graveyard to get an oversized Living Lore.

            In the case where a bugged interaction only becomes known to a player during a competitive match, at the TO's discretion, a game loss or match loss may be imposed rather than a disqualification.

            The game loss should be enacted by the bugged cards controller conceding the game.

            Any confusion should be discussed with the Tournament Organizer before conceding the game or ending the match, on the bugged card player's clock.

            * When a new bug is encountered for the first time (does not appear at <https://pennydreadfulmagic.com/bugs/>) during a competitive match both players may agree to play on.

            * If either player does not agree the player with the bugged cards must swap out the bugged cards (only) from their decklist, restart the match, players concede games in the correct order until the record matches the record before the bugged game. Sideboarding then takes place if it was not game 1 and the rest of the match plays out.

            For all these matters the Tournament Organizer has the flexibility to rule as they see fit and their decision is final.

        """
    else:
        raise InvalidArgumentException('Unknown version: {version}'.format(version=version))
    return prep(fmt, s)

def prep(fmt, s):
    if fmt == TEXT:
        s = s.replace('\n\n', '\n')
    elif fmt == HTML:
        print(s)
        s = textwrap.dedent(s).strip()
        print(s)
        s = markdown.markdown(s)
        print(s)
    else:
        raise InvalidArgumentException('Unrecognized format {fmt}'.format(fmt=fmt))
    return s
