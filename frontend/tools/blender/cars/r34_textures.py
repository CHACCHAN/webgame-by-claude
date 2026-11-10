"""
Textures for the R34 (deterministic, PIL on the host; no photo pixels):

  python3 tools/blender/cars/r34_textures.py      -> tools/blender/textures/r34/*.png

headlight.png  the lamp unit seen through its clear cover: smoked dark housing, three round elements (inner projector
               in an oval chrome ring, middle multi-reflector, stippled clearance reflector in the corner), black
               lower band (bright parts are the glow pattern at night)
taillight.png  two round lamps side by side: left = outer lamp (red centre), right = inner lamp (amber centre)
plate.png      a white Japanese plate with fictional text (朧 300 / さ 12-34), Noto Sans CJK (OFL)
indicator.png  clear ribbed lens of the front indicators and the reverse lamp (faint amber glow behind)
mesh.png       black honeycomb grille mesh (tiles)
tyre.png       tyre: tread band (v 0.3 .. 0.7: four grooves, sipes) between plain sidewalls; repeats 12x round
"""
import math
import os

from PIL import Image, ImageDraw, ImageFilter, ImageFont

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'textures', 'r34')
FONT = '/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc'


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(len(a)))


def radial(draw, cx, cy, r, inner, outer, steps=40):
    for k in range(steps, 0, -1):
        t = k / steps
        c = lerp(inner, outer, t)
        draw.ellipse([cx - r * t, cy - r * t, cx + r * t, cy + r * t], fill=c)


# the head lamp lens's box (r34_fit.LAMP_BOX) in the nose's unrolled coordinates (r34_fit.Unrolled): s = x on the
# front, then the distance on round the wing's corner (from s ~0.85) and back along the side to the lamp's rounded
# rear end (s 1.115); y bottom to top. The texture spans it: u = 0 at the inner end
LAMP_BOX = (0.444, 0.602, 1.118, 0.765)


def headlight(w=1536, h=360, ss=2):
    """
    One lamp unit seen through its clear cover (u = 0 at the grille, 1 at the rear end of the part wrapped round the
    wing's corner; v up), as on the photos (head-on r29 hi-res, front 3/4 r07, r12, r22, side r36): a smoked, near-black
    housing holding three round elements in a row with dark separators between them: the inner projector (low beam)
    in a big oval chrome ring that fills the lamp's height, the middle multi-reflector (high beam) round its bulb
    shield, and the smaller stippled reflector of the clearance lamp in the corner; a chrome bar in the side part; a
    black band along the bottom under a thin chrome strip. The reflectors are mid-grey chrome with bright glints (they
    mirror a dark surround), not white: bright parts are also the glow pattern at night.
    """
    W, H = w * ss, h * ss
    x0, y0, x1, y1 = LAMP_BOX
    P = lambda x, y: ((x - x0) / (x1 - x0) * W, (1 - (y - y0) / (y1 - y0)) * H)
    R = lambda r: r / (x1 - x0) * W
    RY = lambda r: r / (y1 - y0) * H
    bottom = lambda s: 0.602 + min(s - 0.444, 0.40) * 0.107 - max(0.0, s - 0.95) * 0.03
    top = lambda s: min(0.712 + (s - 0.452) * 0.130, 0.762)
    im = Image.new('RGB', (W, H), (26, 27, 30))
    d = ImageDraw.Draw(im)
    for py in range(H):                      # housing: smoked dark grey, a little lighter up high (the cover's sheen)
        t = py / H
        d.line([(0, py), (W, py)], fill=lerp((70, 72, 78), (42, 43, 48), t))

    def ell(cx, cy, rx, ry, k, fill):
        d.ellipse([cx - rx * k, cy - ry * k, cx + rx * k, cy + ry * k], fill=fill)

    def bowl(x, y, rx_, ry_, facets, lo=(70, 72, 78), hi=(112, 115, 122), well=(40, 42, 47)):
        """a chrome reflector bowl: faceted sectors (alternating), the upper ones catching the sky, darker in the
        well round the centre, a bright rim and a few glints"""
        cx, cy = P(x, y)
        rx, ry = R(rx_), RY(ry_)
        for k in range(facets):
            a0, a1 = 360 * k / facets, 360 * (k + 1) / facets
            c = hi if k % 2 else lo
            if 200 < (a0 + a1) / 2 < 340:
                c = tuple(min(255, v + 30) for v in c)
            d.pieslice([cx - rx, cy - ry, cx + rx, cy + ry], a0, a1, fill=c)
        for k in range(30, 0, -1):
            t = k / 30 * 0.5
            ell(cx, cy, rx, ry, t, lerp(well, lerp(lo, hi, 0.5), t / 0.5))
        d.ellipse([cx - rx, cy - ry, cx + rx, cy + ry], outline=(170, 174, 182), width=ss * 2)
        for hx, hy, hr in ((-0.50, -0.55, 0.08), (0.58, -0.40, 0.05), (-0.70, 0.25, 0.04), (0.30, 0.62, 0.035)):
            ell(cx + rx * hx, cy + ry * hy, rx * hr, rx * hr, 1.0, (232, 234, 238))
        return cx, cy, rx, ry

    # separators between the elements: dark slanted bands with a thin chrome edge
    for s0, s1 in ((0.628, 0.640), (0.800, 0.814)):
        d.polygon([P(s0 - 0.004, 0.59), P(s1 - 0.004, 0.59), P(s1 + 0.004, 0.78), P(s0 + 0.004, 0.78)], fill=(22, 23, 26))
        d.line([P(s1 - 0.004, 0.59), P(s1 + 0.004, 0.78)], fill=(120, 123, 130), width=ss * 2)
    # inner element: the projector in a big oval chrome ring (as tall as the lamp there)
    cx, cy = P(0.560, 0.684)
    rx, ry = R(0.068), RY(0.054)
    ell(cx, cy, rx, ry, 1.0, (176, 179, 186))
    ell(cx, cy, rx, ry, 0.93, (32, 33, 37))
    bowl(0.560, 0.684, 0.060, 0.048, 14)
    for k, c in ((0.46, (168, 172, 178)), (0.40, (78, 82, 90))):          # the lens's chrome cowl
        ell(cx, cy, rx * 0.88, ry * 1.1, k, c)
    for k in range(24, 0, -1):                                             # the lens: grey glass, lighter low down
        t = k / 24
        ell(cx, cy, rx * 0.88, ry * 1.1, 0.36 * t, lerp((112, 118, 130), (52, 57, 66), t))
    ell(cx - rx * 0.10, cy - ry * 0.16, rx * 0.07, rx * 0.07, 1.0, (228, 232, 240))
    # middle element: the high beam's multi-reflector round the bulb shield
    cx, cy, rx, ry = bowl(0.716, 0.698, 0.076, 0.056, 18, lo=(80, 83, 90), hi=(126, 130, 138))
    for k in (0.62, 0.80):                                                 # the reflector's facet rings
        d.ellipse([cx - rx * k, cy - ry * k, cx + rx * k, cy + ry * k], outline=(70, 72, 78), width=ss * 2)
    ell(cx, cy, rx, ry, 0.20, (60, 62, 68))
    radial(d, cx, cy, ry * 0.15, (236, 236, 232), (128, 130, 136))         # the bulb shield
    # corner element: the clearance lamp's stippled reflector, wrapped round the corner
    cx, cy = P(0.888, 0.705)
    rx, ry = R(0.058), RY(0.048)
    ell(cx, cy, rx, ry, 1.0, (150, 154, 162))
    ell(cx, cy, rx, ry, 0.93, (88, 92, 100))
    step = R(0.006)
    yy = cy - ry
    row = 0
    while yy < cy + ry:                                                    # the stipple: a grid of small domes
        xx = cx - rx + (step / 2 if row % 2 else 0)
        while xx < cx + rx:
            if ((xx - cx) / rx) ** 2 + ((yy - cy) / ry) ** 2 < 0.80:
                ell(xx, yy, step * 0.32, step * 0.32, 1.0, (140, 144, 152) if (yy < cy) else (112, 116, 124))
            xx += step
        yy += step * 0.87
        row += 1
    radial(d, cx, cy, ry * 0.18, (240, 240, 236), (140, 142, 148))
    # the side part: a grey chrome reflector behind the clear cover (bright seen from the side, r36), lighter high up,
    # with dark bars across it
    for k in range(60):
        t = k / 60
        s0 = 0.950 + 0.17 * t
        d.polygon([P(s0, 0.62), P(s0 + 0.003, 0.62), P(s0 + 0.003, 0.77), P(s0, 0.77)],
                  fill=lerp((96, 99, 106), (72, 74, 80), t))
    for k in range(H // ss // 4):
        yv = 0.62 + 0.15 * k / (H // ss // 4)
        d.line([P(0.950, yv), P(1.12, yv)], fill=lerp((72, 74, 80), (112, 116, 124), (yv - 0.62) / 0.15), width=ss * 2)
    d.line([P(1.030, 0.636), P(1.024, 0.756)], fill=(36, 37, 41), width=ss * 6)
    d.line([P(0.958, 0.640), P(0.953, 0.758)], fill=(36, 37, 41), width=ss * 6)
    d.line([P(1.037, 0.636), P(1.031, 0.756)], fill=(160, 164, 172), width=ss * 2)
    # black band along the bottom under a thin chrome strip, dark screen print along the top edge
    ss_ = [x0 + (x1 - x0) * k / 80 for k in range(81)]
    d.polygon([P(s, bottom(s) + 0.016) for s in ss_] + [P(s, 0.59) for s in reversed(ss_)], fill=(30, 31, 34))
    d.line([P(s, bottom(s) + 0.017) for s in ss_ if s < 0.80], fill=(176, 179, 186), width=ss * 3)
    d.polygon([P(s, top(s) - 0.003) for s in ss_] + [P(s, 0.78) for s in reversed(ss_)], fill=(26, 26, 29))
    im = im.resize((w, h), Image.LANCZOS).filter(ImageFilter.GaussianBlur(0.6))
    im.save(os.path.join(OUT, 'headlight.png'))


def taillight(s=512):
    """
    Two round lamps side by side (left half: the outer lamp, right: the inner); the lens radius is 0.476 of a half's
    width. As on the tail-on photo (r37): a deep red outer ring over its reflector (lighter towards the bottom), a dark
    ring, then the domed centre: red on the outer lamp (r 0.45), red-orange on the inner one (turn signal, r 0.50).
    """
    im = Image.new('RGB', (2 * s, s), (30, 3, 4))
    d = ImageDraw.Draw(im)
    for k, (centre, rc) in enumerate((((214, 30, 24), 0.45), ((226, 82, 42), 0.50))):
        cx, cy, r = k * s + s / 2, s / 2, s * 0.476
        d.ellipse([cx - r * 1.02, cy - r * 1.02, cx + r * 1.02, cy + r * 1.02], fill=(36, 4, 5))
        radial(d, cx, cy, r, (112, 14, 14), (84, 9, 10))
        for a in range(0, 360, 5):                    # the ring's reflector facets
            t = math.radians(a)
            d.line([(cx + r * (rc + 0.10) * math.cos(t), cy + r * (rc + 0.10) * math.sin(t)),
                    (cx + r * 0.96 * math.cos(t), cy + r * 0.96 * math.sin(t))], fill=(98, 12, 12), width=2)
        for j in range(24):                           # lighter reflex towards the bottom of the ring
            t = j / 24
            d.arc([cx - r * (0.70 + 0.25 * t), cy - r * (0.70 + 0.25 * t), cx + r * (0.70 + 0.25 * t),
                   cy + r * (0.70 + 0.25 * t)], 30, 150, fill=lerp((150, 36, 34), (110, 16, 16), t), width=3)
        d.ellipse([cx - r * (rc + 0.07), cy - r * (rc + 0.07), cx + r * (rc + 0.07), cy + r * (rc + 0.07)],
                  fill=(46, 5, 6))
        radial(d, cx, cy, r * rc, lerp(centre, (255, 255, 255), 0.22), lerp(centre, (0, 0, 0), 0.18))
        for ring in (0.35, 0.65):
            d.ellipse([cx - r * rc * ring, cy - r * rc * ring, cx + r * rc * ring, cy + r * rc * ring],
                      outline=lerp(centre, (0, 0, 0), 0.25), width=3)
    im = im.filter(ImageFilter.GaussianBlur(1.0))
    im.save(os.path.join(OUT, 'taillight.png'))


def plate(w=1024, h=512):
    im = Image.new('RGB', (w, h), (240, 241, 236))
    d = ImageDraw.Draw(im)
    green = (22, 92, 52)
    d.rounded_rectangle([6, 6, w - 7, h - 7], radius=26, outline=green, width=10)
    f1 = ImageFont.truetype(FONT, 118, index=0)
    f2 = ImageFont.truetype(FONT, 250, index=0)
    f3 = ImageFont.truetype(FONT, 120, index=0)
    d.text((w / 2, 112), '朧 300', font=f1, fill=green, anchor='mm')
    d.text((112, 335), 'さ', font=f3, fill=green, anchor='mm')
    d.text((w / 2 + 70, 330), '12-34', font=f2, fill=green, anchor='mm')
    for x in (w * 0.22, w * 0.78):         # bolts
        d.ellipse([x - 16, 40, x + 16, 72], fill=(170, 172, 168))
    im.save(os.path.join(OUT, 'plate.png'))


def indicator(w=256, h=128):
    """
    The clear lens of the front indicators and the rear reverse lamp (u, v across the lens's box), as on the head-on
    photo (r29 hi-res): light grey-silver prismatic glass, fine horizontal ribs over fainter vertical ones, darker
    towards the edges where the black inner housing shows through, the amber bulb only a faint warm glow behind it.
    """
    im = Image.new('RGB', (w, h))
    px = im.load()
    for y in range(h):
        for x in range(w):
            u, v = (x + 0.5) / w, (y + 0.5) / h
            e = min(u, 1 - u, (v * h / w), ((1 - v) * h / w)) / 0.10          # 0 at the edge .. 1 inside
            k = 0.40 + 0.60 * min(1.0, e) ** 0.6
            c = [158 * k, 156 * k, 152 * k]
            rib = math.cos(2 * math.pi * y / 9.0)                              # horizontal ribs
            col = math.cos(2 * math.pi * x / 10.0)                             # fainter vertical ones
            for i in range(3):
                c[i] += 15 * rib * k + 6 * col * k + 10 * (1 - v) * k          # a little lighter up high
            g = math.exp(-(((u - 0.5) / 0.16) ** 2 + ((v - 0.5) / 0.22) ** 2))  # the amber bulb's faint glow
            c = [c[0] + 26 * g, c[1] + 8 * g, c[2] - 14 * g]
            px[x, y] = tuple(int(max(0, min(255, a))) for a in c)
    im = im.filter(ImageFilter.GaussianBlur(0.5))
    im.save(os.path.join(OUT, 'indicator.png'))


def mesh(s=256):
    im = Image.new('RGB', (s, s), (8, 8, 9))
    d = ImageDraw.Draw(im)
    n = 8
    rx = s / n
    ry = rx * math.sqrt(3) / 2
    for j in range(-1, int(s / ry) + 2):
        for i in range(-1, n + 2):
            cx = i * rx + (rx / 2 if j % 2 else 0)
            cy = j * ry
            pts = [(cx + rx * 0.5 * math.cos(math.radians(60 * k + 30)), cy + rx * 0.5 * math.sin(math.radians(60 * k + 30)))
                   for k in range(6)]
            d.polygon(pts, outline=(78, 80, 84), fill=(3, 3, 4), width=3)
    im.save(os.path.join(OUT, 'mesh.png'))


def tyre(s=512):
    """u: round the tyre (one of 12 repeats), v: across the profile (sidewall, tread, sidewall)"""
    im = Image.new('RGB', (s, s), (27, 27, 28))
    d = ImageDraw.Draw(im)
    t0, t1 = int(0.30 * s), int(0.70 * s)
    d.rectangle([0, t0, s, t1], fill=(33, 33, 34))
    for k in range(6):           # sidewall rings
        for y in (int(s * (0.07 + 0.035 * k)), int(s * (0.93 - 0.035 * k))):
            d.line([0, y, s, y], fill=(30, 30, 31) if k % 2 else (24, 24, 25), width=2)
    for g in (0.37, 0.46, 0.54, 0.63):   # circumferential grooves
        y = int(g * s)
        d.rectangle([0, y - 6, s, y + 6], fill=(10, 10, 10))
    for i in range(8):           # slanted sipes on the shoulders
        x = i * s // 8
        d.line([x, t0 + 4, x + 22, int(0.355 * s)], fill=(14, 14, 14), width=5)
        d.line([x + 30, int(0.645 * s), x + 52, t1 - 4], fill=(14, 14, 14), width=5)
    im = im.filter(ImageFilter.GaussianBlur(0.8))
    im.save(os.path.join(OUT, 'tyre.png'))


if __name__ == '__main__':
    os.makedirs(OUT, exist_ok=True)
    headlight()
    taillight()
    indicator()
    plate()
    mesh()
    tyre()
