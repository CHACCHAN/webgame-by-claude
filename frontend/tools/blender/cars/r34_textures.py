"""
Textures for the R34 (deterministic, PIL on the host; no photo pixels):

  python3 tools/blender/cars/r34_textures.py      -> tools/blender/textures/r34/*.png

headlight.png  the lamp unit seen through its clear lens: inner projector, high-beam reflector, small outer lamp
               (bright parts are the glow pattern at night)
taillight.png  two round lamps side by side: left = outer lamp (red centre), right = inner lamp (amber centre)
plate.png      a white Japanese plate with fictional text (朧 300 / さ 12-34), Noto Sans CJK (OFL)
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


def headlight(w=1024, h=256):
    """one lamp unit behind its clear lens, u = 0 at the grille, 1 at the wing corner (the lens's bounding box):
    projector low beam, big multi-facet high-beam reflector, small outer clearance reflector, grey housing"""
    im = Image.new('RGB', (w, h), (40, 42, 46))
    d = ImageDraw.Draw(im)
    for y in range(h):                       # housing: mid grey, a lighter band across the middle
        t = abs(y / h - 0.48) * 2
        d.line([(0, y), (w, y)], fill=lerp((132, 135, 141), (74, 76, 81), t ** 1.4))
    for u, r in ((0.22, 0.36), (0.60, 0.46), (0.88, 0.26)):     # chrome bowls in grey surrounds
        cx, cy, rr = u * w, 0.50 * h, r * h
        radial(d, cx, cy, rr * 1.15, (104, 107, 113), (78, 80, 86))
        radial(d, cx, cy, rr, (214, 217, 223), (110, 113, 120))
    # projector (low beam): chrome cowl rings and a dark glass lens
    cx, cy, rr = 0.22 * w, 0.50 * h, 0.36 * h
    for ring in range(3):
        k = 0.95 - ring * 0.09
        d.ellipse([cx - rr * k, cy - rr * k, cx + rr * k, cy + rr * k], outline=(150, 154, 162), width=2)
    radial(d, cx, cy, rr * 0.58, (200, 206, 218), (22, 25, 32))
    d.ellipse([cx - rr * 0.58, cy - rr * 0.58, cx + rr * 0.58, cy + rr * 0.58], outline=(18, 18, 22), width=5)
    # high beam: the big multi-facet reflector with its bulb shield
    cx, rr = 0.60 * w, 0.46 * h
    for a in range(0, 360, 30):
        t = math.radians(a)
        d.line([(cx + rr * 0.25 * math.cos(t), cy + rr * 0.25 * math.sin(t)),
                (cx + rr * 0.97 * math.cos(t), cy + rr * 0.97 * math.sin(t))], fill=(120, 124, 132), width=2)
    for ring in (0.45, 0.72):
        d.ellipse([cx - rr * ring, cy - rr * ring, cx + rr * ring, cy + rr * ring], outline=(130, 134, 142), width=2)
    radial(d, cx, cy, rr * 0.2, (235, 235, 238), (140, 142, 148))
    # clearance lamp at the outer end
    cx, rr = 0.88 * w, 0.26 * h
    radial(d, cx, cy, rr * 0.25, (225, 225, 228), (120, 122, 128))
    # the lens's black screen print along the lower and upper edges
    d.rectangle([0, int(h * 0.93), w, h], fill=(30, 30, 33))
    d.rectangle([0, 0, w, int(h * 0.04)], fill=(36, 36, 40))
    im = im.filter(ImageFilter.GaussianBlur(1.0))
    im.save(os.path.join(OUT, 'headlight.png'))


def taillight(s=512):
    im = Image.new('RGB', (2 * s, s), (40, 4, 4))
    d = ImageDraw.Draw(im)
    for k, centre in enumerate(((150, 12, 10), (225, 120, 20))):
        cx, cy, r = k * s + s / 2, s / 2, s * 0.48
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(60, 6, 6))
        radial(d, cx, cy, r * 0.97, (200, 22, 18), (120, 8, 8))
        # radial ribs of the outer ring
        for a in range(0, 360, 6):
            t = math.radians(a)
            d.line([(cx + r * 0.62 * math.cos(t), cy + r * 0.62 * math.sin(t)),
                    (cx + r * 0.95 * math.cos(t), cy + r * 0.95 * math.sin(t))], fill=(150, 12, 10), width=3)
        # dark ring, then the centre lamp
        d.ellipse([cx - r * 0.60, cy - r * 0.60, cx + r * 0.60, cy + r * 0.60], fill=(70, 6, 6))
        radial(d, cx, cy, r * 0.52, lerp(centre, (255, 255, 255), 0.25), centre)
        for ring in (0.18, 0.32, 0.45):
            d.ellipse([cx - r * ring, cy - r * ring, cx + r * ring, cy + r * ring],
                      outline=lerp(centre, (0, 0, 0), 0.3), width=3)
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
    plate()
    mesh()
    tyre()
