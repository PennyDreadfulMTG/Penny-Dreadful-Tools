from typing import List
import html


def sanitize(s: str) -> str:
    """Try and corral the given string-ish thing into a unicode string. Expects input from files in arbitrary encodings and with bits of HTML in them. Useful for Lim-Dûl and similar."""
    try:
        s = s.encode('latin-1').decode('utf-8')
    except UnicodeDecodeError:
        pass
    return html.unescape(s)

def unambiguous_prefixes(words: List[str]) -> List[str]:
    prefixes = []
    for w in words:
        for i in range(1, len(w)):
            prefix = w[0:i]
            n = 0
            for w2 in words:
                if w2.startswith(prefix):
                    n += 1
            if n == 1:
                prefixes.append(prefix)
    return prefixes
