"""
Chapel Street Research — pixel logo generator.
Renders a "CS" monogram with "RESEARCH" wordmark below, at low logical
resolution then scales up with nearest-neighbor to keep crisp pixel edges.
"""

from PIL import Image, ImageDraw

# -----------------------------------------------------------------------------
# Palette (matches the site)
# -----------------------------------------------------------------------------
BG       = (10, 10, 10)        # #0a0a0a
BG_SOFT  = (17, 17, 20)        # #111114
GREY     = (60, 64, 72)        # #3c4048
GREY_DIM = (42, 45, 51)        # #2a2d33
WHITE    = (244, 246, 248)     # #f4f6f8
TEXT_DIM = (138, 143, 152)     # #8a8f98
BLUE     = (107, 155, 196)     # #6b9bc4
BLUE_DIM = (74, 119, 153)      # #4a7799
SCAN     = (255, 255, 255, 8)  # subtle scan-line overlay

# -----------------------------------------------------------------------------
# 5x7 pixel font (just the chars we need)
# -----------------------------------------------------------------------------
FONT5x7 = {
    'A': ["01110","10001","10001","11111","10001","10001","10001"],
    'B': ["11110","10001","10001","11110","10001","10001","11110"],
    'C': ["01111","10000","10000","10000","10000","10000","01111"],
    'D': ["11110","10001","10001","10001","10001","10001","11110"],
    'E': ["11111","10000","10000","11110","10000","10000","11111"],
    'F': ["11111","10000","10000","11110","10000","10000","10000"],
    'G': ["01111","10000","10000","10011","10001","10001","01111"],
    'H': ["10001","10001","10001","11111","10001","10001","10001"],
    'I': ["01110","00100","00100","00100","00100","00100","01110"],
    'J': ["00111","00010","00010","00010","00010","10010","01100"],
    'K': ["10001","10010","10100","11000","10100","10010","10001"],
    'L': ["10000","10000","10000","10000","10000","10000","11111"],
    'M': ["10001","11011","10101","10001","10001","10001","10001"],
    'N': ["10001","11001","10101","10101","10011","10001","10001"],
    'O': ["01110","10001","10001","10001","10001","10001","01110"],
    'P': ["11110","10001","10001","11110","10000","10000","10000"],
    'Q': ["01110","10001","10001","10001","10101","10010","01101"],
    'R': ["11110","10001","10001","11110","10100","10010","10001"],
    'S': ["01111","10000","10000","01110","00001","00001","11110"],
    'T': ["11111","00100","00100","00100","00100","00100","00100"],
    'U': ["10001","10001","10001","10001","10001","10001","01110"],
    'V': ["10001","10001","10001","10001","10001","01010","00100"],
    'W': ["10001","10001","10001","10001","10101","11011","10001"],
    'X': ["10001","10001","01010","00100","01010","10001","10001"],
    'Y': ["10001","10001","10001","01010","00100","00100","00100"],
    'Z': ["11111","00001","00010","00100","01000","10000","11111"],
    '0': ["01110","10001","10011","10101","11001","10001","01110"],
    '1': ["00100","01100","00100","00100","00100","00100","01110"],
    '2': ["01110","10001","00001","00010","00100","01000","11111"],
    '3': ["11110","00001","00001","01110","00001","00001","11110"],
    '4': ["00010","00110","01010","10010","11111","00010","00010"],
    '5': ["11111","10000","11110","00001","00001","10001","01110"],
    '6': ["00110","01000","10000","11110","10001","10001","01110"],
    '7': ["11111","00001","00010","00100","01000","01000","01000"],
    '8': ["01110","10001","10001","01110","10001","10001","01110"],
    '9': ["01110","10001","10001","01111","00001","00010","01100"],
    '.': ["00000","00000","00000","00000","00000","00000","00100"],
    '/': ["00001","00010","00010","00100","01000","01000","10000"],
    '·': ["00000","00000","00000","00100","00000","00000","00000"],
    ' ': ["00000","00000","00000","00000","00000","00000","00000"],
    '-': ["00000","00000","00000","11111","00000","00000","00000"],
}

# -----------------------------------------------------------------------------
# 9x12 chunky font for the QBRIDGE wordmark
# (block-style; reads like a CRT bitmap font)
# -----------------------------------------------------------------------------
FONT9x12 = {
    'Q': [
        "001111100",
        "011111110",
        "110000011",
        "110000011",
        "110000011",
        "110000011",
        "110000011",
        "110010011",
        "110011011",
        "011111110",
        "001111100",
        "000000111",
    ],
    'B': [
        "111111100",
        "111111110",
        "110000011",
        "110000011",
        "110000111",
        "111111110",
        "111111110",
        "110000111",
        "110000011",
        "110000011",
        "111111110",
        "111111100",
    ],
    'R': [
        "111111100",
        "111111110",
        "110000011",
        "110000011",
        "110000011",
        "111111110",
        "111111100",
        "110011000",
        "110001100",
        "110000110",
        "110000011",
        "110000011",
    ],
    'I': [
        "111111111",
        "111111111",
        "000111000",
        "000111000",
        "000111000",
        "000111000",
        "000111000",
        "000111000",
        "000111000",
        "000111000",
        "111111111",
        "111111111",
    ],
    'D': [
        "111111100",
        "111111110",
        "110000011",
        "110000011",
        "110000011",
        "110000011",
        "110000011",
        "110000011",
        "110000011",
        "110000011",
        "111111110",
        "111111100",
    ],
    'G': [
        "001111110",
        "011111111",
        "110000001",
        "110000000",
        "110000000",
        "110000000",
        "110001111",
        "110000011",
        "110000011",
        "110000011",
        "011111111",
        "001111110",
    ],
    'E': [
        "111111111",
        "111111111",
        "110000000",
        "110000000",
        "110000000",
        "111111100",
        "111111100",
        "110000000",
        "110000000",
        "110000000",
        "111111111",
        "111111111",
    ],
    'A': [
        "000111000",
        "001111100",
        "011000110",
        "110000011",
        "110000011",
        "110000011",
        "111111111",
        "111111111",
        "110000011",
        "110000011",
        "110000011",
        "110000011",
    ],
    'Y': [
        "110000011",
        "110000011",
        "011000110",
        "011000110",
        "001111100",
        "000111000",
        "000111000",
        "000111000",
        "000111000",
        "000111000",
        "000111000",
        "000111000",
    ],
    'K': [
        "110000110",
        "110001100",
        "110011000",
        "110110000",
        "111100000",
        "111000000",
        "111100000",
        "110110000",
        "110011000",
        "110001100",
        "110000110",
        "110000011",
    ],
    'S': [
        "001111110",
        "011111111",
        "110000011",
        "110000000",
        "110000000",
        "011111100",
        "001111110",
        "000000011",
        "000000011",
        "110000011",
        "111111110",
        "011111100",
    ],
    'T': [
        "111111111",
        "111111111",
        "000111000",
        "000111000",
        "000111000",
        "000111000",
        "000111000",
        "000111000",
        "000111000",
        "000111000",
        "000111000",
        "000111000",
    ],
    'M': [
        "110000011",
        "111000111",
        "111101111",
        "110111011",
        "110010011",
        "110000011",
        "110000011",
        "110000011",
        "110000011",
        "110000011",
        "110000011",
        "110000011",
    ],
    'C': [
        "001111110",
        "011111111",
        "110000011",
        "110000000",
        "110000000",
        "110000000",
        "110000000",
        "110000000",
        "110000000",
        "110000011",
        "011111111",
        "001111110",
    ],
    'H': [
        "110000011",
        "110000011",
        "110000011",
        "110000011",
        "110000011",
        "111111111",
        "111111111",
        "110000011",
        "110000011",
        "110000011",
        "110000011",
        "110000011",
    ],
}

# -----------------------------------------------------------------------------
# Drawing helpers
# -----------------------------------------------------------------------------
def draw_bitmap(draw, bitmap, x, y, color, scale=1):
    """Draw a 2D string bitmap (list of '01' strings) at (x, y)."""
    for row, line in enumerate(bitmap):
        for col, ch in enumerate(line):
            if ch == '1':
                px = x + col * scale
                py = y + row * scale
                if scale == 1:
                    draw.point((px, py), fill=color)
                else:
                    draw.rectangle([px, py, px + scale - 1, py + scale - 1], fill=color)


def text_5x7(draw, text, x, y, color, char_w=5, char_h=7, gap=1, scale=1):
    cx = x
    for ch in text:
        glyph = FONT5x7.get(ch, FONT5x7[' '])
        draw_bitmap(draw, glyph, cx, y, color, scale=scale)
        cx += (char_w + gap) * scale
    return cx


def text_9x12(draw, text, x, y, color, char_w=9, char_h=12, gap=2, scale=1):
    cx = x
    for ch in text:
        glyph = FONT9x12.get(ch)
        if glyph is None:
            cx += (char_w + gap) * scale
            continue
        draw_bitmap(draw, glyph, cx, y, color, scale=scale)
        cx += (char_w + gap) * scale
    return cx


def measure_5x7(text, char_w=5, gap=1, scale=1):
    return (len(text) * char_w + (len(text) - 1) * gap) * scale


def measure_9x12(text, char_w=9, gap=2, scale=1):
    return (len(text) * char_w + (len(text) - 1) * gap) * scale


# -----------------------------------------------------------------------------
# Compose the logo at logical 128x128 then scale up
# -----------------------------------------------------------------------------
def build_logo(logical_size=128, scale=8):
    W = H = logical_size
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)

    # ---- subtle background grid (diagonal pattern, every 4th pixel) ----
    for y in range(0, H, 4):
        for x in range(0, W, 4):
            if (x + y) % 8 == 0:
                d.point((x, y), fill=BG_SOFT)

    # ---- frame (thin double-line border with gaps) ----
    inner_pad = 4
    # outer hairline
    d.rectangle([inner_pad, inner_pad, W - inner_pad - 1, H - inner_pad - 1],
                outline=GREY_DIM)

    # ---- corner brackets in blue ----
    bl = 9  # bracket length
    bw = 2  # bracket thickness
    bp = 6  # bracket inset from edge
    corners = [
        (bp, bp, +1, +1),                 # top-left
        (W - bp - 1, bp, -1, +1),         # top-right
        (bp, H - bp - 1, +1, -1),         # bottom-left
        (W - bp - 1, H - bp - 1, -1, -1), # bottom-right
    ]
    for cx, cy, dx, dy in corners:
        # horizontal arm
        x0 = cx
        x1 = cx + dx * (bl - 1)
        d.rectangle([min(x0, x1), cy, max(x0, x1), cy + (bw - 1)],
                    fill=BLUE)
        # vertical arm
        y0 = cy
        y1 = cy + dy * (bl - 1)
        d.rectangle([cx, min(y0, y1), cx + (bw - 1), max(y0, y1)],
                    fill=BLUE)

    # ---- big "CS" monogram (9x12 glyphs scaled up) ----
    cs_scale = 5
    cs = "CS"
    cs_w = measure_9x12(cs, scale=cs_scale)
    cs_h = 12 * cs_scale
    cx_logo = (W - cs_w) // 2
    cy_logo = 18
    text_9x12(d, cs, cx_logo, cy_logo, BLUE, scale=cs_scale)

    # ---- "RESEARCH" wordmark below ----
    word = "RESEARCH"
    word_w = measure_9x12(word)
    wx = (W - word_w) // 2
    wy = 94
    text_9x12(d, word, wx, wy, WHITE)

    # underline accent under wordmark
    ul_pad = 4
    d.rectangle([wx - ul_pad, wy + 14, wx + word_w + ul_pad - 1, wy + 14], fill=BLUE)

    # ---- scale up with nearest-neighbor for crisp pixels ----
    big = img.resize((W * scale, H * scale), Image.NEAREST)

    # ---- scan-line overlay on the upscaled image ----
    overlay = Image.new("RGBA", big.size, (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    line_step = 4  # every Nth row in the upscaled image
    for y in range(0, big.size[1], line_step):
        od.line([(0, y), (big.size[0], y)], fill=SCAN)
    big = Image.alpha_composite(big.convert("RGBA"), overlay).convert("RGB")

    return big


def build_icon_only(logical_size=64, scale=16):
    """Compact 1024x1024 mark — just Q + bridge, no text. For small uses."""
    W = H = logical_size
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)

    # background grid texture
    for y in range(0, H, 4):
        for x in range(0, W, 4):
            if (x + y) % 8 == 0:
                d.point((x, y), fill=BG_SOFT)

    # corner brackets
    bl = 6
    bw = 1
    bp = 3
    corners = [
        (bp, bp, +1, +1),
        (W - bp - 1, bp, -1, +1),
        (bp, H - bp - 1, +1, -1),
        (W - bp - 1, H - bp - 1, -1, -1),
    ]
    for cx, cy, dx, dy in corners:
        x0 = cx; x1 = cx + dx * (bl - 1)
        d.rectangle([min(x0, x1), cy, max(x0, x1), cy + (bw - 1)], fill=BLUE)
        y0 = cy; y1 = cy + dy * (bl - 1)
        d.rectangle([cx, min(y0, y1), cx + (bw - 1), max(y0, y1)], fill=BLUE)

    # large pixel "Q" centered with bridge tail
    Q = [
        "0011111100",
        "0111111110",
        "1100000011",
        "1100000011",
        "1100000011",
        "1100000011",
        "1100000011",
        "1100000011",
        "1100100011",
        "1100110011",
        "0111111110",
        "0011111110",
        "0000000011",
        "0000000111",
        "0000001110",
    ]
    qx = (W - 10) // 2
    qy = 18
    draw_bitmap(d, Q, qx, qy, BLUE)

    # bridge underline (small bridge silhouette under the Q)
    base_y = qy + len(Q) + 4
    left = qx - 6
    right = qx + 16
    # deck
    d.rectangle([left, base_y, right, base_y], fill=BLUE)
    # towers
    d.rectangle([left + 4, base_y - 4, left + 4, base_y - 1], fill=BLUE)
    d.rectangle([right - 4, base_y - 4, right - 4, base_y - 1], fill=BLUE)
    # cable
    span = (right - 4) - (left + 4)
    for x in range(left + 4, right - 4 + 1):
        t = (x - (left + 4)) / span
        y = (base_y - 4) + int(round(3 * 4 * t * (1 - t)))
        d.point((x, y), fill=BLUE_DIM)

    big = img.resize((W * scale, H * scale), Image.NEAREST)
    overlay = Image.new("RGBA", big.size, (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    for y in range(0, big.size[1], 4):
        od.line([(0, y), (big.size[0], y)], fill=SCAN)
    big = Image.alpha_composite(big.convert("RGBA"), overlay).convert("RGB")
    return big


if __name__ == "__main__":
    full = build_logo(logical_size=128, scale=8)   # 1024 x 1024
    full.save("/Users/tre/Desktop/QBridge Site/chapelstreet-logo.png")
    print(f"Saved logo: {full.size}")
