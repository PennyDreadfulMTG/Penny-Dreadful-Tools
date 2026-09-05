import html
import re
import unicodedata
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
    """Remove pictographic emoji from text, with names as an emoji-only fallback.

    Unicode characters with text presentation, such as © and ♥, are preserved.
    """
    found_emoji = False

    def remove(chars: str, data: dict[str, Any]) -> str:
        nonlocal found_emoji
        if data.get('status') == emoji.STATUS['unqualified']:
            return chars
        found_emoji = True
        return ' '

    without_emoji = emoji.replace_emoji(s, replace=remove)
    if not found_emoji:
        return s

    without_emoji = re.sub(r'\s+', ' ', without_emoji).strip()
    if any(c.isalnum() for c in without_emoji):
        return without_emoji

    def replace(chars: str, data: dict[str, Any]) -> str:
        if data.get('status') == emoji.STATUS['unqualified']:
            return chars
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

def merge_slashes(name: str) -> str:
    """Collapse each run of slashes, and the whitespace around it, to a bare '/'.

    The proxies in front of us merge repeated slashes, so `/cards/Bedeck // Bedazzle/` arrives as
    `Bedeck / Bedazzle`. Both spellings, and the stored `Bedeck // Bedazzle`, share this form.
    """
    return re.sub(r'\s*/+\s*', '/', name)

def fold_accents(s: str) -> str:
    """Drop combining marks, so `Seance` and `Séance` compare equal as they do under utf8mb4_unicode_ci."""
    return ''.join(c for c in unicodedata.normalize('NFKD', s) if not unicodedata.combining(c))
