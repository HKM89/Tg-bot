"""Draw a timestamp / location overlay in the top-right corner of a photo.

The layout is calibrated against the sample photo (1280x960):
    white text, right aligned, ~38px font, ~44.6px line pitch,
    ~42px right margin, first cap-line ~48px from the top.
All values are expressed relative to the shorter side of the image so
the overlay looks the same on any resolution / orientation.
"""
from __future__ import annotations

import io
import os
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

FONT_PATH = os.environ.get(
    "STAMP_FONT", os.path.join(os.path.dirname(__file__), "fonts", "Inter-Regular.otf")
)

# Ratios relative to the short side (960 in the sample)
FONT_RATIO = 38 / 960
LINE_RATIO = 44.6 / 960
RIGHT_RATIO = 42 / 960
TOP_RATIO = 39 / 960


def _font(size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(FONT_PATH, size)
    except OSError:
        return ImageFont.load_default(size)


def stamp_image(data: bytes, lines: list[str], shadow: bool = True) -> bytes:
    img = Image.open(io.BytesIO(data))
    img = ImageOps.exif_transpose(img).convert("RGB")
    w, h = img.size
    short = min(w, h)

    size = max(12, round(short * FONT_RATIO))
    font = _font(size)
    pitch = short * LINE_RATIO
    right = w - short * RIGHT_RATIO
    top = short * TOP_RATIO

    # Shrink the font if the longest line would not fit
    max_w = w - 2 * short * RIGHT_RATIO
    longest = max((font.getlength(t) for t in lines), default=0)
    if longest > max_w:
        k = max_w / longest
        size = max(10, int(size * k))
        font = _font(size)
        pitch *= k

    positions = []
    for i, text in enumerate(lines):
        x = right - font.getlength(text)
        y = top + i * pitch
        positions.append((x, y, text))

    if shadow:
        layer = Image.new("L", img.size, 0)
        d = ImageDraw.Draw(layer)
        off = max(1, size // 20)
        for x, y, text in positions:
            d.text((x + off, y + off), text, font=font, fill=150)
        layer = layer.filter(ImageFilter.GaussianBlur(max(1, size // 14)))
        img.paste((0, 0, 0), mask=layer)

    draw = ImageDraw.Draw(img)
    for x, y, text in positions:
        draw.text((x, y), text, font=font, fill=(255, 255, 255))

    out = io.BytesIO()
    img.save(out, format="JPEG", quality=95)
    return out.getvalue()
