import base64
import os
import sys
import tempfile
import unicodedata

from fontTools import subset
from fontTools.ttLib import TTFont

from decksite.database import db

# Called as a maintenance task this will output to stdout an HTML file.
# Part of that (marked) should be copy-and-pasted into pd.css.
# Instead, you can call it from the commandline something like this:
#
# $ PYTHONPATH=. pipenv run python3 maintenance/fonts.py  >/tmp/index.html && open /tmp/index.html
#
# to see all the possibilities and maybe update the PREFER dict below.
#
# Relies on find_base_chars being kept up to date with the symbols we are using across the site.

# Prefer the simplest, lightest, but largest, version of each symbol
PREFER = {
    '☀': 'NotoEmoji',
    '☐': 'Symbola',
    '☑': 'NotoEmoji',
    '☝': 'NotoEmoji',
    '☭': 'Symbola',
    '⚡': 'NotoEmoji',
    '☺': 'Segoe UI Symbol',
    '✅': 'Segoe UI Symbol',
    '✋': 'NotoEmoji',
    '🏆': 'Segoe UI Symbol',
    '🐟': 'NotoEmoji',
    '👻': 'Segoe UI Symbol',
    '💻': 'Segoe UI Symbol',
    '🌩': 'NotoEmoji',
    '📷': 'NotoEmoji',
    '🚮': 'Symbola',
    '🛏': 'NotoEmoji',
    '🪦': 'NotoEmoji',
}

CharToFontsMapping = dict[str, list[str]]
FontInfo = list[tuple[str, str, set[str], set[str], str]]

def ad_hoc(*args: str) -> None:
    options_mode = 'options' in args
    base_only = 'base-only' in args
    # Some symbols we use outside of deck names
    base_chars = find_base_chars()
    # And all the non-latin1 chars in deck names
    from_deck_names = set() if base_only else deck_name_chars()
    all_chars = base_chars | from_deck_names
    print('\nLooking for', len(all_chars), 'chars -', len(base_chars), 'base chars, and', len(from_deck_names), 'from deck names\n', file=sys.stderr)
    remaining_chars = all_chars.copy()
    char_to_fonts: CharToFontsMapping = {}
    font_info: FontInfo = []
    for path in get_font_paths():
        name = os.path.basename(path).replace('-Regular', '').replace('.ttf', '')
        font = TTFont(path, 0, allowVID=0, ignoreDecompileErrors=True, fontNumber=-1)
        found_chars = find_chars(font, name, options_mode, all_chars)
        for c in found_chars:
            fonts_so_far = char_to_fonts.get(c, [])
            char_to_fonts[c] = fonts_so_far + [name]
        needed_found_chars = found_chars & remaining_chars
        remaining_chars -= needed_found_chars
        css = ''
        if needed_found_chars and name != 'main-text':
            woff2 = subset_font(path, needed_found_chars)
            encoded = encode(woff2)
            css = font_face(name, encoded)
        if options_mode or needed_found_chars:
            font_info.append((name, path, found_chars, needed_found_chars, css))
        if not options_mode and not remaining_chars:
            break
    if options_mode:
        print_options(char_to_fonts, font_info)
    else:
        print_css(font_info)
    print_report(font_info, remaining_chars)

def deck_name_chars() -> set[str]:
    sql = 'SELECT id, name FROM deck'
    rs = db().select(sql)
    seen = set()
    for row in rs:
        name = row['name']
        for c in name:
            if c not in seen:
                try:
                    char_name = unicodedata.name(c)
                except ValueError as e:
                    char_name = f'VALUE ERROR NO NAME {e}'  # control characters do this
                print(f"{c} {char_name} (U+{ord(c)}) from {row['id']}", file=sys.stderr)
                seen.add(c)
    return seen

# You need to get these fonts/alter these paths before running this script.
def get_font_paths() -> list[str]:
    return [
        '/Users/bakert/Downloads/main-text.ttf',
        '/Users/bakert/notofonts.github.io/megamerge/NotoSansLiving-Regular.ttf',
        '/Users/bakert/noto-cjk/Sans/Variable/TTF/NotoSansCJKjp-VF.ttf',
        '/Users/bakert/notofonts.github.io/megamerge/NotoSansHistorical-Regular.ttf',
        '/Users/bakert/notofonts.github.io/fonts/NotoSansSymbols/hinted/ttf/NotoSansSymbols-Regular.ttf',
        '/Users/bakert/notofonts.github.io/fonts/NotoSansSymbols2/hinted/ttf/NotoSansSymbols2-Regular.ttf',
        '/Users/bakert/Downloads/Noto_Emoji/static/NotoEmoji-Regular.ttf',
        '/Users/bakert/Downloads/Segoe UI Symbol.ttf',
        '/Users/bakert/Downloads/symbola/Symbola.ttf',
    ]

def find_chars(font: TTFont, name: str, options_mode: bool, to_find: set[str]) -> set[str]:
    found = set()
    for table in font['cmap'].tables:
        for glyph in to_find:
            has_preferred = PREFER.get(glyph)
            if not options_mode and has_preferred and PREFER.get(glyph) != name:
                continue
            if ord(glyph) in table.cmap.keys():
                found.add(glyph)
    return found

def subset_font(path: str, chars: set[str]) -> bytes:
    print(f'Subsetting {path}', file=sys.stderr)
    _, tmppath = tempfile.mkstemp()
    try:
        text = ','.join(chars)
        args = [
            path,
            f'--text={text}',
            '--no-layout-closure',
            f'--output-file={tmppath}',
            '--flavor=woff2',
        ]
        subset.main(args)
        with open(tmppath, 'rb') as f:
            s = f.read()
            return s
    finally:
        os.remove(tmppath)

def find_base_chars() -> set[str]:
    return set('①②③④⑤⑥⑦⑧⑯Ⓣ⇅⊕⸺▪🐞🚫🏆📰💻▾△🛈✅☐☑⚔🏅')

def encode(woff2: bytes) -> str:
    enc_file = base64.b64encode(woff2)
    return enc_file.decode('ascii')

def font_face(name: str, encoded: str) -> str:
    return f"""
        @font-face {{
            font-family: {name};
            font-style: normal;
            font-weight: normal;
            font-stretch: normal;
            src: url("data:font/woff2;charset=utf-8;base64,{encoded}") format("woff2");
        }}
    """

def print_css(font_info: FontInfo) -> None:
    symbol_font_names = [name for name, _, _, _, _ in font_info if not name == 'main-text']
    font_faces = ''.join(css for _, _, _, _, css in font_info)
    sample_chars = [(name, ''.join(f'<span title="{ord(c)}">{c}</span>' for c in sorted(used))) for name, _, _, used, _ in font_info]
    samples = ''.join(f'<p>{name} {sample}</p>' for name, sample in sample_chars)
    print('-------- 8< --------', file=sys.stderr)
    print(f"""
        <!DOCTYPE html>
        <html lang="en">
            <head>
                <meta charset="utf-8">
                <title>Penny Dreadful Font Test</title>
                <style>
                    body {{
                        font-family: "Concourse T3", var(--symbol-fonts);
                        font-size: 20px;
                    }}

                    /* BEGIN COPY AND PASTE OUTPUT FOR pd.css */

                    :root {{
                        --symbol-fonts: {', '.join(symbol_font_names)};
                    }}
                    {font_faces}

                    /* END COPY AND PASTE OUTPUT FOR pd.css */
                </style>
            </head>
            <body>
                {samples}
            </body>
        </html>
    """)
    print('-------- 8< --------', file=sys.stderr)

def print_options(char_to_fonts: CharToFontsMapping, font_info: FontInfo) -> None:
    print("""
        <!DOCTYPE html>
        <html lang="en">
            <head>
                <meta charset="utf-8">
                <title>Penny Dreadful Font Test</title>
                <style>
                body {
                    font-family: monospace;
                    font-size: 20px;
                }
    """)
    for name, path, _, _, _ in font_info:
        print(f"""
            @font-face {{
                font-family: '{name}';
                src: url('file://{path}') format('truetype');
        }}
        """)
    print("""
                </style>
            </head>
            <body>
    """)
    for c in sorted(char_to_fonts):
        if 'main-text' in char_to_fonts[c]:
            continue
        print(f'<p><span style="width: 40em; display: inline-block; text-align: right;">{unicodedata.name(c)} (U+{ord(c)})</span> ')
        for name in char_to_fonts[c]:
            print(f'<span title="{name}" style="font-family: {name}">{c}</span> ')
        print('</p>')
    print("""
            </body>
        </html>
    """)

def print_report(font_info: FontInfo, remaining_chars: set[str]) -> None:
    longest = max(len(name) for name, _, _, _, _ in font_info)
    print('Font'.rjust(longest), 'Found', 'Used', file=sys.stderr)
    for name, _, found, used, _ in font_info:
        if len(used) > 0:
            print(name.rjust(longest), str(len(found)).rjust(5), str(len(used)).rjust(4), ''.join(sorted(used)), file=sys.stderr)
    if remaining_chars:
        print('\nWARNING! DID NOT FIND THE FOLLOWING CHARS:', remaining_chars, file=sys.stderr)
    print(file=sys.stderr)


if __name__ == '__main__':
    ad_hoc(*sys.argv)
