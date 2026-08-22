import base64
import io
import re
from pathlib import Path

from fontTools.ttLib import TTFont


def test_embedded_font_glyph_bounding_boxes_are_correct() -> None:
    css = Path('shared_web/static/css/pd.css').read_text()
    encoded_fonts = re.findall(r'base64,([^"\)]+)', css)

    assert len(encoded_fonts) == 4
    for encoded_font in encoded_fonts:
        font = TTFont(io.BytesIO(base64.b64decode(encoded_font)))
        glyf = font['glyf']
        for glyph_name in font.getGlyphOrder():
            glyph = glyf[glyph_name]
            if glyph.numberOfContours == 0:
                continue
            bounds = tuple(getattr(glyph, key) for key in ('xMin', 'yMin', 'xMax', 'yMax'))
            glyph.recalcBounds(glyf)
            recalculated_bounds = tuple(getattr(glyph, key) for key in ('xMin', 'yMin', 'xMax', 'yMax'))
            assert bounds == recalculated_bounds, glyph_name
