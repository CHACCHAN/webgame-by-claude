"""
Paints the Impreza's textures (deterministic, our own drawing; no photo pixels) with PIL on the host:

  python3 tools/blender/cars/raijin_textures.py [outdir]      (default tools/blender/textures/raijin/)

headlight.png  head lamp lens (projector, high-beam bowl, chrome housing); the game glows through it at night
taillight.png  tail lamp lens (red, the round stop / tail element, ribs)
plate.png      white Japanese plate with fictional text (Noto Sans CJK, OFL)
grille.png     honeycomb mesh (tiles)
tire.png       tyre: sidewall and tread blocks (u around the tyre, v across the profile)
"""
import math
import os
import sys

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from PIL import Image, ImageDraw, ImageFilter, ImageFont  # noqa: E402

import raijin_data as D  # noqa: E402

OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(HERE), 'textures', 'raijin')
SS = 4   # supersampling
FONT = '/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc'


class Sheet:
    """a canvas over a box of the lamp frame (w0, w1, v0, v1) in metres"""

    def __init__(self, box, w, h, bg):
        self.box = box
        self.W, self.H = w * SS, h * SS
        self.img = Image.new('RGB', (self.W, self.H), bg)
        self.d = ImageDraw.Draw(self.img)

    def px(self, w, v):
        w0, w1, v0, v1 = self.box
        return ((w - w0) / (w1 - w0) * self.W, (v1 - v) / (v1 - v0) * self.H)

    def r(self, metres):
        return metres / (self.box[1] - self.box[0]) * self.W

    def poly(self, pts, fill, outline=None, width=0):
        self.d.polygon([self.px(*p) for p in pts], fill=fill, outline=outline, width=width)

    def circle(self, cx, cy, rad, fill, outline=None, width=0):
        x, y = self.px(cx, cy)
        r = self.r(rad)
        self.d.ellipse([x - r, y - r, x + r, y + r], fill=fill, outline=outline, width=int(width))

    def radial(self, cx, cy, rad, inner, outer, steps=24):
        for k in range(steps, 0, -1):
            t = k / steps
            col = tuple(int(inner[i] + (outer[i] - inner[i]) * t) for i in range(3))
            self.circle(cx, cy, rad * t, col)

    def save(self, path, size):
        self.img.resize(size, Image.LANCZOS).save(path)


def _mask(s, pts):
    m = Image.new('L', (s.W, s.H), 0)
    ImageDraw.Draw(m).polygon([s.px(*p) for p in pts], fill=255)
    return m


def _vgrad(s, pts, top, bottom, steps=48):
    """fill an outline with a vertical gradient (top colour → bottom colour)"""
    w0, w1, v0, v1 = s.box
    grad = Image.new('RGB', (s.W, s.H))
    gd = ImageDraw.Draw(grad)
    for k in range(steps):
        t = k / (steps - 1)
        col = tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3))
        y0 = s.H * k / steps
        gd.rectangle([0, y0, s.W, y0 + s.H / steps + 1], fill=col)
    s.img = Image.composite(grad, s.img, _mask(s, pts))
    s.d = ImageDraw.Draw(s.img)


def _lerp(a, b, t):
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))


def _bowl(s, cx, cy, rad, facets, lo, hi, well, rim=(176, 180, 188), glints=True):
    """a chrome reflector bowl seen through the clear lens: alternating facets (the upper ones catch the sky), darker
    in the well round the centre, a bright rim and a few glints. Mid-grey chrome, not white: it mirrors a dark
    surround (the bright parts are also the glow pattern at night)."""
    x, y = s.px(cx, cy)
    r = s.r(rad)
    for k in range(facets):
        a0, a1 = 360 * k / facets, 360 * (k + 1) / facets
        c = hi if k % 2 else lo
        if 200 < (a0 + a1) / 2 < 340:
            c = tuple(min(255, v + 26) for v in c)
        s.d.pieslice([x - r, y - r, x + r, y + r], a0, a1, fill=c)
    for k in range(24, 0, -1):
        t = k / 24 * 0.5
        rr = r * t
        s.d.ellipse([x - rr, y - rr, x + rr, y + rr], fill=_lerp(well, _lerp(lo, hi, 0.5), t / 0.5))
    s.d.ellipse([x - r, y - r, x + r, y + r], outline=rim, width=2 * SS)
    if glints:
        for hx, hy, hr in ((-0.50, -0.55, 0.07), (0.58, -0.40, 0.05), (-0.70, 0.25, 0.04)):
            s.d.ellipse([x + r * hx - r * hr, y + r * hy - r * hr, x + r * hx + r * hr, y + r * hy + r * hr], fill=(232, 234, 238))


def headlight():
    """
    The 2004 lamp seen through its clear cover, as on the photos (head-on r16, front 3/4 r02): a silver-grey chrome
    housing (lighter high up, where it mirrors the sky), the projector's chrome ring and dark glass lens in the round
    inner end with a dark shroud round it, the high beam's faceted bowl in the middle, the position bulb in the top
    outer corner, the indicator's amber reflector low in the outer end and its amber streak along the top of the
    middle, a dark grey band along the lower edge. Layout: raijin_data (measured, lamp frame w, v).
    """
    w0, w1, v0, v1 = D.HEAD_BOX
    bg = (30, 31, 35)
    s = Sheet(D.HEAD_BOX, 768, round(768 * (v1 - v0) / (w1 - w0)), bg)
    outline = D.closed_spline(D.HEAD_OUTLINE, 4)
    # housing: mid-grey chrome, lighter towards the top; vertical facet bands
    _vgrad(s, outline, (172, 176, 184), (100, 104, 112))
    lines = s.img.copy()
    ld = ImageDraw.Draw(lines)
    for k in range(22):
        x, _ = s.px(w0 + (w1 - w0) * (k + 0.5) / 22, 0)
        ld.line([(x, 0), (x, s.H)], fill=(124, 128, 136), width=SS)
    s.img = Image.composite(lines, s.img, _mask(s, outline))
    s.d = ImageDraw.Draw(s.img)
    # the dark grey band along the lower edge (the housing's lower bezel)
    low = [(p[0], p[1]) for p in outline if p[1] < -0.03]
    band = [(w, v + 0.020) for w, v in sorted(low)] + [(w, v - 0.01) for w, v in sorted(low, reverse=True)]
    s.d.polygon([s.px(*p) for p in band], fill=(58, 60, 66))
    # amber streak along the top of the middle part (the amber reflector seen head-on)
    st = D.closed_spline(D.HEAD_STREAK, 3)
    _vgrad(s, st, (206, 134, 58), (168, 100, 44))
    s.d = ImageDraw.Draw(s.img)
    # high beam: a faceted chrome bowl round the bulb cap
    hx, hy, hr = D.HEAD_HIGH
    _bowl(s, hx, hy, hr, 20, (112, 116, 124), (164, 168, 176), (66, 68, 74))
    for k in (0.62, 0.82):
        x, y = s.px(hx, hy)
        r = s.r(hr) * k
        s.d.ellipse([x - r, y - r, x + r, y + r], outline=(78, 80, 88), width=SS)
    s.radial(hx, hy, hr * 0.16, (236, 236, 232), (128, 130, 136))
    # projector: dark shroud, chrome ring, the lens (dark blue-grey glass, lighter low down) with a glint
    px, py, pr = D.HEAD_PROJECTOR
    s.circle(px, py, pr * 1.16, (46, 48, 54))
    s.radial(px, py, pr, (184, 188, 196), (112, 116, 124))
    s.circle(px, py, pr * 0.80, (40, 42, 48))
    for k in range(20, 0, -1):
        t = k / 20
        s.circle(px, py, pr * 0.74 * t, _lerp((58, 66, 80), (104, 114, 130), 1 - t))
    s.circle(px - pr * 0.22, py + pr * 0.30, pr * 0.10, (232, 238, 246))
    # the indicator's amber reflector in the outer end: amber facets, muted under the clear cover
    amber = D.closed_spline(D.HEAD_AMBER, 3)
    _vgrad(s, amber, (214, 140, 62), (164, 96, 40))
    s.d = ImageDraw.Draw(s.img)
    lines = s.img.copy()
    ld = ImageDraw.Draw(lines)
    for k in range(40):
        x, _ = s.px(w0 + (w1 - w0) * (k + 0.5) / 40, 0)
        ld.line([(x, 0), (x, s.H)], fill=(150, 88, 38), width=SS)
    s.img = Image.composite(lines, s.img, _mask(s, amber))
    s.d = ImageDraw.Draw(s.img)
    # position lamp: a small chrome bowl with its bulb, top outer corner
    qx, qy, qr = D.HEAD_POSITION
    _bowl(s, qx, qy, qr * 1.6, 12, (110, 114, 122), (150, 154, 162), (70, 72, 78), glints=False)
    s.radial(qx, qy, qr * 0.6, (250, 250, 252), (150, 154, 160))
    # the lens's seal and the clear cover's highlight along the top edge
    s.d.line([s.px(*p) for p in outline + outline[:1]], fill=(22, 23, 26), width=4 * SS)
    top = [p for p in outline if p[1] > 0.02 and 0.0 < p[0] < 0.27]
    s.d.line([s.px(p[0], p[1] - 0.009) for p in sorted(top)], fill=(214, 220, 228), width=2 * SS)
    s.img = s.img.filter(ImageFilter.GaussianBlur(SS * 0.6))
    s.save(os.path.join(OUT, 'headlight.png'), (768, s.H // SS))


def taillight():
    """
    The 2004 tail lamp, as on the photos (tail-on r17, rear 3/4 r10, side r13): red lens with fine horizontal ribs,
    darker low down; the clear upper wedge under a red rim along the top (silver reflector, two clear reverse bulbs
    inboard, two amber indicator bulbs outboard); the round stop / tail element at the inner bottom (Fresnel rings in a
    dark ring). Layout: raijin_data (measured, lamp frame w, v).
    """
    w0, w1, v0, v1 = D.TAIL_BOX
    s = Sheet(D.TAIL_BOX, 768, round(768 * (v1 - v0) / (w1 - w0)), (30, 6, 6))
    outline = D.closed_spline(D.TAIL_OUTLINE, 4)
    _vgrad(s, outline, (190, 30, 32), (122, 14, 16))
    mask = _mask(s, outline)
    ribs = s.img.copy()
    rd = ImageDraw.Draw(ribs)
    for k in range(52):
        y = s.px(0, v0 + (v1 - v0) * k / 52)[1]
        rd.rectangle([0, y, s.W, y + 1.2 * SS], fill=(118, 14, 16))
    s.img = Image.composite(ribs, s.img, mask)
    s.d = ImageDraw.Draw(s.img)
    # the round element: a dark ring, Fresnel rings, brighter centre
    for cx, cy, cr in [e for e in (D.TAIL_ROUND, D.TAIL_ROUND2) if e]:
        s.circle(cx, cy, cr * 1.10, (84, 8, 10))
        s.circle(cx, cy, cr * 1.02, (150, 20, 22))
        s.radial(cx, cy, cr * 0.94, (236, 58, 54), (150, 18, 20))
        for k in range(1, 7):
            s.circle(cx, cy, cr * 0.94 * k / 7, None, (132, 16, 18), width=SS)
    # the clear wedge: a silver reflector behind the clear cover (lighter high up), faceted
    clear = D.closed_spline(D.TAIL_CLEAR, 3)
    _vgrad(s, clear, (178, 180, 186), (118, 120, 128))
    cm = _mask(s, clear)
    fac = s.img.copy()
    fd = ImageDraw.Draw(fac)
    for k in range(48):
        x, _ = s.px(w0 + (w1 - w0) * (k + 0.5) / 48, 0)
        fd.line([(x, 0), (x, s.H)], fill=(136, 138, 146), width=SS)
    s.img = Image.composite(fac, s.img, cm)
    s.d = ImageDraw.Draw(s.img)
    for (bx, by, br), amber in zip(D.TAIL_BULBS, D.TAIL_BULB_AMBER):
        # a plain chrome cup round the bulb (seen through the clear cover: no facets)
        s.radial(bx, by, br * 1.15, (164, 166, 172), (104, 106, 114))
        s.circle(bx, by, br * 1.15, None, (92, 94, 100), width=SS)
        s.radial(bx, by, br * 0.50, (228, 144, 58) if amber else (236, 236, 238), (168, 90, 34) if amber else (148, 150, 156))
    s.d.line([s.px(*p) for p in clear + clear[:1]], fill=(110, 26, 26), width=2 * SS)
    s.d.line([s.px(*p) for p in outline + outline[:1]], fill=(36, 8, 8), width=4 * SS)
    s.img = s.img.filter(ImageFilter.GaussianBlur(SS * 0.5))
    s.save(os.path.join(OUT, 'taillight.png'), (768, s.H // SS))


def plate():
    W, H = 660 * 2, 330 * 2
    img = Image.new('RGB', (W, H), (240, 241, 236))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([6, 6, W - 7, H - 7], radius=28, outline=(70, 90, 80), width=8)
    green = (24, 92, 52)
    area, cls, kana, num = D.PLATE_TEXT
    f1 = ImageFont.truetype(FONT, 118)
    f2 = ImageFont.truetype(FONT, 104)
    f3 = ImageFont.truetype(FONT, 300)
    d.text((W * 0.30, H * 0.07), area, font=f1, fill=green)
    d.text((W * 0.50, H * 0.08), cls, font=f2, fill=green)
    d.text((W * 0.06, H * 0.47), kana, font=f1, fill=green)
    d.text((W * 0.20, H * 0.18), num, font=f3, fill=green)
    for x in (W * 0.22, W * 0.78):
        d.ellipse([x - 16, H * 0.12 - 16, x + 16, H * 0.12 + 16], fill=(170, 172, 168))
    img.resize((512, 256), Image.LANCZOS).save(os.path.join(OUT, 'plate.png'))


def grille():
    W = 256 * SS
    img = Image.new('RGB', (W, W), (8, 8, 9))
    d = ImageDraw.Draw(img)
    r = W / 8
    h = r * math.sqrt(3) / 2
    for j in range(-1, 10):
        for i in range(-1, 10):
            cx = i * 1.5 * r
            cy = j * 2 * h + (h if i % 2 else 0)
            pts = [(cx + r * 0.88 * math.cos(math.radians(60 * k)), cy + r * 0.88 * math.sin(math.radians(60 * k))) for k in range(6)]
            d.polygon(pts, outline=(52, 54, 58), width=int(r * 0.14))
    img.resize((256, 256), Image.LANCZOS).save(os.path.join(OUT, 'grille.png'))


def tire():
    """u: 1 = one twelfth of the circumference; v: 0 inner bead → 1 outer bead (tread from 0.36 to 0.64)"""
    W, H = 256 * SS, 512 * SS
    img = Image.new('RGB', (W, H), (34, 34, 35))
    d = ImageDraw.Draw(img)
    t0, t1 = 0.36 * H, 0.64 * H
    d.rectangle([0, t0, W, t1], fill=(46, 46, 47))
    # circumferential grooves
    for g in (0.405, 0.465, 0.535, 0.595):
        d.rectangle([0, g * H - 5 * SS, W, g * H + 5 * SS], fill=(14, 14, 15))
    # lateral grooves: 5 blocks per tile, staggered per rib, slanted
    ribs = [(0.36, 0.40), (0.41, 0.46), (0.47, 0.53), (0.54, 0.59), (0.60, 0.64)]
    for k, (a, b) in enumerate(ribs):
        n = 5 if k in (0, 4) else 10
        for i in range(n):
            x = (i + 0.5 * (k % 2)) * W / n
            d.polygon([(x - 3 * SS, a * H), (x + 3 * SS, a * H), (x + 3 * SS + 14 * SS, b * H), (x - 3 * SS + 14 * SS, b * H)],
                      fill=(16, 16, 17))
    # sidewall rim rings
    for v in (0.12, 0.20, 0.80, 0.88):
        d.rectangle([0, v * H - 2 * SS, W, v * H + 2 * SS], fill=(26, 26, 27))
    img.resize((256, 512), Image.LANCZOS).save(os.path.join(OUT, 'tire.png'))


def main():
    os.makedirs(OUT, exist_ok=True)
    headlight()
    taillight()
    plate()
    grille()
    tire()
    print('textures →', OUT)


main()
