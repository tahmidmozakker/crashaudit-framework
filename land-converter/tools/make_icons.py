"""Generate the PWA icon set for the land-measurement app.

No third-party imaging library is available in this environment, so the
PNGs are written straight from an RGBA pixel buffer with zlib.

    python3 tools/make_icons.py
"""

import os
import struct
import zlib

OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "icons")

GREEN_DARK = (13, 92, 63, 255)
GREEN = (22, 132, 88, 255)
SAND = (244, 232, 205, 255)
GOLD = (226, 168, 61, 255)
CLEAR = (0, 0, 0, 0)


def blank(size, colour=CLEAR):
    return [[colour for _ in range(size)] for _ in range(size)]


def fill_rect(px, x0, y0, x1, y1, colour):
    size = len(px)
    for y in range(max(0, int(y0)), min(size, int(y1))):
        row = px[y]
        for x in range(max(0, int(x0)), min(size, int(x1))):
            row[x] = colour


def fill_rounded(px, x0, y0, x1, y1, radius, colour):
    """Filled rectangle with rounded corners, anti-aliased on the arcs."""
    size = len(px)
    for y in range(max(0, int(y0)), min(size, int(y1))):
        for x in range(max(0, int(x0)), min(size, int(x1))):
            cx = min(max(x + 0.5, x0 + radius), x1 - radius)
            cy = min(max(y + 0.5, y0 + radius), y1 - radius)
            dist = ((x + 0.5 - cx) ** 2 + (y + 0.5 - cy) ** 2) ** 0.5
            if dist <= radius - 0.5:
                px[y][x] = colour
            elif dist < radius + 0.5:
                a = radius + 0.5 - dist
                px[y][x] = blend(px[y][x], colour, a)


def blend(under, over, alpha):
    a = max(0.0, min(1.0, alpha)) * (over[3] / 255.0)
    if a <= 0:
        return under
    ua = under[3] / 255.0
    out_a = a + ua * (1 - a)
    if out_a <= 0:
        return CLEAR
    return tuple(
        [int(round((over[i] * a + under[i] * ua * (1 - a)) / out_a)) for i in range(3)]
        + [int(round(out_a * 255))]
    )


def draw_plot(px, box, colour_field, colour_line):
    """A surveyed land plot: a field divided by boundary lines, seen in plan."""
    x0, y0, x1, y1 = box
    w = x1 - x0
    h = y1 - y0
    fill_rounded(px, x0, y0, x1, y1, w * 0.06, colour_field)
    line = max(2.0, w * 0.055)
    # vertical division at 40%, horizontal division at 55%
    vx = x0 + w * 0.40
    hy = y0 + h * 0.55
    fill_rect(px, vx - line / 2, y0, vx + line / 2, hy, colour_line)
    fill_rect(px, x0, hy - line / 2, x1, hy + line / 2, colour_line)
    # measuring ticks along the bottom edge (a chain / scale)
    tick_h = h * 0.10
    for i in range(1, 6):
        tx = x0 + w * i / 6.0
        fill_rect(px, tx - line * 0.35, y1 - tick_h, tx + line * 0.35, y1, colour_line)


def render(size, maskable=False):
    px = blank(size)
    if maskable:
        # Safe zone is the middle 80%; bleed the background to every edge.
        fill_rect(px, 0, 0, size, size, GREEN_DARK)
        pad = size * 0.26
    else:
        fill_rounded(px, 0, 0, size, size, size * 0.22, GREEN_DARK)
        pad = size * 0.20
    fill_rounded(px, pad * 0.55, pad * 0.55, size - pad * 0.55, size - pad * 0.55,
                 size * 0.10, GREEN)
    draw_plot(px, (pad, pad, size - pad, size - pad), SAND, GREEN_DARK)
    # corner marker: the survey peg
    r = size * 0.055
    cx, cy = size - pad * 0.98, pad * 0.98
    fill_rounded(px, cx - r, cy - r, cx + r, cy + r, r, GOLD)
    return px


def write_png(path, px):
    size = len(px)
    raw = bytearray()
    for row in px:
        raw.append(0)
        for r, g, b, a in row:
            raw += bytes((r, g, b, a))
    comp = zlib.compress(bytes(raw), 9)

    def chunk(tag, data):
        out = struct.pack(">I", len(data)) + tag + data
        return out + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0))
    png += chunk(b"IDAT", comp)
    png += chunk(b"IEND", b"")
    with open(path, "wb") as fh:
        fh.write(png)
    print("wrote %s (%d bytes)" % (path, len(png)))


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    for size in (192, 512):
        write_png(os.path.join(OUT_DIR, "icon-%d.png" % size), render(size))
    write_png(os.path.join(OUT_DIR, "icon-maskable-512.png"), render(512, maskable=True))
    write_png(os.path.join(OUT_DIR, "apple-touch-icon.png"), render(180))
    write_png(os.path.join(OUT_DIR, "favicon-64.png"), render(64))


if __name__ == "__main__":
    main()
