#!/usr/bin/env python3
"""Signage textures for the Keikyu New 1000 (1st batch) Blender model.

Host python3 + PIL only (no numpy).  Deterministic: no random numbers, same bytes every run.
    python3 frontend/tools/blender/keikyu1000_textures.py [outdir]
Default output: frontend/tools/blender/textures/keikyu1000/

Physical mapping (all images: u to the right, v down, pixel density given per image):

  led_runno.png / led_runno_off.png   0.350 x 0.205 m   1600 px/m   560 x 328    3-colour LED, orange "13H"
  led_type.png  / led_type_off.png    0.290 x 0.205 m   1600 px/m   464 x 328    full-colour LED, 快特 white on green
  led_dest.png  / led_dest_off.png    0.670 x 0.210 m   1600 px/m  1072 x 336    white LED "京急本線" (the line, not a station)
  led_side.png  / led_side_off.png    0.300 x 0.135 m   1600 px/m   480 x 216    side unit "快特 | 京急本線"
  cab_band_001.png, cab_band_008.png  2.900 x 0.400 m   1500 px/m  4350 x 600    RGBA cream band, u: x -1.45..+1.45 m,
                                      v: y 2.06 (top) .. 1.66 (bottom) m   (x = car's left = viewer's right)
  lamp_unit_L.png / lamp_unit_R.png   0.450 x 0.170 m   ~1138 px/m 512 x 194    waist lamp unit (base colour)
  lamp_unit_emit_L.png / _R.png       same, emission (express lamp lit white, tail lamp dark)

LED panels: dot matrices (dark panel, unlit dots visible, lit dots with a glow); one RGB image serves as base colour and
as emission.  The *_off images have every dot dark (cars' rear ends, or a display that is switched off).

Cab band geometry: measured on the CC0 photo "2次車のワイパーカバー.png" (1 px = 1 mm in the digits' bounding box, levelled by
1.0 degree): the four slit bands of every digit, the zero outline fitted (superellipse, shear 0.45, counter) and the corner
points of the "1" read off.  The photo's pixels are not used; shapes are rebuilt from numbers below.  The 1st batch ("1次車")
has the same outlines, the flag of the "1" is black there.
Fonts: Noto Sans CJK JP (index 0 of the .ttc; SIL OFL 1.1) Medium for the LED characters.  No other font is used: the
cab-front numbers 001/008 are drawn as geometry (slanted rings and a slash), as on the real train.
"""
import math
import os
import sys

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, 'textures', 'keikyu1000')

FONT_CJK = '/usr/share/fonts/opentype/noto/NotoSansCJK-Medium.ttc'  # index 0 = Noto Sans CJK JP

# the displays show the line, not a station (the owner's choice for every train)
LINE, LINE_EN = '京急本線', 'Keikyu Main Line'

CREAM = (239, 233, 216)
SLIT = (12, 12, 14)

# ----------------------------------------------------------------------------------------------------------------------
# LED dot matrices
# ----------------------------------------------------------------------------------------------------------------------
PPM_LED = 1600
PANEL = (7, 8, 10)
UNLIT = (19, 20, 24)

ORANGE = (255, 112, 12)
WHITE = (236, 242, 255)
GREEN = (0, 168, 78)
RED = (214, 22, 30)
BLUE = (30, 60, 220)


def _font(size):
    return ImageFont.truetype(FONT_CJK, size, index=0)


def _glyph_em(ch, em_w, em_h, S):
    """Coverage image (L, S px per dot) of one CJK char stretched from its em square to em_w x em_h dots."""
    F = 256
    f = _font(F)
    im = Image.new('L', (F, F), 0)
    d = ImageDraw.Draw(im)
    bb = d.textbbox((0, 0), ch, font=f)
    d.text(((F - (bb[2] - bb[0])) / 2 - bb[0], (F - (bb[3] - bb[1])) / 2 - bb[1]), ch, font=f, fill=255)
    # tight crop of the ink, then stretched to the requested box (so 三 is as wide as 崎)
    ink = im.getbbox()
    im = im.crop(ink)
    return im.resize((max(1, round(em_w * S)), max(1, round(em_h * S))), Image.LANCZOS)


def _glyph_latin(ch, cap_h, xscale, S):
    F = 256
    f = _font(F)
    im = Image.new('L', (F * 2, F * 2), 0)
    d = ImageDraw.Draw(im)
    d.text((F // 2, F // 2), ch, font=f, fill=255)
    ink = im.getbbox()
    # digits and capitals share the cap height: normalise on "H"
    ref = Image.new('L', (F * 2, F * 2), 0)
    ImageDraw.Draw(ref).text((F // 2, F // 2), 'H', font=f, fill=255)
    rb = ref.getbbox()
    cap = rb[3] - rb[1]
    sc = cap_h * S / cap
    im = im.crop(ink)
    w = max(1, round(im.width * sc * xscale))
    h = max(1, round(im.height * sc))
    # baseline: bottom of the ink for non-descenders is the bottom of H
    return im.resize((w, h), Image.LANCZOS), (ink[3] - rb[3]) * sc


class Matrix:
    """A dot grid: cols x rows dots filling the display exactly; per-dot RGB."""

    def __init__(self, w_m, h_m, cols, rows):
        self.w_m, self.h_m, self.cols, self.rows = w_m, h_m, cols, rows
        self.S = 8
        self.layers = []  # (coverage L image at S px per dot, colour)
        self.dots = [[(0, 0, 0)] * cols for _ in range(rows)]

    def fill(self, colour, x0=0, y0=0, x1=None, y1=None):
        x1 = self.cols if x1 is None else x1
        y1 = self.rows if y1 is None else y1
        for j in range(y0, y1):
            for i in range(x0, x1):
                self.dots[j][i] = colour

    def _paste_cov(self, cov_img, x_m, y_m, colour):
        """Composite a coverage image placed with its top-left at (x_m, y_m) metres."""
        S = self.S
        cv = Image.new('L', (self.cols * S, self.rows * S), 0)
        px = x_m / self.w_m * self.cols * S
        py = y_m / self.h_m * self.rows * S
        cv.paste(cov_img, (round(px), round(py)))
        self.layers.append((cv, colour))

    def text_cjk(self, text, x_m, y_m, cw_m, ch_m, pitch_m, colour):
        dx = self.cols / self.w_m
        dy = self.rows / self.h_m
        for k, c in enumerate(text):
            g = _glyph_em(c, cw_m * dx, ch_m * dy, self.S)
            self._paste_cov(g, x_m + k * pitch_m, y_m, colour)

    def text_latin(self, text, x_m, base_m, cap_m, cw_m, pitch_m, colour):
        """Latin/digits on a common baseline (base_m = baseline y), cap height cap_m, char box width cw_m."""
        dx = self.cols / self.w_m
        dy = self.rows / self.h_m
        for k, c in enumerate(text):
            g, below = _glyph_latin(c, cap_m * dy, 1.0, self.S)
            xs = cw_m * dx * self.S / max(1, g.width)
            if c in '1':
                xs = min(xs, 1.0)
            w2 = max(1, round(g.width * min(xs, 1.35)))
            g = g.resize((w2, g.height), Image.LANCZOS)
            x0 = x_m + k * pitch_m + (cw_m - w2 / self.S / dx) / 2
            y0 = base_m - cap_m + (0 if c not in 'gjpqy' else 0)
            self._paste_cov(g, x0, y0 - 0, colour)

    def text_fit(self, text, x_m, y_m, w_m, h_m, colour, track=0.12):
        """Latin text (proportional, letter-spaced by `track` em) whose ink box is stretched to w_m x h_m metres."""
        F = 200
        f = _font(F)
        im = Image.new('L', (F * len(text) * 2, F * 2), 0)
        d = ImageDraw.Draw(im)
        x = F // 2
        for c in text:
            d.text((x, F // 2), c, font=f, fill=255)
            x += d.textlength(c, font=f) + track * F
        im = im.crop(im.getbbox())
        dx = self.cols / self.w_m * self.S
        dy = self.rows / self.h_m * self.S
        im = im.resize((max(1, round(w_m * dx)), max(1, round(h_m * dy))), Image.LANCZOS)
        self._paste_cov(im, x_m, y_m, colour)

    def dots_from_layers(self):
        """Resolve layers into per-dot colours, with sharp levels (LED dots are on / dim / off)."""
        for cv, colour in self.layers:
            small = cv.resize((self.cols, self.rows), Image.BOX)
            sp = small.load()
            for j in range(self.rows):
                for i in range(self.cols):
                    c = sp[i, j] / 255.0
                    lvl = max(0.0, min(1.0, (c - 0.26) / 0.36))
                    if lvl > 0:
                        old = self.dots[j][i]
                        self.dots[j][i] = tuple(round(old[k] * (1 - lvl) + colour[k] * lvl) for k in range(3))

    def render(self, lit=True, ppm=PPM_LED):
        W = round(self.w_m * ppm)
        H = round(self.h_m * ppm)
        SS = 4
        pw, ph = W / self.cols, H / self.rows
        base = Image.new('RGB', (W * SS, H * SS), PANEL)
        d = ImageDraw.Draw(base)
        lit_layer = Image.new('RGB', (W * SS, H * SS), (0, 0, 0))
        dl = ImageDraw.Draw(lit_layer)
        r = 0.40 * min(pw, ph) * SS
        for j in range(self.rows):
            cy = (j + 0.5) * ph * SS
            for i in range(self.cols):
                cx = (i + 0.5) * pw * SS
                d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=UNLIT)
                col = self.dots[j][i]
                if lit and max(col) > 0:
                    dl.ellipse((cx - r, cy - r, cx + r, cy + r), fill=col)
        img = ImageChops.add(base, lit_layer) if lit else base
        img = img.resize((W, H), Image.LANCZOS)
        if lit:
            glow = lit_layer.resize((W, H), Image.LANCZOS).filter(ImageFilter.GaussianBlur(0.75 * min(pw, ph)))
            glow = glow.point(lambda v: min(255, int(v * 0.22)))
            img = ImageChops.add(img, glow)
        return img


def led_runno(text='13H'):
    # 0.35 x 0.205 m, pitch 8.54 mm: 41 x 24 dots
    m = Matrix(0.35, 0.205, 41, 24)
    # characters 0.125 m tall (14.6 dots), pitch 0.065 (head-on photo 02: "15D" 0.19 m wide, 0.125 m tall)
    n = len(text)
    pitch = 0.066
    total = (n - 1) * pitch + 0.058
    x0 = (0.35 - total) / 2
    m.text_latin(text, x0, 0.205 / 2 + 0.0625, 0.125, 0.058, pitch, ORANGE)
    m.dots_from_layers()
    return m


def led_type(name='快特', field=GREEN, fg=WHITE):
    # 0.29 x 0.205 m: 34 x 24 dots, whole panel is the coloured field; two white characters 0.115 high
    m = Matrix(0.29, 0.205, 34, 24)
    m.fill(field)
    cw, pitch = 0.118, 0.128
    total = pitch + cw
    m.text_cjk(name, (0.29 - total) / 2, (0.205 - 0.125) / 2, cw, 0.125, pitch, fg)
    m.dots_from_layers()
    return m


def led_dest(name=LINE):
    # 0.67 x 0.21 m: 100 x 32 dots (pitch ~6.7 mm); chars 0.135 wide x 0.108 high at pitch 0.22 (measured on photo 08)
    m = Matrix(0.67, 0.21, 100, 32)
    cw, ch = 0.145, 0.15
    n = len(name)
    pitch = 0.22 if n == 3 else 0.17
    total = (n - 1) * pitch + cw
    m.text_cjk(name, (0.67 - total) / 2, (0.21 - ch) / 2, cw, ch, pitch, WHITE)
    m.dots_from_layers()
    return m


def led_side(type_name='快特', dest=LINE):
    # 0.30 x 0.135 m: 60 x 27 dots (pitch 5 mm).  Green type field on the left third, white destination on black
    # (four characters set narrower than three).
    m = Matrix(0.30, 0.135, 60, 27)
    fw = 20  # dots of the type field
    m.fill(GREEN, 0, 0, fw, 27)
    m.text_cjk(type_name, 0.0035, 0.0165, 0.044, 0.1, 0.048, WHITE)
    if len(dest) <= 3:
        m.text_cjk(dest, 0.108, 0.0175, 0.058, 0.1, 0.0635, WHITE)
    else:
        m.text_cjk(dest, 0.108, 0.0175, 0.044, 0.1, 0.046, WHITE)
    m.dots_from_layers()
    return m


def led_side_wide():
    """Side destination unit, 0.88 x 0.14 m, 352 x 56 dots (2.5 mm), full-colour LED, layout read off the close-up
    KHK1001HND.jpg (aspect 6.4:1): green type block with 快特 + "Limited Exp." at the left, a dark gap, then a white
    destination field with dark text: the line, 京急本線 + "Keikyu Main Line" (the photo's 羽田空港 + "Haneda Airport")."""
    m = Matrix(0.88, 0.14, 352, 56)
    DARK = (0, 0, 0)
    m.fill(GREEN, round(0.022 / 0.88 * 352), round(0.0196 / 0.14 * 56), round(0.250 / 0.88 * 352),
           round(0.130 / 0.14 * 56))
    m.fill(WHITE, round(0.333 / 0.88 * 352), round(0.0157 / 0.14 * 56), round(0.852 / 0.88 * 352),
           round(0.130 / 0.14 * 56))
    m.text_cjk('快特', 0.0413, 0.0347, 0.0715, 0.0706, 0.121, WHITE)
    m.text_fit('Limited Exp.', 0.0468, 0.109, 0.173, 0.0205, WHITE)
    m.text_cjk(LINE, 0.3825, 0.0325, 0.074, 0.068, 0.110, DARK)
    m.text_fit(LINE_EN, 0.425, 0.1035, 0.32, 0.0215, DARK)
    m.dots_from_layers()
    return m


# ----------------------------------------------------------------------------------------------------------------------
# Cab front band: cream, "001"/"008" and the "1000" slits
# ----------------------------------------------------------------------------------------------------------------------
PPM_BAND = 1500
BAND_X = (-1.45, 1.45)
BAND_Y = (1.66, 2.06)
SSB = 3

# The "1000" in the levelled photo frame (pixels).  Bands (y ranges) cut every digit into four slits.
SLIT_BANDS = [(175, 218), (250, 294), (326, 369), (401, 452)]
ZERO = dict(a=108.8, b=137.0, n=2.45, sh=0.45, cw=31.3, ch=116.7, cn=2.5, cy=313.0, cxs=(563.9, 829.9, 1098.9))
# "1": four pieces, as measured (photo frame before levelling; levelled below).  b2 is the flag + stem.
ONE_RAW = [
    [(382, 170), (452, 170), (431, 211), (344, 211)],
    [(306, 244), (420, 246), (402, 286), (334, 286), (342, 264), (290, 262)],
    [(318, 319), (386, 319), (367, 361), (299, 361)],
    [(284, 392), (352, 392), (334, 435), (266, 435)],
]
LEVEL_DEG = 1.0
LEVEL_C = (740.0, 310.0)


def _level(p):
    th = math.radians(LEVEL_DEG)
    dx, dy = p[0] - LEVEL_C[0], p[1] - LEVEL_C[1]
    return (LEVEL_C[0] + dx * math.cos(th) + dy * math.sin(th), LEVEL_C[1] - dx * math.sin(th) + dy * math.cos(th))


def _superellipse(cx, cy, a, b, n, sh, N=240):
    pts = []
    for i in range(N):
        t = 2 * math.pi * i / N
        c, s = math.cos(t), math.sin(t)
        x = a * math.copysign(abs(c) ** (2 / n), c)
        y = b * math.copysign(abs(s) ** (2 / n), s)
        pts.append((cx + x - sh * y, cy + y))  # image y is down: the top (y < 0) leans to the right
    return pts


def _thousand_shapes():
    """Returns (zero_outer_polys, zero_counter_polys, one_polys) in photo pixels."""
    z = ZERO
    outer = [_superellipse(cx, z['cy'], z['a'], z['b'], z['n'], z['sh']) for cx in z['cxs']]
    inner = [_superellipse(cx, z['cy'], z['cw'], z['ch'], z['cn'], z['sh']) for cx in z['cxs']]
    one = [[_level(p) for p in poly] for poly in ONE_RAW]
    return outer, inner, one


def _band_mask_shape(S):
    W = round((BAND_X[1] - BAND_X[0]) * PPM_BAND)
    H = round((BAND_Y[1] - BAND_Y[0]) * PPM_BAND)
    m = Image.new('L', (W * S, H * S), 0)
    d = ImageDraw.Draw(m)
    d.rounded_rectangle((0, 0, W * S - 1, H * S - 1), radius=int(0.10 * PPM_BAND * S), fill=255,
                        corners=(False, False, True, True))
    return m


class Mapper:
    """x metres / y metres <-> output pixels (supersampled) of the band image."""

    def __init__(self, S):
        self.S = S

    def px(self, x_m, y_m):
        return ((x_m - BAND_X[0]) * PPM_BAND * self.S, (BAND_Y[1] - y_m) * PPM_BAND * self.S)


def _draw_thousand(canvas_size, to_px, band_edges_y):
    outer, inner, one = _thousand_shapes()
    zero = Image.new('L', canvas_size, 0)
    d = ImageDraw.Draw(zero)
    for poly in outer:
        d.polygon([to_px(p) for p in poly], fill=255)
    for poly in inner:
        d.polygon([to_px(p) for p in poly], fill=0)
    bands = Image.new('L', canvas_size, 0)
    db = ImageDraw.Draw(bands)
    for (b0, b1) in SLIT_BANDS:
        db.rectangle((0, to_px((0, b0))[1], canvas_size[0], to_px((0, b1))[1]), fill=255)
    zero = ImageChops.multiply(zero, bands)
    d = ImageDraw.Draw(zero)
    for poly in one:
        d.polygon([to_px(p) for p in poly], fill=255)
    return zero


def _thousand_mask(S):
    """Mask (L, supersampled) of the black slits of "1000" mapped on x in [0.27, 1.235], y in [1.73, 2.01]."""
    # bounding box of the cut figure in photo pixels: draw it once at 4x in the photo frame
    k = 4
    probe = _draw_thousand((1400 * k, 600 * k), lambda p: (p[0] * k, p[1] * k), None)
    bb = probe.getbbox()
    x_min, y_min, x_max, y_max = bb[0] / k, bb[1] / k, bb[2] / k, bb[3] / k
    X0, X1, Y0, Y1 = 0.27, 1.235, 1.73, 2.01
    ax = (X1 - X0) / (x_max - x_min)
    ay = (Y1 - Y0) / (y_max - y_min)
    mp = Mapper(S)

    def to_px(p):
        return mp.px(X0 + (p[0] - x_min) * ax, Y1 - (p[1] - y_min) * ay)

    W = round((BAND_X[1] - BAND_X[0]) * PPM_BAND)
    H = round((BAND_Y[1] - BAND_Y[0]) * PPM_BAND)
    return _draw_thousand((W * S, H * S), to_px, None), (x_min, x_max, y_min, y_max, ax, ay)


# Cab-front numbers "001" / "008": heavy, nearly monoline slanted ovals.  Shapes fitted (IoU about 0.9) on the pixels of
# photo 02 (c02_meas.png, 253 px/m, digits 31.5 px tall) for the zeros and the "1", and on photo 10 for the "8" (two
# rings, scaled by 1/0.82 into photo-02 units).  Units below are photo-02 pixels; the ink box 176..265.5 x 485.5..517
# is mapped onto the brief's box x -0.80..-0.445, y 1.73..1.86 (so about 0.0040 m / px).  The "1" is a plain slash
# with flat cut ends (no flag), as on photos 02, 08, 09 and 10.
DIG_X0, DIG_X1, DIG_Y0, DIG_Y1 = 176.0, 265.5, 485.5, 517.0
Z_A, Z_B, Z_N, Z_TH = 11.405, 18.829, 2.228, -0.765          # outer: half axes (short, long), roundness, tilt (rad)
Z_AI, Z_BI, Z_NI, Z_IDX, Z_IDY = 6.428, 11.935, 1.954, -0.183, 0.081  # counter
Z_CY = (501.52, 501.88)
ONE_POLY = [(258.4, 485.5), (265.4, 485.5), (253.3, 517.0), (246.0, 517.0)]
# the "8": upper ring (smaller) and lower ring, as (dx, dy, a, b, tilt) relative to the centre of the pair; stroke
EIGHT = [(2.9, -5.9, 7.66, 12.1, -1.26), (-2.9, 6.0, 9.46, 14.8, -1.20)]
EIGHT_STROKE = 4.9
STROKE_NOTE = 'zero stroke: 5.0 px at the short axis (16 % of height), 6.9 px at the long axis (22 %)'


def _rot_se(cx, cy, a, b, n, th, N=160):
    pts = []
    for i in range(N):
        t = 2 * math.pi * i / N
        c, s = math.cos(t), math.sin(t)
        x = a * math.copysign(abs(c) ** (2 / n), c)
        y = b * math.copysign(abs(s) ** (2 / n), s)
        pts.append((cx + x * math.cos(th) + y * math.sin(th), cy - x * math.sin(th) + y * math.cos(th)))
    return pts


def _digit_geom(text):
    """The digits as polygons in metres (face frame of the band): list of (kind, outer polygons, hole polygons).
    The mask drawn into the textures and the exported outlines both come from here."""
    sy = 0.13 / (DIG_Y1 - DIG_Y0)
    if text == '001':
        glyphs = [('0', 192.25, Z_CY[0]), ('0', 227.5, Z_CY[1]), ('1', 0, 0)]
        x1 = DIG_X1
    else:  # '008': the 8 pushes the right edge out a little; squeeze the whole figure to the same box
        glyphs = [('0', 192.25, Z_CY[0]), ('0', 226.5, Z_CY[1]), ('8', 255.0, 501.25)]
        pts8 = [q for dx, dy, a, b, th in EIGHT for q in _rot_se(255.0 + dx, 501.25 + dy, a, b, Z_N, th)]
        x1 = 255.0 + (max(q[0] for q in pts8) - min(q[0] for q in pts8)) / 2
    sx = 0.355 / (x1 - DIG_X0)

    def mt(pts):
        return [(-0.80 + (q[0] - DIG_X0) * sx, 1.86 - (q[1] - DIG_Y0) * sy) for q in pts]

    out = []
    for kind, cx, cy in glyphs:
        if kind == '0':
            out.append((kind, [mt(_rot_se(cx, cy, Z_A, Z_B, Z_N, Z_TH))],
                        [mt(_rot_se(cx + Z_IDX, cy + Z_IDY, Z_AI, Z_BI, Z_NI, Z_TH))]))
        elif kind == '1':
            out.append((kind, [mt(ONE_POLY)], []))
        else:
            rings = [(cx + dx, cy + dy, a, b, th) for dx, dy, a, b, th in EIGHT]
            # recentre so the bounding box of the outer rings is centred on (cx, cy)
            pts = [q for (rx, ry, a, b, th) in rings for q in _rot_se(rx, ry, a, b, Z_N, th)]
            ox = cx - (min(q[0] for q in pts) + max(q[0] for q in pts)) / 2
            oy = cy - (min(q[1] for q in pts) + max(q[1] for q in pts)) / 2
            outs = [mt(_rot_se(rx + ox, ry + oy, a, b, Z_N, th)) for (rx, ry, a, b, th) in rings]
            ins = [mt(_rot_se(rx + ox, ry + oy, a - EIGHT_STROKE, b - EIGHT_STROKE * 1.3, Z_NI, th))
                   for (rx, ry, a, b, th) in rings]
            out.append((kind, outs, ins))
    return out


def _digits_mask(text, S):
    """Black italic digits "001"/"008" in x in [-0.80, -0.445], y in [1.73, 1.86]."""
    W = round((BAND_X[1] - BAND_X[0]) * PPM_BAND)
    H = round((BAND_Y[1] - BAND_Y[0]) * PPM_BAND)
    m = Image.new('L', (W * S, H * S), 0)
    d = ImageDraw.Draw(m)
    mp = Mapper(S)
    for kind, outs, ins in _digit_geom(text):
        for poly in outs:
            d.polygon([mp.px(*q) for q in poly], fill=255)
        for poly in ins:
            d.polygon([mp.px(*q) for q in poly], fill=0)
    return m


# ----------------------------------------------------------------------------------------------------------------------
# Outlines of the numbers as flat polygons (cab_numbers.json) for geometry instead of a decal
# ----------------------------------------------------------------------------------------------------------------------
DP_TOL = 0.0003  # m, Douglas-Peucker tolerance of the exported outlines


def _seg_hit(p, p2, q, q2):
    d1 = (p2[0] - p[0], p2[1] - p[1])
    d2 = (q2[0] - q[0], q2[1] - q[1])
    den = d1[0] * d2[1] - d1[1] * d2[0]
    if abs(den) < 1e-18:
        return None
    t = ((q[0] - p[0]) * d2[1] - (q[1] - p[1]) * d2[0]) / den
    u = ((q[0] - p[0]) * d1[1] - (q[1] - p[1]) * d1[0]) / den
    if 0 <= t < 1 and 0 <= u < 1:
        return t, u, (p[0] + t * d1[0], p[1] + t * d1[1])
    return None


def _inside(pt, poly):
    x, y = pt
    c = False
    n = len(poly)
    for i in range(n):
        (x0, y0), (x1, y1) = poly[i], poly[(i + 1) % n]
        if (y0 > y) != (y1 > y) and x < x0 + (y - y0) * (x1 - x0) / (y1 - y0):
            c = not c
    return c


def _union2(A, B):
    """Union outline of two simple polygons that cross each other exactly twice (same orientation)."""
    hits = []
    for i in range(len(A)):
        for j in range(len(B)):
            h = _seg_hit(A[i], A[(i + 1) % len(A)], B[j], B[(j + 1) % len(B)])
            if h:
                hits.append((i, j, h[0], h[1], h[2]))
    assert len(hits) == 2, f'expected 2 crossings, got {len(hits)}'
    # walk A from just after the crossing where A leaves B, until the next crossing, then walk B
    out = []
    # find the crossing where A goes from inside B to outside B (walking forward on A)
    for k in (0, 1):
        i, j, t, u, pt = hits[k]
        nxt = A[(i + 1) % len(A)]
        if not _inside(nxt, B):
            start, other = hits[k], hits[1 - k]
            break
    i, j, t, u, pt = start
    out.append(pt)
    # along A from start to the other crossing
    idx = (i + 1) % len(A)
    while True:
        if idx == (other[0] + 1) % len(A) and (idx != (i + 1) % len(A) or out[-1] != pt) and len(out) > 1:
            break
        out.append(A[idx])
        if idx == other[0]:
            idx = (idx + 1) % len(A)
            break
        idx = (idx + 1) % len(A)
    out.append(other[4])
    # along B from the other crossing to the start crossing
    jdx = (other[1] + 1) % len(B)
    while True:
        out.append(B[jdx])
        if jdx == j:
            break
        jdx = (jdx + 1) % len(B)
    return out


def _dp(pts, tol):
    """Douglas-Peucker on a closed polygon (split at the two points farthest apart)."""
    n = len(pts)
    best = (0, 0, 0)
    for i in range(0, n, max(1, n // 40)):
        for j in range(i + 1, n, max(1, n // 40)):
            dd = (pts[i][0] - pts[j][0]) ** 2 + (pts[i][1] - pts[j][1]) ** 2
            if dd > best[0]:
                best = (dd, i, j)
    _, i, j = best
    a = pts[i:j + 1]
    b = pts[j:] + pts[:i + 1]

    def rec(seg):
        if len(seg) < 3:
            return seg
        (x0, y0), (x1, y1) = seg[0], seg[-1]
        L = math.hypot(x1 - x0, y1 - y0) or 1e-12
        dmax, k = 0, 0
        for t in range(1, len(seg) - 1):
            dist = abs((x1 - x0) * (y0 - seg[t][1]) - (x0 - seg[t][0]) * (y1 - y0)) / L
            if dist > dmax:
                dmax, k = dist, t
        if dmax > tol:
            return rec(seg[:k + 1])[:-1] + rec(seg[k:])
        return [seg[0], seg[-1]]

    return rec(a)[:-1] + rec(b)[:-1]


def number_contours(text):
    """Closed contours (no repeated first point) of the dark area of a number, in metres."""
    cont = []
    for kind, outs, ins in _digit_geom(text):
        if len(outs) == 2:
            outs = [_union2(outs[0], outs[1])]
        for poly in outs + ins:
            cont.append(_dp(poly, DP_TOL))
    return cont


def _raster_even_odd(contours, S):
    W = round((BAND_X[1] - BAND_X[0]) * PPM_BAND)
    H = round((BAND_Y[1] - BAND_Y[0]) * PPM_BAND)
    mp = Mapper(S)
    acc = Image.new('1', (W * S, H * S), 0)
    for c in contours:
        layer = Image.new('1', acc.size, 0)
        ImageDraw.Draw(layer).polygon([mp.px(*q) for q in c], fill=1)
        acc = ImageChops.logical_xor(acc, layer)
    return acc


def export_numbers(outdir, overlay_dir=None):
    import json
    res = {}
    for text in ('001', '008'):
        cont = number_contours(text)
        res[text] = {'contours': [[[round(x, 5), round(y, 5)] for x, y in c] for c in cont]}
        pts = sum(len(c) for c in cont)
        # check: even-odd raster of the polygons vs the digit mask used in the textures (3x supersampled band pixels)
        ref = _digits_mask(text, SSB).point(lambda v: 255 if v > 127 else 0).convert('1')
        rr = [[(round(x, 5), round(y, 5)) for x, y in c] for c in cont]
        mine = _raster_even_odd(rr, SSB)
        inter = ImageChops.logical_and(ref, mine).convert('L').histogram()[255]
        union = ImageChops.logical_or(ref, mine).convert('L').histogram()[255]
        iou = inter / union
        print(f'cab_numbers {text}: {len(cont)} contours, {pts} points {[len(c) for c in cont]}, IoU {iou:.4f}')
        if overlay_dir:
            band = cab_band(text).convert('RGB')
            Z = 3
            x0, x1 = round((-0.83 + 1.45) * PPM_BAND), round((-0.415 + 1.45) * PPM_BAND)
            y0, y1 = round((2.06 - 1.89) * PPM_BAND), round((2.06 - 1.70) * PPM_BAND)
            crop = band.crop((x0, y0, x1, y1)).resize(((x1 - x0) * Z, (y1 - y0) * Z), Image.LANCZOS)
            d = ImageDraw.Draw(crop)
            for c in cont:
                pp = [(((x + 1.45) * PPM_BAND - x0) * Z, ((2.06 - y) * PPM_BAND - y0) * Z) for x, y in c]
                d.line(pp + [pp[0]], fill=(255, 0, 0), width=1)
                for q in pp:
                    d.ellipse((q[0] - 2, q[1] - 2, q[0] + 2, q[1] + 2), outline=(0, 120, 255))
            crop.save(os.path.join(overlay_dir, f'cab_numbers_overlay_{text}.png'))
    with open(os.path.join(outdir, 'cab_numbers.json'), 'w') as f:
        json.dump(res, f, separators=(',', ':'), sort_keys=True)
    return res


def cab_band(text):
    S = SSB
    W = round((BAND_X[1] - BAND_X[0]) * PPM_BAND)
    H = round((BAND_Y[1] - BAND_Y[0]) * PPM_BAND)
    shape = _band_mask_shape(S)
    thousand, _ = _thousand_mask(S)
    digits = _digits_mask(text, S)
    ink = ImageChops.lighter(thousand, digits)
    ink = ImageChops.multiply(ink, shape)
    shape = shape.resize((W, H), Image.LANCZOS)
    ink = ink.resize((W, H), Image.LANCZOS)
    img = Image.new('RGB', (W, H), CREAM)
    img.paste(Image.new('RGB', (W, H), SLIT), (0, 0), ink)
    out = img.convert('RGBA')
    out.putalpha(shape)
    # transparent pixels: keep the colour of the cream so the mip chain does not bleed black
    return out


# ----------------------------------------------------------------------------------------------------------------------
# Waist lamp unit (0.45 x 0.17 m): outer = express (clear lens), inner = tail (dark mesh)
# Layout measured on c02_meas.png (unit as seen on the viewer's left, i.e. the car's right side):
#   express lamp lens: u 0.10..0.28, v 0.115..0.83; tail lamp mesh: u 0.44..0.83, v 0.115..0.865.  R is the mirror image.
# ----------------------------------------------------------------------------------------------------------------------
LAMP_W, LAMP_H = 512, 194
EXPRESS_U = (0.10, 0.28)
EXPRESS_V = (0.115, 0.83)
TAIL_U = (0.44, 0.83)
TAIL_V = (0.115, 0.865)


def lamp_unit(emit=False):
    SS = 4
    W, H = LAMP_W * SS, LAMP_H * SS
    img = Image.new('RGB', (W, H), (6, 6, 8) if not emit else (0, 0, 0))
    d = ImageDraw.Draw(img)
    if not emit:
        # housing: slightly lighter inner bevel so the black is not flat
        d.rounded_rectangle((0.02 * W, 0.04 * H, 0.98 * W, 0.96 * H), radius=int(0.4 * H), outline=(18, 18, 22),
                            width=int(0.025 * H))
    # express lamp lens
    x0, x1 = EXPRESS_U[0] * W, EXPRESS_U[1] * W
    y0, y1 = EXPRESS_V[0] * H, EXPRESS_V[1] * H
    r = int(0.08 * (y1 - y0))
    if emit:
        d.rounded_rectangle((x0, y0, x1, y1), radius=r, fill=(255, 250, 235))
    else:
        d.rounded_rectangle((x0, y0, x1, y1), radius=r, fill=(206, 210, 212))
        # three vertical prism flutes
        n = 4
        for k in range(1, n):
            xx = x0 + (x1 - x0) * k / n
            d.line((xx, y0 + r, xx, y1 - r), fill=(150, 154, 158), width=int(0.012 * W))
        d.rounded_rectangle((x0, y0, x1, y1), radius=r, outline=(60, 62, 66), width=int(0.01 * W))
    # tail lamp: dark lens with a diamond mesh
    tx0, tx1 = TAIL_U[0] * W, TAIL_U[1] * W
    ty0, ty1 = TAIL_V[0] * H, TAIL_V[1] * H
    tr = int(0.07 * (ty1 - ty0))
    if not emit:
        d.rounded_rectangle((tx0, ty0, tx1, ty1), radius=tr, fill=(22, 20, 22))
        pitch = 0.0125 * W
        dot = 0.0034 * W
        row = 0
        y = ty0 + pitch * 0.6
        while y < ty1 - pitch * 0.3:
            off = (pitch / 2) if row % 2 else 0
            x = tx0 + pitch * 0.6 + off
            while x < tx1 - pitch * 0.3:
                d.ellipse((x - dot, y - dot, x + dot, y + dot), fill=(104, 108, 114))
                x += pitch
            y += pitch / 2
            row += 1
        d.rounded_rectangle((tx0, ty0, tx1, ty1), radius=tr, outline=(52, 54, 58), width=int(0.008 * W))
    img = img.resize((LAMP_W, LAMP_H), Image.LANCZOS)
    return img


def main():
    os.makedirs(OUT, exist_ok=True)

    def save(img, name):
        p = os.path.join(OUT, name)
        img.save(p, optimize=True)
        print(f'{name:26s} {img.width}x{img.height} {img.mode}')

    m = led_runno('13H')
    save(m.render(True), 'led_runno.png')
    save(m.render(False), 'led_runno_off.png')
    m = led_type('快特')
    save(m.render(True), 'led_type.png')
    save(m.render(False), 'led_type_off.png')
    m = led_dest()
    save(m.render(True), 'led_dest.png')
    save(m.render(False), 'led_dest_off.png')
    m = led_side()
    save(m.render(True), 'led_side.png')
    save(m.render(False), 'led_side_off.png')
    m = led_side_wide()
    save(m.render(True, 3200), 'led_side_wide.png')
    save(m.render(False, 3200), 'led_side_wide_off.png')

    save(cab_band('001'), 'cab_band_001.png')
    save(cab_band('008'), 'cab_band_008.png')

    export_numbers(OUT, os.environ.get('NUMBERS_OVERLAY_DIR'))

    L = lamp_unit(False)
    save(L, 'lamp_unit_L.png')
    save(L.transpose(Image.FLIP_LEFT_RIGHT), 'lamp_unit_R.png')
    E = lamp_unit(True)
    save(E, 'lamp_unit_emit_L.png')
    save(E.transpose(Image.FLIP_LEFT_RIGHT), 'lamp_unit_emit_R.png')


if __name__ == '__main__':
    main()
