#!/usr/bin/env python3
"""VELMARA — a travel poster for a place that isn't there.

Pure standard library. Draws a 768x1024 PNG poster of Velmara, the
floating lantern isles, and writes it to /output/entry.png.
Deterministic: same bytes on every run.
"""

import os
import struct
import zlib

W, H = 768, 1024
OUT = "/output/entry.png"

# ---------------------------------------------------------------- font
# Hand-drawn 5x7 bitmap font. '1' = ink, '0' = empty.
FONT = {
    "A": ("01110", "10001", "10001", "11111", "10001", "10001", "10001"),
    "B": ("11110", "10001", "10001", "11110", "10001", "10001", "11110"),
    "C": ("01110", "10001", "10000", "10000", "10000", "10001", "01110"),
    "D": ("11110", "10001", "10001", "10001", "10001", "10001", "11110"),
    "E": ("11111", "10000", "10000", "11110", "10000", "10000", "11111"),
    "F": ("11111", "10000", "10000", "11110", "10000", "10000", "10000"),
    "G": ("01110", "10001", "10000", "10111", "10001", "10001", "01111"),
    "H": ("10001", "10001", "10001", "11111", "10001", "10001", "10001"),
    "I": ("01110", "00100", "00100", "00100", "00100", "00100", "01110"),
    "J": ("00111", "00010", "00010", "00010", "00010", "10010", "01100"),
    "K": ("10001", "10010", "10100", "11000", "10100", "10010", "10001"),
    "L": ("10000", "10000", "10000", "10000", "10000", "10000", "11111"),
    "M": ("10001", "11011", "10101", "10101", "10001", "10001", "10001"),
    "N": ("10001", "11001", "10101", "10011", "10001", "10001", "10001"),
    "O": ("01110", "10001", "10001", "10001", "10001", "10001", "01110"),
    "P": ("11110", "10001", "10001", "11110", "10000", "10000", "10000"),
    "Q": ("01110", "10001", "10001", "10001", "10101", "10010", "01101"),
    "R": ("11110", "10001", "10001", "11110", "10100", "10010", "10001"),
    "S": ("01111", "10000", "10000", "01110", "00001", "00001", "11110"),
    "T": ("11111", "00100", "00100", "00100", "00100", "00100", "00100"),
    "U": ("10001", "10001", "10001", "10001", "10001", "10001", "01110"),
    "V": ("10001", "10001", "10001", "10001", "10001", "01010", "00100"),
    "W": ("10001", "10001", "10001", "10101", "10101", "11011", "10001"),
    "X": ("10001", "10001", "01010", "00100", "01010", "10001", "10001"),
    "Y": ("10001", "10001", "01010", "00100", "00100", "00100", "00100"),
    "Z": ("11111", "00001", "00010", "00100", "01000", "10000", "11111"),
    " ": ("00000", "00000", "00000", "00000", "00000", "00000", "00000"),
    "-": ("00000", "00000", "00000", "01110", "00000", "00000", "00000"),
    ".": ("00000", "00000", "00000", "00000", "00000", "01100", "01100"),
}


def text_width(text, scale):
    """Pixel width of text at the given scale (1px gap between glyphs)."""
    return len(text) * 6 * scale - scale


def draw_text(px, text, x, y, scale, color):
    """Draw text with its top-left corner at (x, y)."""
    for ci, ch in enumerate(text):
        glyph = FONT.get(ch.upper(), FONT[" "])
        ox = x + ci * 6 * scale
        for gy, row in enumerate(glyph):
            for gx, bit in enumerate(row):
                if bit == "1":
                    fill_rect(px, ox + gx * scale, y + gy * scale,
                              scale, scale, color)


# ---------------------------------------------------------------- canvas
def new_canvas():
    return bytearray(W * H * 3)


def set_px(px, x, y, color):
    if 0 <= x < W and 0 <= y < H:
        i = (y * W + x) * 3
        px[i], px[i + 1], px[i + 2] = color


def fill_rect(px, x, y, w, h, color):
    x0, y0 = max(0, x), max(0, y)
    x1, y1 = min(W, x + w), min(H, y + h)
    if x1 <= x0 or y1 <= y0:
        return
    r, g, b = color
    for yy in range(y0, y1):
        base = (yy * W + x0) * 3
        for xx in range(x0, x1):
            i = base + (xx - x0) * 3
            px[i], px[i + 1], px[i + 2] = r, g, b


def blend(px, x, y, color, alpha):
    """Blend color over the pixel at (x, y); alpha 0..1."""
    if 0 <= x < W and 0 <= y < H:
        i = (y * W + x) * 3
        px[i] = int(px[i] * (1 - alpha) + color[0] * alpha)
        px[i + 1] = int(px[i + 1] * (1 - alpha) + color[1] * alpha)
        px[i + 2] = int(px[i + 2] * (1 - alpha) + color[2] * alpha)


def disc(px, cx, cy, r, color, alpha=1.0):
    for yy in range(cy - r, cy + r + 1):
        for xx in range(cx - r, cx + r + 1):
            dx, dy = xx - cx, yy - cy
            if dx * dx + dy * dy <= r * r:
                if alpha >= 1.0:
                    set_px(px, xx, yy, color)
                else:
                    blend(px, xx, yy, color, alpha)


def hline(px, x0, x1, y, color, alpha=1.0):
    for xx in range(x0, x1 + 1):
        if alpha >= 1.0:
            set_px(px, xx, y, color)
        else:
            blend(px, xx, y, color, alpha)


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


# ---------------------------------------------------------------- PNG
def _chunk(kind, data):
    out = struct.pack(">I", len(data)) + kind + data
    out += struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    return out


def write_png(px, path):
    raw = bytearray()
    for y in range(H):
        raw.append(0)  # filter: none
        raw += px[y * W * 3:(y + 1) * W * 3]
    ihdr = struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0)
    png = b"\x89PNG\r\n\x1a\n"
    png += _chunk(b"IHDR", ihdr)
    png += _chunk(b"IDAT", zlib.compress(bytes(raw), 9))
    png += _chunk(b"IEND", b"")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(png)
    return len(png)

# ---------------------------------------------------------------- scene
# Palette (5 colours, purposeful): indigo dusk, violet, sunset amber,
# lantern gold, deep teal sea. Cream type.
INDIGO = (26, 30, 78)
VIOLET = (96, 56, 122)
AMBER = (238, 140, 72)
GOLD = (255, 196, 96)
CREAM = (255, 238, 204)
TEAL = (14, 52, 88)
DEEP = (10, 26, 54)
ROCK = (30, 24, 56)
PINE = (18, 40, 44)

HORIZON = 660  # where sea meets sky


def vgrad(px, y0, y1, top, bottom):
    for y in range(y0, y1):
        t = (y - y0) / max(1, y1 - y0 - 1)
        fill_rect(px, 0, y, W, 1, lerp(top, bottom, t))


def lantern(px, cx, cy, r=5):
    """A glowing paper lantern: halo, shell, warm core."""
    disc(px, cx, cy, r + 7, (255, 150, 60), 0.18)
    disc(px, cx, cy, r + 3, (255, 170, 80), 0.35)
    disc(px, cx, cy, r, GOLD)
    set_px(px, cx, cy - 1, (255, 244, 210))
    set_px(px, cx, cy, (255, 244, 210))


def island(px, cx, top_y, half_w, depth, big):
    """A floating rock isle: flat green top, tapering rocky underside,
    a pine silhouette and hanging lanterns. Waterfalls drip below."""
    # rocky underside: tapered wedge
    for d in range(depth):
        t = d / depth
        w = int(half_w * (1 - t * 0.92))
        y = top_y + d
        fill_rect(px, cx - w, y, w * 2, 1, ROCK)
    # flat top with warm rim light
    fill_rect(px, cx - half_w, top_y - 6, half_w * 2, 7, PINE)
    hline(px, cx - half_w, cx + half_w, top_y - 6, GOLD, 0.9)
    # pine silhouette on top (a second pine + a lantern pavilion on big isles)
    for k in range(3):
        pw = 14 - k * 4
        py = top_y - 6 - 12 - k * 10
        fill_rect(px, cx - pw // 2, py, pw, 10, PINE)
    fill_rect(px, cx - 2, top_y - 14, 4, 9, PINE)
    if big:
        for ox in (-52, 48):
            for k in range(2):
                pw = 12 - k * 4
                py = top_y - 6 - 10 - k * 9
                fill_rect(px, cx + ox - pw // 2, py, pw, 9, PINE)
        # tiny pavilion with a lit roof, centre of the isle
        for r in range(10):
            fill_rect(px, cx - 18 + r, top_y - 40 + r, 36 - 2 * r, 2, GOLD)
        fill_rect(px, cx - 13, top_y - 30, 26, 24, ROCK)
        lantern(px, cx, top_y - 18, 4)
    # hanging lanterns along the rim
    n = 5 if big else 3
    for i in range(n):
        lx = cx - half_w + int((i + 0.5) * (2 * half_w) / n)
        ly = top_y + 14 + (i % 2) * 10
        hline(px, lx, lx, top_y + 2, GOLD, 0.7)  # string
        for yy in range(top_y + 2, ly):
            set_px(px, lx, yy, GOLD)
        lantern(px, lx, ly, 5 if big else 4)
    # waterfalls dripping from the underside into the sea
    for fx in (-half_w // 2, half_w // 3):
        x = cx + fx
        for yy in range(top_y + depth - 2, HORIZON + 26):
            if (yy * 5 + x) % 9:
                blend(px, x, yy, (170, 220, 240), 0.45)
                blend(px, x + 1, yy, (170, 220, 240), 0.25)


def bird(px, x, y, s):
    for dx in range(s):
        set_px(px, x - dx, y + dx // 2, (20, 18, 44))
        set_px(px, x + dx, y + dx // 2, (20, 18, 44))


def draw():
    px = new_canvas()

    # --- sky: indigo dusk melting into sunset amber at the horizon
    vgrad(px, 0, 420, INDIGO, VIOLET)
    vgrad(px, 420, HORIZON, VIOLET, AMBER)

    # --- low sun, big and warm, clear of the isles, just above the horizon
    disc(px, 630, 505, 110, (255, 170, 90), 0.16)
    disc(px, 630, 505, 82, (255, 190, 110), 0.28)
    disc(px, 630, 505, 58, (255, 216, 138))
    disc(px, 630, 505, 42, (255, 236, 190))

    # --- thin dusk clouds catching the light (below the tagline)
    for (cy, cw, cx0) in ((250, 180, 90), (295, 240, 430),
                          (335, 150, 200)):
        for dy in range(4):
            hline(px, cx0, cx0 + cw, cy + dy, (255, 170, 120), 0.10)

    # --- the name, large, in the upper third, cream with indigo shadow
    name = "VELMARA"
    scale = 12
    nx = (W - text_width(name, scale)) // 2
    ny = 84
    draw_text(px, name, nx + 6, ny + 7, scale, (16, 14, 52))
    draw_text(px, name, nx, ny, scale, CREAM)
    # thin gold rule under the name
    fill_rect(px, nx + 20, ny + 7 * scale + 18, text_width(name, scale) - 40,
              4, GOLD)

    # --- tagline, small, beneath the rule
    tag = "THE FLOATING LANTERN ISLES"
    tscale = 3
    tx = (W - text_width(tag, tscale)) // 2
    draw_text(px, tag, tx + 2, ny + 7 * scale + 34, tscale, (16, 14, 52))
    draw_text(px, tag, tx, ny + 7 * scale + 32, tscale, GOLD)

    # --- floating lantern isles: one great isle, two small companions
    island(px, 384, 470, 190, 96, big=True)
    island(px, 150, 380, 78, 58, big=False)
    island(px, 620, 400, 66, 50, big=False)

    # --- birds crossing the dusk
    bird(px, 250, 300, 9)
    bird(px, 300, 268, 7)
    bird(px, 500, 250, 8)

    # --- sea: deep teal, darker toward the bottom
    vgrad(px, HORIZON, H, TEAL, DEEP)
    # sun path: shimmering gold streaks on the water, centred under the sun
    for i, (sy, sw) in enumerate(((690, 220), (730, 280), (775, 340),
                                  (825, 400), (880, 460), (940, 520))):
        x0 = 630 - sw // 2
        for xx in range(x0, x0 + sw):
            if (xx * 31 + sy * 17) % 7:
                blend(px, xx, sy, GOLD, 0.30 - i * 0.02)
    # lantern reflections: faint gold columns under each isle
    for cx in (150, 384, 620):
        for yy in range(HORIZON + 8, HORIZON + 120):
            if (yy * 3 + cx) % 4 == 0:
                blend(px, cx, yy, GOLD, 0.16)
    # faint moonlit ripple on the quiet left water
    for (sy, sw, x0) in ((760, 180, 90), (860, 240, 130), (950, 160, 70)):
        for xx in range(x0, x0 + sw):
            if (xx * 17 + sy * 11) % 5:
                blend(px, xx, sy, (120, 180, 220), 0.14)

    # --- foreground silhouette hills, framing the bottom corners
    for x in range(0, 210):
        hgt = int(70 * (1 - x / 210.0) ** 1.4) + 18
        fill_rect(px, x, H - hgt, 1, hgt, (8, 10, 30))
    for x in range(560, W):
        hgt = int(60 * ((x - 560) / 208.0) ** 1.4) + 14
        fill_rect(px, x, H - hgt, 1, hgt, (8, 10, 30))
    # one lantern glowing on the near hill, a promise of a stay
    lantern(px, 120, H - 96, 6)

    # --- thin cream poster frame
    fill_rect(px, 20, 20, W - 40, 3, CREAM)
    fill_rect(px, 20, H - 23, W - 40, 3, CREAM)
    fill_rect(px, 20, 20, 3, H - 40, CREAM)
    fill_rect(px, W - 23, 20, 3, H - 40, CREAM)

    return px


def main():
    px = draw()
    size = write_png(px, OUT)
    print(f"wrote {OUT}: {W}x{H}, {size} bytes")


if __name__ == "__main__":
    main()
