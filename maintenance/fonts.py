import base64
import html
import os
import sys
import tempfile
import unicodedata

import grapheme
from fontTools import subset
from fontTools.merge import Merger, Options
from fontTools.ttLib import TTFont
from fontTools.ttLib.scaleUpem import scale_upem
from fontTools.ttLib.woff2 import compress

from decksite.database import db
from magic import oracle
from shared.pd_exception import InvalidDataException

# The basic function of this script is to generate a woff2 font covering all the symbols we use on the site,
# including in user-submitted deck names, and output it to static/fonts/symbols.woff2. It will always output
# this file.
#
# It can also be used to inspect the symbols in question and their representation in the fonts we have available.
#
# Called with the show flag we will output an HTML file showing the symbols as currently rendered.
# $ PYTHONPATH=. pipenv run python3 maintenance/fonts.py show >/tmp/index.html && open /tmp/index.html
#
# Called with the options flag we will output an HTML file showing the symbols
# $ PYTHONPATH=. pipenv run python3 maintenance/fonts.py options >/tmp/index.html && open /tmp/index.html
# to see all the possibilities and maybe update the PREFER dict below.
#
# base-only can also be provided in the args list in order to only use the base symbols (not those from deck names).
#
# Relies on find_base_graphemes being kept up to date with the symbols we are using across the site.

# Override our default preferences where we've decided to use a specific font for a symbol.
# Prefer the simplest, lightest, but largest, version of each symbol
PREFER = {
    '☀': 'NotoEmoji',
    '☐': 'Symbola',
    '☑': 'NotoEmoji',
    '☝': 'NotoEmoji',
    '☭': 'Symbola',
    '⚡': 'NotoEmoji',
    '☺': 'SegoeUISymbol',
    '✅': 'SegoeUISymbol',
    '✋': 'NotoEmoji',
    '🏆': 'SegoeUISymbol',
    '🐟': 'NotoEmoji',
    '👻': 'SegoeUISymbol',
    '💻': 'SegoeUISymbol',
    '🌩': 'NotoEmoji',
    '📷': 'NotoEmoji',
    '🚮': 'Symbola',
    '🛏': 'NotoEmoji',
    '🪦': 'NotoEmoji',
    '🏠': 'SegoeUISymbol',
}

GraphemeToFontMapping = dict[str, list[str]]
FontInfo = list[tuple[str, str, set[str], set[str], str]]

def get_font_name(path: str) -> str:
    return os.path.basename(path).replace('-Regular', '').replace('.ttf', '').replace(' ', '')


def ad_hoc(*args: str) -> None:
    show_mode = 'show' in args
    options_mode = 'options' in args
    base_only = 'base-only' in args
    # Some symbols we use outside of deck names
    base_graphemes = find_base_graphemes()
    # Any symbols used in card names
    from_card_names, card_names = card_name_graphemes()
    # And all the symbols we use in deck names
    from_deck_names, deck_names = (set(), set()) if base_only else deck_name_graphemes()
    all_graphemes = base_graphemes | from_card_names | from_deck_names
    print('\nLooking for', len(all_graphemes), 'graphemes -', len(base_graphemes), 'base graphemes, and', len(from_card_names), 'from card names, and', len(from_deck_names), 'from deck names\n', file=sys.stderr)
    print('\nOnly from cards: ', from_card_names - base_graphemes - from_deck_names, '\n', file=sys.stderr)
    # Make a copy of all_graphemes for processing BUT exclude things like APOSTROPHE+COMBINING GRAVE ACCENT (U+39 and U+768)
    # which will overwrite main-text's apostrophe with one from a font that supports that combination. This makes all apostrophes
    # in the site look wrong for the sake of a single deck name – https://pennydreadfulmagic.com/decks/10989/
    # At some point we should find a more general solution in case it happens with other characters
    # and if at all possible stop rendering this deck name (partially) in system fonts.
    remaining_graphemes = {grapheme for grapheme in all_graphemes if "'" not in grapheme}
    graphemes_to_fonts: GraphemeToFontMapping = {}
    font_info: FontInfo = []
    metrics: dict[str, int] = {}
    used_fonts = []
    for path in get_font_paths():
        name = get_font_name(path)
        font = TTFont(path)
        if not metrics:
            metrics = get_vertical_metrics(font)
        found_graphemes = find_graphemes(font, name, options_mode, all_graphemes)
        for c in found_graphemes:
            fonts_so_far = graphemes_to_fonts.get(c, [])
            graphemes_to_fonts[c] = fonts_so_far + [name]
        needed_found_graphemes = found_graphemes & remaining_graphemes
        remaining_graphemes -= needed_found_graphemes
        css = ''
        if needed_found_graphemes and name != 'main-text':
            subsetted = subset_font(font, needed_found_graphemes)
            # main-text has 1000 upem, scale this font so that it has the same upem so that the vertical metrics work
            scale_upem(subsetted, 1000)
            # Fonts like Noto Sans Living Regular have insane bounding boxes to account for wild Indonesian characters and similar.
            # Force them to have the same vertical metrics as main-text to prevent wild line height and other issues.
            adjusted = adjust_vertical_metrics(subsetted, metrics)
            used_fonts.append((name, adjusted))
            woff2_path = os.path.join('shared_web', 'static', 'fonts', f'{name}.woff2')
            _, ttf_path = tempfile.mkstemp(suffix='.ttf')
            adjusted.save(ttf_path)
            compress(ttf_path, woff2_path)
            with open(woff2_path, 'rb') as f:
                encoded = encode(TTFont(f))
            css = font_face(name, encoded)
        if options_mode or needed_found_graphemes:
            font_info.append((name, path, found_graphemes, needed_found_graphemes, css))
        if not options_mode and not remaining_graphemes:
            break
    if show_mode:
        print_css(font_info, deck_names)
    elif options_mode:
        print_options(graphemes_to_fonts, font_info)
    print_report(font_info, remaining_graphemes)

def card_name_graphemes() -> tuple[set[str], set[str]]:
    seen, names = set(), set()
    for name in oracle.cards_by_name().keys():
        for g in grapheme.graphemes(name):
            seen.add(g)
            names.add(name)
    return seen, names

def deck_name_graphemes() -> tuple[set[str], set[str]]:
    sql = 'SELECT deck_id, normalized_name FROM deck_cache'
    rs = db().select(sql)
    seen, names = set(), set()
    for row in rs:
        name = row['normalized_name']
        for g in grapheme.graphemes(name):
            if g not in seen:
                print(f'{g} {named(g)} ({points(g)}) from {row["deck_id"]} ({name})', file=sys.stderr)
                seen.add(g)
                names.add(name)
    return seen, names

def get_font_paths() -> list[str]:
    source_path = os.path.join('shared_web', 'static', 'fonts', 'sources')
    # These are explicitly listed in order of preference, changing the order changes the behavior of this script.
    return [
        os.path.join(source_path, 'main-text.ttf'),
        os.path.join(source_path, 'NotoSansLiving-Regular.ttf'),
        # You must use the static version of these fonts not the variable versions even though it means you need more fonts.
        # These were downloaded from Google fonts, not from the noto-cjk repo which doesn't seem to have them in this format.
        os.path.join(source_path, 'NotoSansJP-Regular.ttf'),
        os.path.join(source_path, 'NotoSansSC-Regular.ttf'),
        os.path.join(source_path, 'NotoSansHistorical-Regular.ttf'),
        os.path.join(source_path, 'NotoSansSymbols-Regular.ttf'),
        os.path.join(source_path, 'NotoSansSymbols2-Regular.ttf'),
        os.path.join(source_path, 'NotoEmoji-Regular.ttf'),
        os.path.join(source_path, 'Segoe UI Symbol.ttf'),
        os.path.join(source_path, 'Symbola.ttf'),
    ]

def find_graphemes(font: TTFont, name: str, options_mode: bool, to_find: set[str]) -> set[str]:
    found = set()
    for table in font['cmap'].tables:
        for g in to_find:
            has_preferred = PREFER.get(g)
            if not options_mode and has_preferred and PREFER.get(g) != name:
                continue
            for c in g:
                if ord(c) not in table.cmap.keys():
                    break
            else:
                found.add(g)
    return found

def subset_font(font: TTFont, graphemes: set[str]) -> TTFont:
    print(f"Subsetting {font['name'].getDebugName(1)}", file=sys.stderr)
    _, tmp_in = tempfile.mkstemp()
    _, tmp_out = tempfile.mkstemp()
    font.save(tmp_in)

    try:
        text = ','.join(graphemes)
        args = [
            tmp_in,
            f'--text={text}',
            f'--output-file={tmp_out}',
            '--flavor=woff2',
        ]

        subset.main(args)
        subsetted_font = TTFont(tmp_out)
        return subsetted_font
    finally:
        os.remove(tmp_in)
        os.remove(tmp_out)


def find_base_graphemes() -> set[str]:
    return set('①②③④⑤⑥⑦⑧⑯Ⓣ⇅⊕⸺▪🐞🚫🏆📰💻▾△🛈✅☐☑⚔🏅☰🏠☼🌙')

def encode(font: TTFont) -> str:
    _, tmp_in = tempfile.mkstemp()
    try:
        font.save(tmp_in)
        with open(tmp_in, 'rb') as f:
            s = f.read()
        enc_file = base64.b64encode(s)
        return enc_file.decode('ascii')
    finally:
        os.remove(tmp_in)

def get_vertical_metrics(font: TTFont) -> dict[str, int]:
    hhea = font['hhea']
    os2 = font['OS/2']
    # The keys are the names that FontForge uses in Element, Font Info, OS/2, Metrics.
    return {
        'Win Ascent': os2.usWinAscent,
        'Win Descent': os2.usWinDescent,
        'Typo Ascent': os2.sTypoAscender,
        'Typo Descent': os2.sTypoDescender,
        'Typo Line Gap': os2.sTypoLineGap,
        'HHead Ascent': hhea.ascent,
        'HHead Descent': hhea.descent,
        'HHead Line Gap': hhea.lineGap,
    }

def adjust_vertical_metrics(font: TTFont, metrics: dict[str, int]) -> TTFont:
    print(f"Adjusting vertical metrics of {font['name'].getDebugName(1)}", file=sys.stderr)
    _, tmp_out = tempfile.mkstemp()
    try:
        os2 = font['OS/2']
        os2.usWinAscent = metrics['Win Ascent']
        os2.usWinDescent = metrics['Win Descent']
        os2.sTypoAscender = metrics['Win Ascent']  # This is theoretically wrong, but it makes everything work, instead of making things sit too high in the bounding box, so here we are.
        os2.sTypoDescender = metrics['Typo Descent']
        os2.sTypoLineGap = metrics['Typo Line Gap']
        hhea = font['hhea']
        hhea.ascent = metrics['HHead Ascent']
        hhea.descent = metrics['HHead Descent']
        hhea.lineGap = metrics['HHead Line Gap']
        font.save(tmp_out)
        return TTFont(tmp_out)
    finally:
        os.remove(tmp_out)

def merge_fonts(fonts: list[TTFont]) -> TTFont:
    temp_files = []
    for font in fonts:
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.ttf')
        font.save(temp_file.name)
        temp_files.append(temp_file.name)

    try:
        # Stole these options from google's noto megamerge
        merger = Merger(options=Options(drop_tables=['vmtx', 'vhea', 'MATH']))
        merged_font = merger.merge(temp_files)
    finally:
        for path in temp_files:
            try:
                os.remove(path)
            except OSError:
                pass

    return merged_font

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

def print_css(font_info: FontInfo, deck_names: set[str]) -> None:
    css = '\n'.join(css for _, _, _, _, css in font_info if css)
    sample_graphemes = [(name, ''.join(f'<span title="{points(grapheme)}">{html.escape(grapheme)}</span>' for grapheme in sorted(used))) for name, _, _, used, _ in font_info]
    samples = ''.join(f'<p>{html.escape(name)} {sample}</p>' for name, sample in sample_graphemes)
    deck_name_samples = '\n'.join(f'<p>{html.escape(name)}</p>' for name in deck_names)

    font_names = [get_font_name(path) for path in get_font_paths()]
    font_stack = ', '.join(font_names + ['fantasy'])

    print(f"""
        <!DOCTYPE html>
        <html lang="en">
            <head>
                <meta charset="utf-8">
                <title>Penny Dreadful Font Test</title>
                <style>
                    * {{
                        font-family: {font_stack}; /* fantasy as base font so we can use js to detect misses, see below. */
                        font-size: 20px;
                    }}

                    @font-face {{
                        font-family: main-text;
                        src: url('file://{os.path.abspath(get_font_paths()[0])}');
                    }}

                    {css}
                </style>
            </head>
            <body>
                <div id="content">
                    {samples}
                    {deck_name_samples}
                </div>
                <script>
                     function detectLocalFontUsage() {{
                        const elements = document.querySelectorAll('#content *');
                        let missing = false;
                        elements.forEach(element => {{
                            const originalText = element.innerText;
                            const testElement = document.createElement('span');
                            testElement.className = 'test-element';
                            testElement.style.fontFamily = 'fantasy';
                            testElement.innerText = originalText;
                            document.body.appendChild(testElement);

                            const originalWidth = element.offsetWidth;
                            const originalHeight = element.offsetHeight;
                            const testWidth = testElement.offsetWidth;
                            const testHeight = testElement.offsetHeight;

                            if (originalWidth === testWidth && originalHeight === testHeight) {{
                                console.warn('Local font detected in element:', element);
                                missing = true;
                            }}

                            document.body.removeChild(testElement);
                        }});
                        if (missing) {{
                            alert('Local font detected, check console output');
                        }}
                    }}

                    window.onload = detectLocalFontUsage;
                </script>
            </body>
        </html>
    """)

def print_options(grapheme_to_fonts: GraphemeToFontMapping, font_info: FontInfo) -> None:
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
                src: url('file://{os.path.abspath(path)}') format('truetype');
            }}
        """)
    print("""
                </style>
            </head>
            <body>
    """)
    for g in sorted(grapheme_to_fonts):
        if 'main-text' in grapheme_to_fonts[g]:
            continue
        print(f'<p><span style="width: 40em; display: inline-block; text-align: right;">{html.escape(named(g))} ({html.escape(points(g))})</span> ')
        for name in grapheme_to_fonts[g]:
            print(f'<span title="{html.escape(name)}" style="font-family: {html.escape(name)}">{html.escape(g)}</span>')
        print('</p>')
    print("""
            </body>
        </html>
    """)

def print_report(font_info: FontInfo, remaining_graphemes: set[str]) -> None:
    longest = max(len(name) for name, _, _, _, _ in font_info)
    print('Font'.rjust(longest), 'Found', 'Used', file=sys.stderr)
    for name, _, found, used, _ in font_info:
        if len(used) > 0:
            print(name.rjust(longest), str(len(found)).rjust(5), str(len(used)).rjust(4), ''.join(sorted(used)), file=sys.stderr)
    if remaining_graphemes:
        print('\nWARNING! DID NOT FIND THE FOLLOWING GRAPHEMES:', remaining_graphemes, file=sys.stderr)
        raise InvalidDataException('Missing graphemes, requires human intervention to add a new font probably')
    print(file=sys.stderr)

def named(grapheme: str) -> str:
    try:
        return '+'.join(unicodedata.name(c) for c in grapheme)
    except ValueError as e:
        return f'VALUE ERROR NO NAME {e} ({grapheme})'  # control characters do this

def points(grapheme: str) -> str:
    return ' and '.join(f'U+{ord(c)}' for c in grapheme)


if __name__ == '__main__':
    ad_hoc(*sys.argv)
