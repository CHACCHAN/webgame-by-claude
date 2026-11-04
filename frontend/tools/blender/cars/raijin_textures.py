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


def headlight():
    w0, w1, v0, v1 = D.HEAD_BOX
    s = Sheet(D.HEAD_BOX, 512, round(512 * (v1 - v0) / (w1 - w0)), (28, 30, 34))
    outline = D.closed_spline(D.HEAD_OUTLINE, 4)
    # chrome bowl behind the clear lens: bright at the top, darker low down
    _vgrad(s, outline, (138, 143, 150), (72, 76, 84))
    # the reflector's faceting: soft vertical bands
    for k in range(14):
        w = w0 + (w1 - w0) * (k + 0.5) / 14
        x, _ = s.px(w, 0)
        s.d.line([(x, 0), (x, s.H)], fill=(104, 110, 118), width=SS)
    s.img = Image.composite(s.img, Image.new('RGB', (s.W, s.H), (28, 30, 34)), _mask(s, outline))
    s.d = ImageDraw.Draw(s.img)
    # high beam: a deep chrome bowl with a bulb cap
    hx, hy, hr = D.HEAD_HIGH
    s.circle(hx, hy, hr * 1.04, (96, 100, 108))
    s.radial(hx, hy, hr, (190, 194, 200), (92, 98, 106))
    for k in range(1, 4):
        s.circle(hx, hy, hr * (0.28 + 0.22 * k), None, (150, 156, 164), width=SS)
    s.circle(hx, hy, hr * 0.22, (100, 104, 112))
    s.circle(hx, hy, hr * 0.12, (60, 62, 68))
    # low beam projector in the tear: dark shroud, chrome ring, glass lens with a bright crescent
    px, py, pr = D.HEAD_PROJECTOR
    s.circle(px, py, pr * 1.10, (84, 88, 96))
    s.radial(px, py, pr, (168, 172, 180), (92, 98, 106))
    s.circle(px, py, pr * 0.74, (52, 58, 68))
    s.radial(px, py, pr * 0.70, (128, 138, 152), (58, 64, 74))
    s.circle(px - pr * 0.22, py + pr * 0.26, pr * 0.16, (236, 242, 250))
    # position lamp bulb near the top of the outer part
    qx, qy, qr = D.HEAD_POSITION
    s.radial(qx, qy, qr, (250, 250, 252), (150, 154, 160))
    # amber indicator strip at the outer end
    amber = D.closed_spline(D.HEAD_AMBER, 3)
    s.poly(amber, (196, 120, 48))
    # the lens's gasket and the clear lens's highlight along the top edge
    s.d.line([s.px(*p) for p in outline + outline[:1]], fill=(24, 26, 30), width=4 * SS)
    top = [p for p in D.closed_spline(D.HEAD_OUTLINE, 4) if p[1] > 0.035 and p[0] < 0.29]
    s.d.line([s.px(p[0], p[1] - 0.010) for p in sorted(top)], fill=(240, 244, 250), width=2 * SS)
    s.save(os.path.join(OUT, 'headlight.png'), (512, s.H // SS))


def taillight():
    w0, w1, v0, v1 = D.TAIL_BOX
    s = Sheet(D.TAIL_BOX, 512, round(512 * (v1 - v0) / (w1 - w0)), (30, 6, 6))
    outline = D.closed_spline(D.TAIL_OUTLINE, 4)
    _vgrad(s, outline, (176, 22, 24), (112, 12, 14))
    # fine horizontal ribs over the red
    mask = _mask(s, outline)
    ribs = s.img.copy()
    rd = ImageDraw.Draw(ribs)
    for k in range(40):
        y = s.px(0, v0 + (v1 - v0) * k / 40)[1]
        rd.rectangle([0, y, s.W, y + 1.5 * SS], fill=(92, 10, 12))
    s.img = Image.composite(ribs, s.img, mask)
    s.d = ImageDraw.Draw(s.img)
    # the two round elements: Fresnel rings
    for cx, cy, cr in (D.TAIL_ROUND, D.TAIL_ROUND2):
        s.circle(cx, cy, cr * 1.06, (96, 8, 10))
        s.radial(cx, cy, cr, (238, 52, 50), (150, 16, 18))
        for k in range(1, 6):
            s.circle(cx, cy, cr * k / 6, None, (128, 14, 16), width=SS)
    # the clear upper inner part: silver reflector behind a clear lens, a bulb in the middle
    clear = D.closed_spline(D.TAIL_CLEAR, 3)
    s.img = Image.composite(Image.new('RGB', (s.W, s.H), (150, 152, 158)), s.img, _mask(s, clear))
    s.d = ImageDraw.Draw(s.img)
    cx = sum(p[0] for p in D.TAIL_CLEAR) / len(D.TAIL_CLEAR)
    cy = sum(p[1] for p in D.TAIL_CLEAR) / len(D.TAIL_CLEAR)
    s.radial(cx, cy, 0.030, (214, 216, 222), (138, 140, 146))
    s.d.line([s.px(*p) for p in clear + clear[:1]], fill=(70, 20, 20), width=2 * SS)
    s.d.line([s.px(*p) for p in outline + outline[:1]], fill=(36, 8, 8), width=4 * SS)
    s.save(os.path.join(OUT, 'taillight.png'), (512, s.H // SS))


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
