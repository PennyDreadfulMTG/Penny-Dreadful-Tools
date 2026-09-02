import html
import re
from typing import Any

import emoji
from anyascii import anyascii


def sanitize(s: str) -> str:
    """Try and corral the given string-ish thing into a unicode string. Expects input from files in arbitrary encodings and with bits of HTML in them. Useful for Lim-Dûl and similar."""
    try:
        s = s.encode('latin-1').decode('utf-8')
    except UnicodeDecodeError:
        pass
    except UnicodeEncodeError:
        pass
    return html.unescape(s)

def replace_emoji_with_text(s: str) -> str:
    """Replace emoji sequences with readable text while preserving other Unicode."""
    def replace(chars: str, data: dict[str, Any]) -> str:
        replacement = anyascii(chars)
        if not replacement or replacement == chars:
            replacement = str(data.get('en', ''))
        replacement = replacement.strip(':').replace(':', ' ').replace('_', ' ')
        return f' {replacement} ' if replacement else ''

    return re.sub(r'\s+', ' ', emoji.replace_emoji(s, replace=replace)).strip()

def unambiguous_prefixes(words: list[str]) -> list[str]:
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
