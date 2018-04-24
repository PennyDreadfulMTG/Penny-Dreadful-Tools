import html


def sanitize(s) -> str:
    """Try and corral the given string-ish thing into a unicode string. Expects input from files in arbitrary encodings and with bits of HTML in them. Useful for Lim-Dûl and similar."""
    try:
        s = s.encode('latin-1').decode('utf-8')
    except UnicodeDecodeError:
        pass
    return html.unescape(s)
