#!/usr/bin/env python3
"""
Painted textures for the roadside props (host python3 + PIL; run by prop_kit.paint, or by hand):
    python3 -I paint.py <outdir> vending bus
Everything is drawn from numbers here (no photo pixels). Fonts: Noto Sans CJK JP (SIL OFL 1.1) only.
No brands, logos or real product names: the drinks are generic categories with abstract labels.

vending_plate.png   1152 x 2048: the machine's front elevation (1.0 m x 1.83 m; x = -0.5..0.5, y = 1.83..0), which
                    every face of the model that looks to the front takes its colour from
vending_emit.png    the same at half size: what of it is lit (buttons, the price display)
vending_labels.png  640 x 640: the samples' labels, 64 x 200 px cells at x = 8 + 66 col, y = 8 + 202 row
                    (row 0 PET bottles, row 1 cans, row 2 short cans; 9 each)
vending_sticker.png the address sticker on the cabinet's side
busstop.png  1024 x 1024: round stop sign (0..512 x 0..512), timetable board (512..1024 x 0..640)
pole_tag.png the street light's number plate
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
# the machine's front elevation: 1.0 m x 1.83 m on 1152 x 2048 px
PX_W, PX_H = 1152, 2048
S = PX_H / 1.83


def X(x):
    return (x + 0.5) * PX_W


def Y(y):
    return (1.83 - y) * S


def rect_m(d, x0, x1, y0, y1, **kw):
    d.rectangle([X(x0), Y(y1), X(x1), Y(y0)], **kw)


def rrect_m(d, x0, x1, y0, y1, r, **kw):
    d.rounded_rectangle([X(x0), Y(y1), X(x1), Y(y0)], radius=r, **kw)


# layout (shared with vending_machine.py): the display window, the shelf level of its rows (top to bottom), the columns
WIN = (-0.43, 0.43, 0.86, 1.70)
ROWS = [1.42, 1.14, 0.86]
NCOL = 9
COLS = [WIN[0] + (WIN[1] - WIN[0]) * (i + 0.5) / NCOL for i in range(NCOL)]
PRICES = [['160', '130', '160', '160', '150', '160', '130', '160', '170'], ['130', '130', '120', '130', '140', '130', '120', '130', '150'],
          ['130', '120', '130', '110', '130', '130', '130', '140', '130']]


def is_hot(row, col):
    """the warm drinks: the right half of the bottom row"""
    return row == 2 and col >= 4


CELL_W, CELL_H = 64, 200
ATLAS_X, ATLAS_Y, ATLAS_DX, ATLAS_DY = 8, 8, 66, 202


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


def vary(c, k):
    """the same design in another colourway"""
    if c is None or k == 0:
        return c
    r, g, b = c
    return (b, r, g) if k == 1 else (g, b, r)


def vending(out):
    """vending_plate.png (the front elevation), vending_emit.png (what of it is lit), vending_labels.png, vending_sticker.png"""
    DOOR = (231, 234, 237)
    plate = Image.new('RGB', (PX_W, PX_H), DOOR)
    glow = Image.new('RGB', (PX_W, PX_H), (0, 0, 0))
    d, e = ImageDraw.Draw(plate), ImageDraw.Draw(glow)
    # --- header: cold on blue, hot on red
    vgrad(plate, (0, int(Y(1.83)), int(X(0.16)), int(Y(1.70))), (40, 108, 196), (22, 72, 150))
    vgrad(plate, (int(X(0.16)), int(Y(1.83)), PX_W, int(Y(1.70))), (214, 70, 48), (168, 40, 30))
    d = ImageDraw.Draw(plate)
    centered(d, (X(-0.17), Y(1.765)), 'つめた〜い', font(88), (255, 255, 255))
    centered(d, (X(0.33), Y(1.765)), 'あったか〜い', font(46), (255, 236, 220))
    rect_m(d, -0.5, 0.5, 1.696, 1.704, fill=(190, 196, 202))
    # --- the window's bezel
    x0, x1, y0, y1 = WIN
    rect_m(d, -0.5, x0, y0, y1, fill=(196, 201, 207))
    rect_m(d, x1, 0.5, y0, y1, fill=(196, 201, 207))
    # --- under each row of samples: the price tags, the buttons (lit: blue = cold, red = hot)
    for r, yb in enumerate(ROWS):
        rect_m(d, x0, x1, yb, yb + 0.05, fill=(56, 62, 70))
        for i, cx in enumerate(COLS):
            rrect_m(d, cx - 0.037, cx + 0.037, yb + 0.027, yb + 0.047, 5, fill=(250, 250, 248), outline=(120, 128, 136))
            centered(d, (X(cx), Y(yb + 0.037)), '¥' + PRICES[r][i], font(19), (26, 28, 34))
            hot = is_hot(r, i)
            col = (224, 70, 50) if hot else (44, 118, 214)
            rrect_m(d, cx - 0.035, cx + 0.035, yb + 0.004, yb + 0.023, 6, fill=col)
            rrect_m(e, cx - 0.035, cx + 0.035, yb + 0.004, yb + 0.023, 6, fill=(255, 96, 64) if hot else (70, 150, 255))
            for im in (d, e):
                centered(im, (X(cx), Y(yb + 0.0135)), 'あたたかい' if hot else 'つめたい', font(13 if hot else 16), (255, 255, 255))
    # --- the belt: a poster, the payment panel
    px0, px1, py0, py1 = -0.45, 0.09, 0.53, 0.83
    vgrad(plate, (int(X(px0)), int(Y(py1)), int(X(px1)), int(Y(py0))), (36, 122, 150), (16, 60, 92))
    d = ImageDraw.Draw(plate)
    d.polygon([(X(px0), Y(py0)), (X(-0.33), Y(0.70)), (X(-0.24), Y(0.63)), (X(-0.12), Y(0.74)), (X(0.02), Y(0.60)), (X(px1), Y(0.66)), (X(px1), Y(py0))], fill=(12, 44, 70))
    d.polygon([(X(-0.33), Y(0.70)), (X(-0.305), Y(0.68)), (X(-0.33), Y(0.672)), (X(-0.352), Y(0.68))], fill=(235, 242, 246))
    d.polygon([(X(-0.12), Y(0.74)), (X(-0.09), Y(0.712)), (X(-0.12), Y(0.70)), (X(-0.148), Y(0.714))], fill=(235, 242, 246))
    centered(d, (X(-0.18), Y(0.79)), '朧峠の天然水', font(52), (255, 255, 255))
    centered(d, (X(-0.18), Y(0.565)), 'よく冷えています', font(30, True), (220, 240, 248))
    d.rectangle([X(px0), Y(py1), X(px1), Y(py0)], outline=(150, 158, 166), width=3)
    rrect_m(d, 0.14, 0.455, 0.52, 0.84, 16, fill=(206, 211, 217), outline=(146, 154, 162), width=3)
    rrect_m(d, 0.17, 0.425, 0.772, 0.826, 8, fill=(14, 15, 18))
    for im in (d, e):
        centered(im, (X(0.33), Y(0.799)), '130', font(50), (255, 60, 44))
    centered(d, (X(0.215), Y(0.799)), '金額', font(15, True), (150, 156, 164))
    centered(d, (X(0.215), Y(0.745)), 'お札', font(20, True), (44, 50, 58))
    rrect_m(d, 0.26, 0.42, 0.728, 0.762, 5, fill=(40, 44, 50))
    centered(d, (X(0.215), Y(0.672)), '硬貨', font(20, True), (44, 50, 58))
    rrect_m(d, 0.30, 0.38, 0.648, 0.698, 5, fill=(186, 192, 198), outline=(110, 118, 126))
    d.ellipse([X(0.215) - 36, Y(0.595) - 36, X(0.215) + 36, Y(0.595) + 36], fill=(34, 38, 46), outline=(110, 118, 126), width=3)
    centered(d, (X(0.215), Y(0.595)), 'IC', font(26), (140, 190, 255))
    e.ellipse([X(0.215) - 36, Y(0.595) - 36, X(0.215) + 36, Y(0.595) + 36], outline=(50, 110, 220), width=4)
    centered(d, (X(0.36), Y(0.618)), '返却', font(18, True), (44, 50, 58))
    centered(d, (X(0.30), Y(0.545)), 'ICカード・現金 使えます', font(13, True), (90, 96, 106))
    # --- below: the take-out port, the change cup, the lock, a warning label
    centered(d, (X(-0.10), Y(0.468)), '取り出し口', font(26), (70, 76, 86))
    rrect_m(d, -0.425, 0.225, 0.135, 0.445, 14, fill=(52, 57, 64), outline=(150, 158, 166), width=3)
    rrect_m(d, -0.40, 0.20, 0.16, 0.40, 10, fill=(20, 22, 26))
    centered(d, (X(-0.10), Y(0.28)), '▼  PUSH', font(40), (104, 112, 122))
    centered(d, (X(0.35), Y(0.428)), 'つり銭', font(18, True), (70, 76, 86))
    rrect_m(d, 0.28, 0.42, 0.30, 0.40, 8, fill=(30, 33, 38), outline=(150, 158, 166), width=2)
    rrect_m(d, 0.255, 0.445, 0.118, 0.172, 4, fill=(250, 212, 50), outline=(30, 30, 30))
    centered(d, (X(0.35), Y(0.156)), '注意 ゆすらないで', font(15), (20, 20, 20))
    centered(d, (X(0.35), Y(0.134)), '転倒のおそれがあります', font(12, True), (20, 20, 20))
    plate.save(os.path.join(out, 'vending_plate.png'))
    glow.resize((PX_W // 2, PX_H // 2), Image.LANCZOS).save(os.path.join(out, 'vending_emit.png'))
    # --- the samples' labels
    lab = Image.new('RGB', (640, 640), (20, 20, 24))
    for row, items in DRINKS.items():
        for col in range(NCOL):
            it = items[col % len(items)]
            k = col // len(items)
            if row == 0:
                liquid, label, accent, kind, text, cap = it
                cell = bottle_cell(liquid, vary(label, k), vary(accent, k), kind, text, vary(cap, k))
            else:
                colour, accent, kind, text = it[1:5]
                cell = can_cell(vary(colour, k), vary(accent, k), kind, text)
            lab.paste(cell, cell_origin(col, row))
    lab.save(os.path.join(out, 'vending_labels.png'))
    # --- the address sticker on the cabinet's side (every machine in Japan carries one for emergency calls)
    st = Image.new('RGB', (384, 144), (250, 250, 246))
    sd = ImageDraw.Draw(st)
    sd.rectangle([0, 0, 383, 143], outline=(20, 120, 70), width=6)
    sd.rectangle([0, 0, 383, 40], fill=(20, 120, 70))
    centered(sd, (192, 20), 'ここの住所は', font(26), (255, 255, 255))
    centered(sd, (192, 78), '朧峠 山頂 1-27', font(38), (20, 24, 30))
    centered(sd, (192, 120), '緊急のときは 110・119', font(20, True), (60, 66, 76))
    st.save(os.path.join(out, 'vending_sticker.png'))


# ------------------------------------------------------------------------------------------------ bus stop
def bus(out):
    path = os.path.join(out, 'busstop.png')
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
    # --- an enamel sign of the local taxi (0.45 x 0.60 m) at (0, 512) .. (384, 1024)
    d.rectangle([0, 512, 383, 1023], fill=(22, 44, 96))
    d.rectangle([10, 522, 373, 1013], outline=(240, 240, 232), width=5)
    for i, ch in enumerate('朧タクシー'):
        centered(d, (120, 580 + i * 84), ch, font(78), (245, 245, 238))
    for i, ch in enumerate('お電話一本'):
        centered(d, (262, 590 + i * 56), ch, font(44), (250, 208, 60))
    d.rectangle([222, 880, 362, 884], fill=(240, 240, 232))
    centered(d, (192, 962), '☎ 27-0127', font(54), (245, 245, 238))
    # --- the town's bear warning (0.64 x 0.48 m) at (512, 640) .. (1024, 1024)
    d.rectangle([512, 640, 1023, 1023], fill=(250, 214, 40))
    d.rectangle([522, 650, 1013, 1013], outline=(20, 20, 20), width=8)
    centered(d, (768, 730), 'クマ出没注意', font(74), (200, 24, 24))
    centered(d, (768, 836), 'この付近で目撃されています', font(31), (20, 20, 20))
    centered(d, (768, 892), '早朝・夕方はとくに注意', font(31), (20, 20, 20))
    centered(d, (768, 968), '朧町役場 農林課', font(28, True), (40, 40, 40))
    img.save(path)


# ------------------------------------------------------------------------------------------------ street light
def pole(out):
    path = os.path.join(out, 'pole_tag.png')
    """the number plate strapped to a lighting pole (85 x 170 mm → 128 x 256 px): what it is, its road, its number"""
    img = Image.new('RGB', (128, 256), (238, 238, 232))
    d = ImageDraw.Draw(img)
    d.rectangle([3, 3, 124, 252], outline=(40, 44, 50), width=2)
    d.rectangle([5, 5, 122, 60], fill=(28, 70, 140))
    centered(d, (64, 20), '道路', font(24), (255, 255, 255))
    centered(d, (64, 44), '照明灯', font(20), (255, 255, 255))
    centered(d, (64, 84), '朧峠線', font(24), (24, 28, 34))
    d.line([(14, 106), (114, 106)], fill=(40, 44, 50), width=2)
    centered(d, (64, 140), '27', font(52), (24, 28, 34))
    d.line([(14, 176), (114, 176)], fill=(40, 44, 50), width=2)
    centered(d, (64, 198), '管理番号', font(17, True), (60, 64, 72))
    centered(d, (64, 226), 'OB-0127', font(20), (24, 28, 34))
    img.save(path)


# ------------------------------------------------------------------------------------------------ curve mirror
def mirror(out):
    """mirror_tag.png: the road office's sticker on the pole (70 x 105 mm); mirror_chui.png: the 注意 plate (400 x 150 mm)"""
    img = Image.new('RGB', (128, 192), (240, 240, 234))
    d = ImageDraw.Draw(img)
    d.rectangle([2, 2, 125, 189], outline=(40, 44, 50), width=2)
    d.rectangle([4, 4, 123, 50], fill=(210, 90, 20))
    centered(d, (64, 26), '道路反射鏡', font(21), (255, 255, 255))
    centered(d, (64, 78), '朧峠線', font(24), (24, 28, 34))
    centered(d, (64, 116), 'M-12', font(34), (24, 28, 34))
    d.line([(14, 142), (114, 142)], fill=(40, 44, 50), width=2)
    centered(d, (64, 164), '破損時は連絡を', font(14, True), (60, 64, 72))
    img.save(os.path.join(out, 'mirror_tag.png'))
    img = Image.new('RGB', (512, 192), (250, 208, 30))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([6, 6, 505, 185], 14, outline=(20, 20, 20), width=7)
    centered(d, (256, 92), '注　意', font(120), (20, 20, 20))
    img.save(os.path.join(out, 'mirror_chui.png'))


# ------------------------------------------------------------------------------------------------ torii
FONT_SERIF = '/usr/share/fonts/opentype/noto/NotoSerifCJK-Bold.ttc'


def torii(out):
    """torii_plaque.png: the shrine's name board (扁額, 440 x 660 mm): gilt characters cut into black lacquer, a gilt border"""
    w, h = 320, 480
    img = Image.new('RGB', (w, h), (22, 18, 15))
    d = ImageDraw.Draw(img)
    gold = (196, 150, 58)
    d.rectangle([10, 10, w - 11, h - 11], outline=gold, width=5)
    d.rectangle([20, 20, w - 21, h - 21], outline=(120, 90, 34), width=2)
    f = ImageFont.truetype(FONT_SERIF, 132, index=0)
    for k, ch in enumerate('朧神社'):
        centered(d, (w // 2, 96 + k * 144), ch, f, gold)
    img.save(os.path.join(out, 'torii_plaque.png'))


PAINTERS = {'vending': vending, 'bus': bus, 'pole': pole, 'mirror': mirror, 'torii': torii}

if __name__ == '__main__':
    out = sys.argv[1]
    os.makedirs(out, exist_ok=True)
    for n in sys.argv[2:]:
        PAINTERS[n](out)
