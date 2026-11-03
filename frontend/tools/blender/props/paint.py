#!/usr/bin/env python3
"""
Painted textures for the roadside props (host python3 + PIL; run by prop_kit.paint, or by hand):
    python3 -I paint.py <outdir> vending bus
Everything is drawn from numbers here (no photo pixels). Fonts: Noto Sans CJK JP (SIL OFL 1.1) only.
No brands, logos or real product names: the drinks are generic categories with abstract labels.

vending.png  1024 x 1024, u right, v down
  left 576 x 1024 px: the machine's front (1.0 m x 1.83 m; x = -0.5..0.5 -> px 0..576, y = 1.83..0 -> px 0..1024)
  right part: the drink label atlas, 64 x 200 px cells at x = 608 + 66 col, y = 8 + 202 row
        row 0 PET bottles, row 1 cans, row 2 short cans (6 colours each), row 3: 0 button (lit), 1 dark trim, 2 steel
busstop.png  1024 x 1024: round stop sign (0..512 x 0..512), timetable board (512..1024 x 0..640)
"""
import math
import os
import sys

from PIL import Image, ImageDraw, ImageFilter, ImageFont

FONT = '/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc'
FONT_M = '/usr/share/fonts/opentype/noto/NotoSansCJK-Medium.ttc'


def font(size, medium=False):
    return ImageFont.truetype(FONT_M if medium else FONT, size, index=0)


def centered(d, xy, text, f, fill, anchor='mm'):
    d.text(xy, text, font=f, fill=fill, anchor=anchor)


def vgrad(img, box, c0, c1):
    x0, y0, x1, y1 = box
    d = ImageDraw.Draw(img)
    for y in range(y0, y1):
        t = (y - y0) / max(1, y1 - y0 - 1)
        d.line([(x0, y), (x1 - 1, y)], fill=tuple(int(a + (b - a) * t) for a, b in zip(c0, c1)))


# ------------------------------------------------------------------------------------------------ vending machine
PX_W, PX_H = 576, 1024
S = PX_H / 1.83


def X(x):
    return (x + 0.5) * PX_W


def Y(y):
    return (1.83 - y) * S


def rect_m(d, x0, x1, y0, y1, **kw):
    d.rectangle([X(x0), Y(y1), X(x1), Y(y0)], **kw)


def rrect_m(d, x0, x1, y0, y1, r, **kw):
    d.rounded_rectangle([X(x0), Y(y1), X(x1), Y(y0)], radius=r, **kw)


# window layout (shared with vending_machine.py)
WIN = (-0.46, 0.14, 0.60, 1.62)
ROWS = [1.28, 0.94, 0.60]          # shelf level y_b of the rows, top to bottom
COLS = [-0.46 + 0.05 + 0.1 * i for i in range(6)]
PRICES = [['130', '130', '160', '150', '120', '130'], ['120', '130', '130', '150', '160', '120'], ['130', '150', '150', '130', '160', '170']]

CELL_W, CELL_H = 64, 200
ATLAS_X, ATLAS_Y, ATLAS_DX, ATLAS_DY = 608, 8, 66, 202


def cell_origin(col, row):
    return ATLAS_X + ATLAS_DX * col, ATLAS_Y + ATLAS_DY * row


def shade(c, k):
    return tuple(max(0, min(255, int(v * k))) for v in c)


def paint_label(cell, colour, accent, kind, text, y0, y1):
    """abstract label on a 64 px wide wrap: its design stays in the front 40 px (centre x = 32)"""
    d = ImageDraw.Draw(cell)
    d.rectangle([0, y0, CELL_W, y1], fill=colour)
    cx = 32
    if kind == 0:      # big disc with a ring
        cy = (y0 + y1) // 2
        d.ellipse([cx - 15, cy - 15, cx + 15, cy + 15], fill=accent)
        d.ellipse([cx - 9, cy - 9, cx + 9, cy + 9], outline=colour, width=3)
    elif kind == 1:    # diagonal stripes
        for k in range(-4, 6):
            x = cx - 22 + k * 11
            d.polygon([(x, y1), (x + 5, y1), (x + 5 + 16, y0), (x + 16, y0)], fill=accent)
    elif kind == 2:    # leaf / drop
        cy = (y0 + y1) // 2
        d.polygon([(cx, cy - 22), (cx + 14, cy), (cx, cy + 20), (cx - 14, cy)], fill=accent)
        d.line([(cx, cy - 18), (cx, cy + 16)], fill=colour, width=2)
    elif kind == 3:    # waves
        for k in range(5):
            yy = y0 + 10 + k * (y1 - y0 - 20) / 4
            d.arc([cx - 24, yy - 6, cx + 24, yy + 6], 0, 180, fill=accent, width=3)
    elif kind == 4:    # bands
        d.rectangle([0, y0 + (y1 - y0) * 0.2, CELL_W, y0 + (y1 - y0) * 0.38], fill=accent)
        d.rectangle([0, y0 + (y1 - y0) * 0.62, CELL_W, y0 + (y1 - y0) * 0.72], fill=accent)
    else:              # dots
        for r in range(4):
            for c in range(3):
                x, y = cx - 14 + c * 14, y0 + 10 + r * (y1 - y0 - 20) / 3
                d.ellipse([x - 4, y - 4, x + 4, y + 4], fill=accent)
    if text:
        f = font(15)
        for i, ch in enumerate(text):
            centered(d, (cx, y0 + 8 + i * 17), ch, f, (255, 255, 255) if sum(colour) < 520 else (20, 20, 20))


def wrap_shading(cell, strength=0.30):
    """fake roundness: the front (u = 0.5) bright, the sides and the back darker"""
    px = cell.load()
    for x in range(CELL_W):
        k = (1 - strength) + strength * math.cos(2 * math.pi * ((x + 0.5) / CELL_W - 0.5))
        k = max(k, 1 - strength * 1.25)
        for y in range(CELL_H):
            r, g, b = px[x, y][:3]
            px[x, y] = (int(r * k), int(g * k), int(b * k))


def can_cell(colour, accent, kind, text):
    c = Image.new('RGB', (CELL_W, CELL_H), (190, 196, 202))
    d = ImageDraw.Draw(c)
    paint_label(c, colour, accent, kind, text, 24, 178)
    d.rectangle([0, 0, CELL_W, 8], fill=(150, 156, 162))
    d.rectangle([0, 8, CELL_W, 22], fill=(205, 210, 215))
    d.rectangle([0, 181, CELL_W, 190], fill=(205, 210, 215))
    d.rectangle([0, 190, CELL_W, CELL_H], fill=(140, 146, 152))
    wrap_shading(c)
    return c


def bottle_cell(liquid, label, accent, kind, text, cap):
    c = Image.new('RGB', (CELL_W, CELL_H), liquid)
    d = ImageDraw.Draw(c)
    d.rectangle([0, 0, CELL_W, 24], fill=cap)                       # cap
    d.rectangle([0, 24, CELL_W, 38], fill=shade(liquid, 1.1))     # neck ring
    for y in range(38, 190):                                       # liquid with a lighter shoulder
        t = (y - 38) / 152
        d.line([(0, y), (CELL_W, y)], fill=shade(liquid, 1.12 - 0.16 * t))
    paint_label(c, label, accent, kind, text, 86, 150)
    d.rectangle([0, 190, CELL_W, CELL_H], fill=shade(liquid, 0.7))
    wrap_shading(c, 0.28)
    return c


DRINKS = {
    # row 0: PET bottles: liquid, label, accent, pattern, text, cap
    0: [((120, 170, 90), (46, 120, 60), (230, 240, 210), 2, 'お茶', (30, 90, 40)),
        ((210, 232, 244), (240, 244, 248), (90, 150, 210), 3, '水', (70, 130, 200)),
        ((120, 70, 40), (230, 200, 150), (150, 70, 40), 0, '紅茶', (150, 40, 40)),
        ((196, 140, 50), (60, 60, 66), (230, 180, 70), 4, '烏龍', (60, 60, 66)),
        ((120, 190, 230), (40, 110, 200), (255, 255, 255), 1, 'スポ', (255, 255, 255)),
        ((240, 214, 90), (240, 190, 40), (255, 250, 220), 5, '檸檬', (240, 190, 40))],
    # row 1: cans
    1: [((120, 30, 30), (200, 40, 40), (255, 255, 255), 1, '', None), ((60, 160, 90), (70, 170, 100), (255, 255, 255), 2, '', None),
        ((240, 140, 30), (245, 150, 40), (255, 240, 200), 0, '', None), ((110, 70, 40), (170, 110, 60), (255, 230, 190), 3, '', None),
        ((90, 50, 130), (120, 70, 170), (230, 210, 250), 5, '', None), ((30, 30, 34), (40, 40, 46), (215, 175, 70), 4, '', None)],
    # row 2: short coffee / soup cans
    2: [((60, 40, 30), (90, 60, 40), (230, 200, 150), 3, '', None), ((200, 180, 140), (210, 190, 150), (110, 70, 40), 0, '', None),
        ((40, 40, 70), (50, 60, 110), (255, 255, 255), 1, '', None), ((230, 230, 230), (240, 240, 240), (200, 60, 50), 4, '', None),
        ((200, 70, 60), (210, 80, 70), (255, 230, 210), 5, '', None), ((50, 120, 80), (60, 140, 90), (255, 255, 255), 2, '', None)],
}


def vending(path):
    img = Image.new('RGB', (1024, 1024), (228, 232, 236))
    d = ImageDraw.Draw(img)
    # --- front plate base
    d.rectangle([0, 0, PX_W - 1, PX_H - 1], fill=(228, 232, 236))
    # header band
    vgrad(img, (int(X(-0.5)), int(Y(1.83)), int(X(0.5)), int(Y(1.64))), (38, 104, 190), (24, 76, 150))
    centered(d, (X(-0.25), Y(1.735)), 'つめたい', font(42), (255, 255, 255))
    centered(d, (X(0.22), Y(1.735)), 'あたたかい', font(34), (255, 214, 190))
    for cx_, col in ((X(-0.455), (255, 255, 255)), (X(0.455), (255, 160, 120))):
        d.ellipse([cx_ - 5, Y(1.735) - 5, cx_ + 5, Y(1.735) + 5], fill=col)
    # window: lit back wall with a floor of each shelf
    x0, x1, y0, y1 = WIN
    rrect_m(d, x0 - 0.02, x1 + 0.02, y0 - 0.02, y1 + 0.02, 8, fill=(54, 60, 68))
    vgrad(img, (int(X(x0)), int(Y(y1)), int(X(x1)), int(Y(y0))), (250, 252, 253), (222, 230, 236))
    d = ImageDraw.Draw(img)
    for r, yb in enumerate(ROWS):
        # button strip, price tags, shelf board
        rect_m(d, x0, x1, yb, yb + 0.05, fill=(70, 76, 84))
        rect_m(d, x0, x1, yb + 0.05, yb + 0.095, fill=(238, 242, 245))
        rect_m(d, x0, x1, yb + 0.095, yb + 0.108, fill=(176, 184, 192))
        for i, cx in enumerate(COLS):
            rrect_m(d, cx - 0.04, cx + 0.04, yb + 0.056, yb + 0.088, 3, fill=(255, 255, 255), outline=(120, 128, 136))
            centered(d, (X(cx), Y(yb + 0.072)), PRICES[r][i], font(15), (200, 30, 30) if (r + i) % 3 == 0 else (30, 30, 34))
        # soft shadow under the shelf above
        if r:
            for k in range(8):
                d.line([(X(x0), Y(yb + 0.34) + k), (X(x1), Y(yb + 0.34) + k)], fill=(214 - 4 * k, 222 - 4 * k, 228 - 4 * k))
    # --- right panel
    rrect_m(d, 0.19, 0.46, 0.60, 1.62, 14, fill=(206, 212, 218), outline=(150, 158, 166), width=2)
    rrect_m(d, 0.22, 0.43, 1.45, 1.58, 6, fill=(20, 22, 26))
    centered(d, (X(0.325), Y(1.515)), '130', font(34), (255, 70, 50))
    rrect_m(d, 0.22, 0.43, 1.28, 1.38, 5, fill=(236, 240, 243), outline=(130, 138, 146))
    centered(d, (X(0.325), Y(1.33)), 'お札', font(17, True), (50, 56, 64))
    rrect_m(d, 0.22, 0.43, 1.17, 1.25, 5, fill=(236, 240, 243), outline=(130, 138, 146))
    centered(d, (X(0.325), Y(1.21)), '硬貨', font(17, True), (50, 56, 64))
    for i, (txt, cx) in enumerate((('100', 0.25), ('50', 0.325), ('10', 0.40))):
        d.ellipse([X(cx) - 13, Y(1.10) - 13, X(cx) + 13, Y(1.10) + 13], fill=(205, 205, 200), outline=(120, 120, 116))
        centered(d, (X(cx), Y(1.10)), txt, font(11), (60, 60, 60))
    centered(d, (X(0.325), Y(0.985)), '返却', font(17, True), (50, 56, 64))
    centered(d, (X(0.325), Y(0.81)), 'つり銭', font(15, True), (50, 56, 64))
    rrect_m(d, 0.22, 0.43, 0.64, 0.76, 6, fill=(44, 48, 54))
    # --- dispensing bay
    rrect_m(d, -0.44, 0.17, 0.10, 0.52, 10, fill=(58, 64, 72))
    rrect_m(d, -0.40, 0.13, 0.14, 0.40, 8, fill=(34, 38, 44), outline=(120, 128, 136), width=2)
    centered(d, (X(-0.135), Y(0.46)), '取り出し口', font(22), (235, 240, 244))
    centered(d, (X(-0.135), Y(0.27)), '▼ PUSH', font(26), (150, 160, 170))
    # plinth
    rect_m(d, -0.5, 0.5, 0.0, 0.10, fill=(52, 56, 62))
    # --- atlas
    d.rectangle([600, 0, 1024, 1024], fill=(20, 20, 24))
    for row, items in DRINKS.items():
        for col, it in enumerate(items):
            cell = bottle_cell(*it) if row == 0 else can_cell(*it[1:5])
            img.paste(cell, cell_origin(col, row))
    # row 3: lit button, dark trim, steel
    for col, fill in enumerate(((255, 244, 206), (34, 38, 44), (186, 192, 198), (255, 255, 255))):
        cell = Image.new('RGB', (CELL_W, CELL_H), fill)
        if col == 0:
            dd = ImageDraw.Draw(cell)
            dd.ellipse([20, 60, 44, 84], fill=(255, 90, 60))
        img.paste(cell, cell_origin(col, 3))
    img.save(path)


# ------------------------------------------------------------------------------------------------ bus stop
def bus(path):
    img = Image.new('RGB', (1024, 1024), (240, 240, 236))
    d = ImageDraw.Draw(img)
    # --- round sign 512 px = 0.5 m
    d.rectangle([0, 0, 511, 511], fill=(240, 240, 236))
    d.ellipse([4, 4, 507, 507], fill=(31, 78, 153))
    d.ellipse([26, 26, 485, 485], fill=(250, 250, 248))
    # bus pictogram
    bx, by = 256, 118
    d.rounded_rectangle([bx - 56, by - 28, bx + 56, by + 28], 10, fill=(31, 78, 153))
    for k in range(4):
        d.rectangle([bx - 46 + k * 25, by - 18, bx - 28 + k * 25, by - 2], fill=(250, 250, 248))
    d.ellipse([bx - 40, by + 18, bx - 20, by + 38], fill=(31, 78, 153), outline=(250, 250, 248), width=3)
    d.ellipse([bx + 20, by + 18, bx + 40, by + 38], fill=(31, 78, 153), outline=(250, 250, 248), width=3)
    centered(d, (256, 262), '朧峠入口', font(76), (24, 30, 40))
    centered(d, (256, 338), 'おぼろとうげいりぐち', font(30, True), (60, 66, 76))
    d.rounded_rectangle([156, 376, 356, 434], 29, fill=(31, 78, 153))
    centered(d, (256, 405), 'のりば 1', font(34), (255, 255, 255))
    # --- timetable board 512 x 640 at (512, 0)
    ox = 512
    d.rectangle([ox, 0, ox + 511, 639], fill=(248, 248, 244))
    d.rectangle([ox + 8, 8, ox + 503, 631], outline=(40, 70, 130), width=5)
    d.rectangle([ox + 8, 8, ox + 503, 84], fill=(31, 78, 153))
    centered(d, (ox + 150, 46), '朧峠入口', font(44), (255, 255, 255))
    centered(d, (ox + 380, 46), '時刻表', font(36), (255, 245, 200))
    d.rectangle([ox + 20, 96, ox + 490, 132], fill=(220, 228, 240))
    for x, t in ((ox + 60, '時'), (ox + 215, '平日'), (ox + 395, '土日祝')):
        centered(d, (x, 114), t, font(22), (30, 40, 70))
    mins = {6: ('20 50', '40'), 7: ('15 45', '30'), 8: ('10 40', '20 50'), 9: ('30', '35'), 10: ('05 50', '—'), 11: ('40', '25'),
            12: ('20', '—'), 13: ('05 45', '10'), 14: ('30', '—'), 15: ('15 55', '40'), 16: ('35', '—'), 17: ('10 40', '25'),
            18: ('05 50', '—'), 19: ('30', '30'), 20: ('15', '—')}
    for i, (h, (wk, we)) in enumerate(mins.items()):
        y = 148 + i * 31
        if i % 2:
            d.rectangle([ox + 20, y - 14, ox + 490, y + 16], fill=(240, 243, 248))
        centered(d, (ox + 60, y), str(h), font(22), (30, 30, 36))
        centered(d, (ox + 215, y), wk, font(20, True), (30, 30, 36))
        centered(d, (ox + 395, y), we, font(20, True), (170, 40, 40) if we != '—' else (120, 120, 120))
    centered(d, (ox + 256, 616), '運行状況は窓口へ', font(15, True), (90, 96, 110))
    img.save(path)


if __name__ == '__main__':
    out = sys.argv[1]
    os.makedirs(out, exist_ok=True)
    for n in sys.argv[2:]:
        {'vending': lambda: vending(os.path.join(out, 'vending.png')), 'bus': lambda: bus(os.path.join(out, 'busstop.png'))}[n]()
