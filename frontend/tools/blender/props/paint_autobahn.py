#!/usr/bin/env python3
"""
Painted textures of the AUTOBAHN course (host python3 + PIL), all drawn from numbers here: no photo pixels.
Lettering: Noto Sans CJK (SIL OFL 1.1) only. Place names are invented; the motorway number "A 77" does not exist.

    python3 -I paint_autobahn.py <outdir> [signs] [phone] [house] [church]

signs   autobahn_signs.webp (2048 x 2048) + autobahn_signs.json: the road signs as one atlas, shelf-packed. The JSON maps
        each sign to its pixel rectangle (x, y, w, h; y down) and its size in metres (w_m, h_m). The game reads both:
        public/textures/autobahn_signs.webp and src/game/render/autobahnSigns.json (copy them there after a change).
phone   notruf.png (512 x 512) for emergency_phone.py: the front plate (phone pictogram, "NOTRUF", arrow) and a steel patch
house   house_facade.png + house_emit.png (1024 x 1024) for village_house*.py: 4 x 4 facade tiles (1 tile = a 2.5 x 2.8 m
        bay): row 0 plaster with a lit / dark / shuttered window, row 1 the same on half-timbering, row 2 doors,
        row 3 plain plaster / plain half-timbering / roof tiles / dark wood. The emit image is black except lit glass.
church  church.png + church_emit.png (512 x 512): clock face (0..256 x 0..256), arched window lit (256.., 0..) and dark
        (256.., 256..), plaster (0.., 256..)
"""
import json
import math
import os
import random
import sys

from PIL import Image, ImageDraw, ImageFont

FONT_B = '/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc'
FONT_M = '/usr/share/fonts/opentype/noto/NotoSansCJK-Medium.ttc'

BLUE = (14, 82, 148)
WHITE = (244, 245, 240)
BLACK = (22, 22, 24)
RED = (200, 24, 30)
GREY = (150, 154, 156)
PX = 100  # pixels per metre on the boards


def font(size, medium=False):
    return ImageFont.truetype(FONT_M if medium else FONT_B, max(1, int(round(size))), index=0)


class SD:
    """ImageDraw in board units (PX per metre): every coordinate, width and font size is scaled by k"""

    def __init__(self, img, k):
        self.d, self.k = ImageDraw.Draw(img), k

    def _p(self, xy):
        k = self.k
        if xy and isinstance(xy[0], (tuple, list)):
            return [(x * k, y * k) for x, y in xy]
        return [v * k for v in xy]

    def rectangle(self, xy, **kw):
        self.d.rectangle(self._p(xy), **self._w(kw))

    def rounded_rectangle(self, xy, radius=0, **kw):
        self.d.rounded_rectangle(self._p(xy), radius=radius * self.k, **self._w(kw))

    def ellipse(self, xy, **kw):
        self.d.ellipse(self._p(xy), **self._w(kw))

    def polygon(self, xy, **kw):
        self.d.polygon(self._p(xy), **self._w(kw))

    def line(self, xy, **kw):
        self.d.line(self._p(xy), **self._w(kw))

    def text(self, xy, s, font=None, **kw):
        self.d.text((xy[0] * self.k, xy[1] * self.k), s, font=ImageFont.truetype(font.path, max(1, int(round(font.size * self.k))), index=0), **kw)

    def textlength(self, s, font=None):
        return self.d.textlength(s, font=font)

    def _w(self, kw):
        if 'width' in kw:
            kw = dict(kw, width=max(1, int(round(kw['width'] * self.k))))
        return kw


def text(d, xy, s, size, fill=WHITE, anchor='lm', medium=False):
    d.text(xy, s, font=font(size, medium), fill=fill, anchor=anchor)


# ------------------------------------------------------------------------------------------------ pictograms

def arrow(d, cx, cy, length, width, angle, fill=WHITE):
    """a straight arrow centred at (cx, cy) pointing at `angle` (degrees, 0 = up, 90 = right)"""
    a = math.radians(angle)
    ux, uy = math.sin(a), -math.cos(a)      # along
    vx, vy = -uy, ux                       # across
    head_l, head_w = width * 1.9, width * 2.6
    tail = length / 2
    pts = [(-width / 2, -tail), (-width / 2, tail - head_l), (-head_w / 2, tail - head_l), (0, tail),
           (head_w / 2, tail - head_l), (width / 2, tail - head_l), (width / 2, -tail)]
    d.polygon([(cx + ux * y + vx * x, cy + uy * y + vy * x) for x, y in pts], fill=fill)


def exit_symbol(d, x, y, h, fill=WHITE, bg=BLUE):
    """the German junction pictogram: a carriageway with a slip road branching off to the right; (x, y) top left"""
    w = h * 0.62
    s = h / 100
    d.rectangle([x + 8 * s, y, x + 30 * s, y + h], fill=fill)            # main carriageway
    # slip road: leaves the main bar low down and bends up and to the right
    pts = []
    for k in range(13):
        t = k / 12
        px = x + 30 * s + (w - 30 * s - 10 * s) * (1 - math.cos(t * math.pi / 2))
        py = y + h * 0.78 - h * 0.74 * math.sin(t * math.pi / 2)
        pts.append((px, py))
    for (a, b) in zip(pts, pts[1:]):
        d.line([a, b], fill=fill, width=int(20 * s))
    d.ellipse([pts[-1][0] - 10 * s, pts[-1][1] - 10 * s, pts[-1][0] + 10 * s, pts[-1][1] + 10 * s], fill=fill)
    return w


def a_shield(d, x, y, h, label='A 77'):
    """motorway number: white lettering in a white-bordered blue box; (x, y) top left; returns its width"""
    f = font(h * 0.72)
    tw = d.textlength(label, font=f)
    w = tw + h * 0.6
    d.rounded_rectangle([x, y, x + w, y + h], radius=h * 0.16, fill=BLUE, outline=WHITE, width=max(3, int(h * 0.07)))
    d.text((x + w / 2, y + h / 2 + h * 0.02), label, font=f, fill=WHITE, anchor='mm')
    return w


def exit_number(d, x, y, h, n='17'):
    """junction number: the pictogram and the number; returns the width used"""
    w = exit_symbol(d, x, y, h)
    f = font(h * 0.8)
    d.text((x + w + h * 0.18, y + h / 2), n, font=f, fill=WHITE, anchor='lm')
    return w + h * 0.18 + d.textlength(n, font=f)


K = 1.0  # pixel density of the sign being painted, relative to PX


def board(w_m, h_m, colour=BLUE, border=True, radius=0.12):
    w, h = w_m * PX, h_m * PX
    img = Image.new('RGB', (int(round(w * K)), int(round(h * K))), (90, 94, 96))
    d = SD(img, K)
    d.rounded_rectangle([0, 0, w - 1, h - 1], radius=int(radius * PX), fill=colour)
    if border:
        b = 0.05 * PX
        d.rounded_rectangle([b, b, w - 1 - b, h - 1 - b], radius=int((radius - 0.04) * PX), outline=WHITE, width=int(0.045 * PX))
    return img, d


# ------------------------------------------------------------------------------------------------ the signs

def sign_exit_announce(dist):
    """Ankündigungstafel: junction number, its name, the distance"""
    img, d = board(4.0, 2.6)
    exit_number(d, 30, 26, 66)
    text(d, (30, 140), 'Nebelfurt', 64)
    text(d, (370, 222), dist, 48, anchor='rm')
    return img


def sign_gantry_main(arrows, w_m, dests, lanes_down=False):
    """over the through lanes: motorway number, destinations, one arrow per lane (up = ahead, down = this lane)"""
    img, d = board(w_m, 3.0)
    w = w_m * PX
    sw = a_shield(d, 30, 26, 52)
    for k, s in enumerate(dests):
        text(d, (30 + sw + 26, 52 + k * 64), s, 56)
    for k in range(arrows):
        cx = w * (k + 0.5) / arrows if lanes_down else w - 90 - k * 120
        arrow(d, cx, 238 if lanes_down else 150, 80 if lanes_down else 110, 16, 180 if lanes_down else 0)
    return img


def sign_gantry_exit(dist=None, diagonal=False):
    """over the exit lane: junction number, its destinations, distance or the diagonal exit arrow"""
    img, d = board(4.2, 3.0)
    exit_number(d, 30, 24, 60)
    text(d, (30, 132), 'Nebelfurt', 54)
    text(d, (30, 190), 'Eulingen', 54)
    if dist:
        text(d, (390, 262), dist, 42, anchor='rm')
    if diagonal:
        arrow(d, 356, 240, 92, 16, 135)
    return img


def sign_ausfahrt():
    """the exit sign at the gore"""
    img, d = board(3.2, 1.1)
    text(d, (24, 55), 'Ausfahrt', 56)
    arrow(d, 272, 55, 70, 13, 45)
    return img


def sign_distance(rows):
    """Entfernungstafel: destinations and kilometres"""
    img, d = board(4.4, 0.74 + 0.5 * len(rows))
    a_shield(d, 26, 18, 36)
    for k, (name, km) in enumerate(rows):
        y = 94 + k * 50
        text(d, (26, y), name, 42)
        text(d, (414, y), f'{km} km', 42, anchor='rm')
    return img


def sign_autobahn():
    """Zeichen 330.1: the motorway pictogram (a bridge over a dual carriageway)"""
    img, d = board(1.2, 1.2, border=True, radius=0.1)
    w = 120
    cx = w / 2
    # the bridge deck and its parapet
    d.rectangle([14, 30, w - 14, 40], fill=WHITE)
    d.rectangle([14, 46, w - 14, 52], fill=WHITE)
    # two carriageways converging to the horizon under the bridge
    for side in (-1, 1):
        d.polygon([(cx + side * 6, 58), (cx + side * 16, 58), (cx + side * 46, 104), (cx + side * 26, 104)], fill=WHITE)
    # abutments
    d.polygon([(14, 52), (30, 52), (14, 74)], fill=WHITE)
    d.polygon([(w - 14, 52), (w - 30, 52), (w - 14, 74)], fill=WHITE)
    return img


def disc(paint):
    """a round sign, painted 4x and filtered down; transparent outside the disc (the game alpha-tests it)"""
    S = int(round(100 * K)) * 4
    big = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    paint(big, S)
    return big.resize((S // 4, S // 4), Image.LANCZOS)


def sign_derestrict():
    """Zeichen 282: end of every limit (a white disc with five black diagonal stripes)"""
    def paint(big, S):
        d = ImageDraw.Draw(big)
        d.ellipse([4, 4, S - 4, S - 4], fill=(120, 124, 126, 255))
        e = S * 0.035
        d.ellipse([e, e, S - e, S - e], fill=WHITE + (255,))
        mask = Image.new('L', (S, S), 0)
        ImageDraw.Draw(mask).ellipse([e, e, S - e, S - e], fill=255)
        stripes = Image.new('RGBA', (S, S), (0, 0, 0, 0))
        sd = ImageDraw.Draw(stripes)
        for k in range(5):
            off = (k - 2) * S * 0.065
            sd.line([(S * 0.86 + off, S * 0.14 + off), (S * 0.14 + off, S * 0.86 + off)], fill=BLACK + (255,), width=int(S * 0.025))
        big.alpha_composite(Image.composite(stripes, Image.new('RGBA', (S, S), (0, 0, 0, 0)), mask))
    return disc(paint)


def sign_limit(n):
    """Zeichen 274: speed limit"""
    def paint(big, S):
        d = ImageDraw.Draw(big)
        d.ellipse([4, 4, S - 4, S - 4], fill=RED + (255,))
        d.ellipse([S * 0.13, S * 0.13, S * 0.87, S * 0.87], fill=WHITE + (255,))
        d.text((S / 2, S / 2 + S * 0.015), str(n), font=font(S * (0.375 if n < 100 else 0.32)), fill=BLACK, anchor='mm')
    return disc(paint)


def sign_bridge(name):
    img, d = board(4.2, 0.6, radius=0.06)
    text(d, (210, 30), name, 32, anchor='mm')
    return img


def sign_banner(label):
    """start / goal boards on the start and finish gantries: dark with a chequered band"""
    w, h = 1000, 260
    img = Image.new('RGB', (int(w * K), int(h * K)), (16, 20, 24))
    d = SD(img, K)
    sq = 26
    for row in range(2):
        for k in range(w // sq + 1):
            d.rectangle([k * sq, h - (row + 1) * sq - 8, k * sq + sq, h - row * sq - 8], fill=WHITE if (k + row) % 2 else BLACK)
    text(d, (w / 2, 100), label, 140, anchor='mm')
    return img


def sign_back():
    """the galvanised back of every board (and its edges)"""
    img = Image.new('RGB', (64, 64), (128, 132, 134))
    d = ImageDraw.Draw(img)
    for y in range(0, 64, 8):
        d.line([(0, y), (63, y)], fill=(112, 116, 118), width=2)
    return img


# name: (painter, size in metres or None = from the painter, pixel density relative to PX)
SIGNS = {
    'exit_1000': (lambda: sign_exit_announce('1000 m'), (4.0, 2.6), 1.3),
    'exit_2000': (lambda: sign_exit_announce('2000 m'), (4.0, 2.6), 1.3),
    'g1_main': (lambda: sign_gantry_main(2, 7.4, ['Sternau', 'Mondbach', 'Wolfshafen']), (7.4, 3.0), 1.3),
    'g1_exit': (lambda: sign_gantry_exit(dist='500 m'), (4.2, 3.0), 1.3),
    'g2_main': (lambda: sign_gantry_main(3, 10.6, ['Sternau', 'Mondbach'], lanes_down=True), (10.6, 3.0), 1.3),
    'g2_exit': (lambda: sign_gantry_exit(diagonal=True), (4.2, 3.0), 1.3),
    'ausfahrt': (sign_ausfahrt, (3.2, 1.1), 1.5),
    'dist_a': (lambda: sign_distance([('Dämmerfeld', 9), ('Nebelfurt', 23), ('Sternau', 41), ('Wolfshafen', 112)]), None, 1.4),
    'dist_b': (lambda: sign_distance([('Sternau', 14), ('Mondbach', 32), ('Wolfshafen', 87)]), None, 1.4),
    'autobahn': (sign_autobahn, (1.2, 1.2), 1.6),
    'derestrict': (sign_derestrict, (0.9, 0.9), 1.6),
    'limit120': (lambda: sign_limit(120), (0.9, 0.9), 1.6),
    'bridge': (lambda: sign_bridge('Talbrücke Schattental'), (4.2, 0.6), 1.5),
    'start': (lambda: sign_banner('START'), (10.0, 2.6), 0.8),
    'goal': (lambda: sign_banner('GOAL'), (10.0, 2.6), 0.8),
    'back': (sign_back, (1.0, 1.0), 1.0),
}


def paint_signs(out):
    global K
    W = 2048
    atlas = Image.new('RGBA', (W, W), (128, 132, 134, 255))
    rects = {}
    imgs = []
    for name, (fn, size, k) in SIGNS.items():
        K = k
        img = fn().convert('RGBA')
        if size is None:
            size = (img.width / (PX * k), img.height / (PX * k))
        imgs.append((name, img, size))
    K = 1.0
    # shelf packing, tallest first, 6 px gutters (edge pixels repeated into them against bleeding)
    imgs.sort(key=lambda t: -t[1].height)
    x = y = 0
    shelf = 0
    G = 6
    for name, img, size in imgs:
        if x + img.width + 2 * G > W:
            x, y = 0, y + shelf + G
            shelf = 0
        if y + img.height + 2 * G > W:
            raise SystemExit('atlas full')
        ex = img.resize((img.width + 2 * G, img.height + 2 * G), Image.NEAREST)
        ex.paste(img, (G, G))
        atlas.paste(ex, (x, y))
        rects[name] = dict(x=x + G, y=y + G, w=img.width, h=img.height, w_m=round(size[0], 3), h_m=round(size[1], 3))
        x += img.width + 2 * G + G
        shelf = max(shelf, img.height + 2 * G)
    print('atlas used up to y =', y + shelf)
    atlas.save(os.path.join(out, 'autobahn_signs.webp'), 'WEBP', quality=90, method=6)
    with open(os.path.join(out, 'autobahn_signs.json'), 'w') as f:
        json.dump({'size': W, 'signs': rects}, f, indent=1, sort_keys=True)
        f.write('\n')


# ------------------------------------------------------------------------------------------------ emergency phone

def paint_phone(out):
    """front plate 0..512 x 0..400 (0.26 x 0.2 m), lower panel 0..512 x 400..512"""
    W = 512
    img = Image.new('RGB', (W, W), (232, 108, 26))
    d = ImageDraw.Draw(img)
    # the pictogram plate: white handset on black
    d.rounded_rectangle([40, 30, 472, 300], radius=26, fill=BLACK)
    hs = [(150, 230), (130, 190), (150, 120), (205, 90), (240, 110), (215, 150), (190, 150), (180, 185), (200, 215), (230, 210),
          (255, 175), (300, 200), (285, 255), (240, 270), (180, 260)]
    # a handset: two rounded ends joined by a curved grip
    d.line([(160, 110), (130, 170), (150, 240), (200, 270)], fill=WHITE, width=34, joint='curve')
    d.ellipse([140, 70, 210, 130], fill=WHITE)
    d.ellipse([190, 240, 260, 300 - 4], fill=WHITE)
    del hs
    text(d, (345, 120), 'SOS', 70, anchor='mm')
    arrow(d, 345, 220, 90, 20, 90)
    # NOTRUF plate
    d.rectangle([40, 320, 472, 392], fill=WHITE)
    text(d, (256, 354), 'NOTRUF', 60, fill=BLACK, anchor='mm')
    # lower part: dark grey flap with a hinge line and a pull
    d.rectangle([0, 404, W, W], fill=(62, 64, 66))
    d.line([(0, 410), (W, 410)], fill=(30, 30, 32), width=4)
    d.rounded_rectangle([200, 440, 312, 470], radius=10, fill=(150, 152, 150))
    img.save(os.path.join(out, 'notruf.png'))


# ------------------------------------------------------------------------------------------------ village house

def paint_house(out):
    W = 1024
    T = W // 4
    col = Image.new('RGB', (W, W), (0, 0, 0))
    emit = Image.new('RGB', (W, W), (0, 0, 0))
    dc, de = ImageDraw.Draw(col), ImageDraw.Draw(emit)
    rnd = random.Random(5)
    plaster = (226, 220, 206)
    beam = (72, 50, 36)

    def plaster_fill(x, y):
        dc.rectangle([x, y, x + T - 1, y + T - 1], fill=plaster)
        for _ in range(500):
            px, py = x + rnd.randrange(T), y + rnd.randrange(T)
            v = rnd.randrange(-14, 10)
            dc.point((px, py), fill=tuple(max(0, min(255, c + v)) for c in plaster))

    def timber(x, y):
        plaster_fill(x, y)
        b = 14
        dc.rectangle([x, y, x + T - 1, y + b], fill=beam)
        dc.rectangle([x, y + T - b, x + T - 1, y + T - 1], fill=beam)
        dc.rectangle([x, y, x + b, y + T - 1], fill=beam)
        dc.rectangle([x + T - b, y, x + T - 1, y + T - 1], fill=beam)
        dc.line([(x, y + T), (x + T * 0.3, y + T * 0.45)], fill=beam, width=b)
        dc.line([(x + T, y + T), (x + T * 0.7, y + T * 0.45)], fill=beam, width=b)

    def window(x, y, state, cross=True):
        # window of 1.1 x 1.3 m in a 2.5 x 2.8 m bay
        wx0, wx1 = x + T * 0.28, x + T * 0.72
        wy0, wy1 = y + T * 0.24, y + T * 0.70
        dc.rectangle([wx0 - 8, wy0 - 8, wx1 + 8, wy1 + 12], fill=(200, 196, 186))
        if state == 'lit':
            warm = rnd.choice([(255, 196, 120), (255, 214, 150), (250, 226, 180)])
            dc.rectangle([wx0, wy0, wx1, wy1], fill=warm)
            de.rectangle([wx0, wy0, wx1, wy1], fill=warm)
            # curtains
            dc.rectangle([wx0, wy0, wx0 + 16, wy1], fill=(220, 150, 90))
            de.rectangle([wx0, wy0, wx0 + 16, wy1], fill=(150, 80, 40))
        elif state == 'dark':
            dc.rectangle([wx0, wy0, wx1, wy1], fill=(34, 40, 48))
        else:  # closed shutters
            dc.rectangle([wx0, wy0, wx1, wy1], fill=(70, 86, 64))
            for k in range(int(wy0), int(wy1), 9):
                dc.line([(wx0, k), (wx1, k)], fill=(52, 64, 48), width=2)
        if cross and state != 'shut':
            mx = (wx0 + wx1) / 2
            dc.line([(mx, wy0), (mx, wy1)], fill=(236, 234, 228), width=6)
            dc.line([(wx0, wy0 + (wy1 - wy0) * 0.35), (wx1, wy0 + (wy1 - wy0) * 0.35)], fill=(236, 234, 228), width=6)

    # rows 0 and 1: plaster / half-timbering with lit, dark, shuttered, lit windows
    for r, base in ((0, plaster_fill), (1, timber)):
        for c, state in enumerate(('lit', 'dark', 'shut', 'lit')):
            base(c * T, r * T)
            window(c * T, r * T, state)
    # row 2: front doors (lit fanlight / dark), a garage door, a lit stairwell strip
    for c in range(4):
        x, y = c * T, 2 * T
        plaster_fill(x, y)
        if c < 2:
            dc.rectangle([x + T * 0.32, y + T * 0.3, x + T * 0.68, y + T - 1], fill=(92, 58, 36))
            dc.rectangle([x + T * 0.36, y + T * 0.34, x + T * 0.64, y + T * 0.44], fill=(255, 210, 140) if c == 0 else (40, 44, 50))
            if c == 0:
                de.rectangle([x + T * 0.36, y + T * 0.34, x + T * 0.64, y + T * 0.44], fill=(255, 200, 120))
                # porch lamp
                dc.ellipse([x + T * 0.76, y + T * 0.34, x + T * 0.84, y + T * 0.44], fill=(255, 230, 170))
                de.ellipse([x + T * 0.76, y + T * 0.34, x + T * 0.84, y + T * 0.44], fill=(255, 220, 150))
        elif c == 2:
            dc.rectangle([x + T * 0.1, y + T * 0.3, x + T * 0.9, y + T - 1], fill=(120, 116, 108))
            for k in range(int(y + T * 0.3), y + T, 12):
                dc.line([(x + T * 0.1, k), (x + T * 0.9, k)], fill=(96, 92, 86), width=3)
        else:
            dc.rectangle([x + T * 0.4, y + T * 0.1, x + T * 0.6, y + T * 0.9], fill=(255, 236, 196))
            de.rectangle([x + T * 0.4, y + T * 0.1, x + T * 0.6, y + T * 0.9], fill=(230, 210, 170))
    # row 3: plain plaster, plain timbering, roof tiles, dark wood
    plaster_fill(0, 3 * T)
    timber(T, 3 * T)
    x, y = 2 * T, 3 * T
    dc.rectangle([x, y, x + T - 1, y + T - 1], fill=(120, 52, 38))
    for k in range(0, T, 16):
        dc.line([(x, y + k), (x + T, y + k)], fill=(86, 36, 28), width=4)
        for j in range(0, T, 22):
            o = 11 if (k // 16) % 2 else 0
            dc.line([(x + j + o, y + k), (x + j + o, y + k + 14)], fill=(98, 42, 32), width=2)
    x = 3 * T
    dc.rectangle([x, y, x + T - 1, y + T - 1], fill=(70, 48, 34))
    for k in range(0, T, 20):
        dc.line([(x + k, y), (x + k, y + T)], fill=(52, 36, 26), width=3)
    col.save(os.path.join(out, 'house_facade.png'))
    emit.save(os.path.join(out, 'house_emit.png'))


# ------------------------------------------------------------------------------------------------ church

def paint_church(out):
    W = 512
    col = Image.new('RGB', (W, W), (0, 0, 0))
    emit = Image.new('RGB', (W, W), (0, 0, 0))
    dc, de = ImageDraw.Draw(col), ImageDraw.Draw(emit)
    # clock face 0..256: lit white dial, black ticks and hands, gold rim
    dc.rectangle([0, 0, 255, 255], fill=(40, 34, 28))
    dc.ellipse([8, 8, 248, 248], fill=(196, 156, 70))
    dc.ellipse([20, 20, 236, 236], fill=(244, 240, 226))
    de.ellipse([20, 20, 236, 236], fill=(230, 222, 196))
    for k in range(12):
        a = k / 12 * 2 * math.pi
        r0, r1 = 88, 104
        dc.line([(128 + math.sin(a) * r0, 128 - math.cos(a) * r0), (128 + math.sin(a) * r1, 128 - math.cos(a) * r1)], fill=BLACK, width=8 if k % 3 == 0 else 4)
    for a, r, w in ((math.radians(312), 58, 9), (math.radians(60), 84, 6)):
        dc.line([(128, 128), (128 + math.sin(a) * r, 128 - math.cos(a) * r)], fill=BLACK, width=w)
        de.line([(128, 128), (128 + math.sin(a) * r, 128 - math.cos(a) * r)], fill=(0, 0, 0), width=w)
    # arched windows: lit (256.., 0..256) and dark (256.., 256..)
    for (y0, lit) in ((0, True), (256, False)):
        x0 = 256
        dc.rectangle([x0, y0, x0 + 255, y0 + 255], fill=(228, 222, 208))
        glass = (255, 200, 120) if lit else (36, 40, 50)
        dc.rectangle([x0 + 60, y0 + 90, x0 + 196, y0 + 246], fill=glass)
        dc.ellipse([x0 + 60, y0 + 22, x0 + 196, y0 + 158], fill=glass)
        if lit:
            de.rectangle([x0 + 60, y0 + 90, x0 + 196, y0 + 246], fill=(220, 160, 90))
            de.ellipse([x0 + 60, y0 + 22, x0 + 196, y0 + 158], fill=(220, 160, 90))
        for k in range(1, 4):
            dc.line([(x0 + 60 + k * 34, y0 + 30), (x0 + 60 + k * 34, y0 + 246)], fill=(90, 80, 70), width=3)
        for k in range(1, 6):
            dc.line([(x0 + 60, y0 + 30 + k * 36), (x0 + 196, y0 + 30 + k * 36)], fill=(90, 80, 70), width=3)
    # plaster (0.., 256..)
    rnd = random.Random(3)
    dc.rectangle([0, 256, 255, 511], fill=(232, 228, 216))
    for _ in range(3000):
        px, py = rnd.randrange(256), 256 + rnd.randrange(256)
        v = rnd.randrange(-12, 8)
        dc.point((px, py), fill=(232 + v, 228 + v, 216 + v))
    col.save(os.path.join(out, 'church.png'))
    emit.save(os.path.join(out, 'church_emit.png'))


if __name__ == '__main__':
    out = sys.argv[1]
    os.makedirs(out, exist_ok=True)
    jobs = sys.argv[2:] or ['signs', 'phone', 'house', 'church']
    for j in jobs:
        {'signs': paint_signs, 'phone': paint_phone, 'house': paint_house, 'church': paint_church}[j](out)
