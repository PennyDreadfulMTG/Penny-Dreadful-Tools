import os
from itertools import chain
from os.path import basename

from fontTools.ttLib import TTFont
from fontTools.unicode import Unicode
from fontTools import subset

from decksite.database import db


def ad_hoc() -> None:
    print("Subsetting fonts")
    # Some symbols we use outside of deck names
    base_chars = {"①", "②", "③", "④", "⑤", "⑥", "⑦", "⑧", "⑯", "Ⓣ", "⇅", "⊕", "⸺", "▪", "🐞", "🚫", "🏆", "📰", "💻", "▾", "△", "🛈", "✅", "☐", "☑"}
    # And all the non-latin1 chars in deck names
    all_chars = base_chars | deck_name_chars()
    print("Looking for", "".join(all_chars))
    remaining_chars = all_chars.copy()
    map = {}
    for path, is_base_font in get_font_paths().items():
        font = TTFont(path, 0, allowVID=0, ignoreDecompileErrors=True, fontNumber=-1)
        found_chars = find_chars(font, all_chars)
        for c in found_chars:
            map[c] = map.get(c, []) + [path]
        needed_found_chars = found_chars & remaining_chars
        remaining_chars -= needed_found_chars
        if found_chars:
            print(f"Found {len(found_chars)} chars ({len(needed_found_chars)} needed): {found_chars} in {path} ({len(remaining_chars)} remaining)")
        if needed_found_chars and not is_base_font:
            subset_font(path, needed_found_chars)
    if remaining_chars:
        print("Could not find all chars:", remaining_chars)
    for c, paths in map.items():
        if len(paths) > 1:
            print(f"Char {c} found in multiple fonts: {paths}")
    print("""
        Done. Now you have a bunch of woff2 files in the current directory. You need to convert them to CSS-friendly base64
        strings and put them in the CSS file. You can do this with https://hellogreg.github.io/woff2base/
        If you end up with a font we've never used before you need to change all the lists of fonts in the CSS file to
        include it. Funnily enough merging the fonts in something like FontLab actually increases their size by 20KB.
    """)

def deck_name_chars() -> set[str]:
    sql = "SELECT name FROM deck WHERE name <> CONVERT(name USING latin2)"
    names = db().values(sql)
    return set("".join(names))

# This is just a giant hack because there's 3G+ of fonts we want to look in (!) so I don't want to add them to the repo.
def get_font_paths() -> dict[str, bool]:
    paths = {
        "/Users/bakert/Downloads/main-text.ttf": True,
        "/Users/bakert/Downloads/Noto_Emoji/static/NotoEmoji-Regular.ttf": False,
        "/Users/bakert/Downloads/symbola/Symbola.ttf": False,
        # I got the TTF for this from https://github.com/indigofeather/fonts/tree/master - it's not in the noto-cjk repo
        "/Users/bakert/Downloads/NotoSansCJKtc-Regular.ttf": False,
    }
    paths.update({path: False for path in find_ttfs("/Users/bakert/notofonts.github.io/")})
    return paths

def find_ttfs(path: str) -> list[str]:
    ttf_files = []
    for root, dirs, files in os.walk(path):
        for file in files:
            if file.endswith(".ttf") and "Regular" in file and "Serif" not in file:
                ttf_files.append(os.path.join(root, file))
    return ttf_files

def find_chars(font: TTFont, to_find: set[str]) -> set[str]:
    chars = chain.from_iterable([y + (Unicode[y[0]],) for y in x.cmap.items()] for x in font["cmap"].tables)
    points = [char[0] for char in chars]
    return {c for c in to_find if ord(c) in points}

def subset_font(path: str, chars: set[str]) -> str:
    text = ",".join(chars)
    new_path = f"{basename(path)}.subset.woff2"
    args = [
        path,
        f"--text={text}",
        "--no-layout-closure",
        f"--output-file={new_path}",
        "--flavor=woff2",
    ]
    subset.main(args)
    return new_path
