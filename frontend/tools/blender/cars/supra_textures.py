"""
Textures of the Supra (game id `supra`), drawn with PIL on the host (deterministic; no photo pixels):

  python3 tools/blender/cars/supra_textures.py      → tools/blender/textures/supra/*.png

- plate.png      Japanese private-car plate, white, green lettering, fictional registration 「朧 300 さ 12-34」
                 (Noto Sans CJK JP, OFL)
- headlamp.png   the head lamp unit under its cover: smoked housing, big chrome reflector inboard, two projector
                 lenses in chrome rings outboard (layout from the late-model photos); bright bowls = the night glow
- taillamp.png   one round tail lamp lens: rings and a brighter centre
- lamps.png      atlas: front indicator (clear lens, amber bulb), amber lens, clear reverse lens, fog lamp,
                 high-mount stop lamp, red reflector
- tyre.png       tyre: sidewalls with fine rings, tread blocks (u round the tyre, repeated; v across, inner → outer)
"""
import math
import os
import sys

from PIL import Image, ImageDraw, ImageFilter, ImageFont

sys.dont_write_bytecode = True
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'textures', 'supra')
FONT = '/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc'
FONT_M = '/usr/share/fonts/opentype/noto/NotoSansCJK-Medium.ttc'
JP = 0          # index of the JP face in the .ttc


def font(path, size):
    return ImageFont.truetype(path, size, index=JP)


def ss(w, h, k=4, bg=(0, 0, 0)):
    """a supersampled canvas"""
    return Image.new('RGB', (w * k, h * k), bg), k


def down(img, k):
    return img.resize((img.width // k, img.height // k), Image.LANCZOS)


def plate():
    w, h = 512, 256
    img, k = ss(w, h, bg=(246, 247, 244))
    d = ImageDraw.Draw(img)
    green = (18, 92, 52)
    d.rounded_rectangle([6 * k, 6 * k, (w - 6) * k, (h - 6) * k], radius=14 * k, outline=green, width=5 * k)
    # bolt holes
    for x in (130, 382):
        d.ellipse([(x - 9) * k, 26 * k, (x + 9) * k, 44 * k], fill=(200, 202, 200), outline=(150, 150, 150), width=k)
    f1 = font(FONT_M, 58 * k)
    d.text((256 * k, 52 * k), '朧 300', font=f1, fill=green, anchor='mm')
    f2 = font(FONT_M, 64 * k)
    d.text((62 * k, 172 * k), 'さ', font=f2, fill=green, anchor='mm')
    f3 = font(FONT, 150 * k)
    d.text((300 * k, 166 * k), '12-34', font=f3, fill=green, anchor='mm')
    down(img, k).save(os.path.join(OUT, 'plate.png'))


def _radial(d, cx, cy, r, stops, k):
    """concentric fills: stops = [(fraction of r, colour)] from outside in"""
    for f, c in stops:
        rr = r * f
        d.ellipse([(cx - rr) * k, (cy - rr) * k, (cx + rr) * k, (cy + rr) * k], fill=c)


def headlamp():
    """the unit as laid on the body (supra_details.headlamp_outline: u -0.250..0.252 m, v -0.082..0.088 m): a smoked
    grey-silver housing, a big chrome reflector inboard, two projector lenses in chrome rings outboard"""
    w, h = 512, 176
    img, k = ss(w, h, bg=(120, 125, 132))
    d = ImageDraw.Draw(img)
    for i in range(h):
        t = i / h
        c = int(104 + 46 * math.exp(-((t - 0.22) / 0.16) ** 2) + 16 * (1 - t))
        d.line([(0, i * k), (w * k, i * k)], fill=(c, c + 4, c + 9), width=k)

    def px(u, v):
        return (u + 0.250) / 0.502 * w, (0.088 - v) / 0.170 * h
    big = px(-0.135, 0.004) + (57,)
    mid = px(0.015, 0.010) + (45,)
    small = px(0.145, 0.014) + (36,)
    # chrome rings round all three
    for cx, cy, r in (big, mid, small):
        _radial(d, cx, cy, r + 7, [(1.0, (84, 88, 96)), (0.97, (222, 226, 232)), (0.90, (150, 156, 164)),
                                   (0.86, (236, 240, 244))], k)
    # inboard: a faceted chrome bowl with the bulb shield in the middle
    cx, cy, r = big
    _radial(d, cx, cy, r, [(1.0, (196, 202, 210)), (0.82, (232, 236, 240)), (0.60, (205, 210, 218)),
                           (0.36, (248, 248, 250)), (0.20, (255, 255, 252))], k)
    for a in range(0, 360, 24):
        x1 = cx + math.cos(math.radians(a)) * r * 0.40
        y1 = cy + math.sin(math.radians(a)) * r * 0.40
        x2 = cx + math.cos(math.radians(a)) * r * 0.97
        y2 = cy + math.sin(math.radians(a)) * r * 0.97
        d.line([(x1 * k, y1 * k), (x2 * k, y2 * k)], fill=(176, 182, 190), width=2 * k)
    # the projectors: a dark throat, a clear domed lens with a bright rim and a highlight
    for cx, cy, r in (mid, small):
        _radial(d, cx, cy, r, [(1.0, (70, 74, 82)), (0.84, (150, 160, 172)), (0.70, (196, 206, 218)),
                               (0.45, (225, 232, 240)), (0.22, (250, 252, 255))], k)
        hx, hy = cx - r * 0.35, cy - r * 0.38
        _radial(d, hx, hy, r * 0.22, [(1.0, (240, 244, 250)), (0.5, (255, 255, 255))], k)
    img = img.filter(ImageFilter.GaussianBlur(k * 0.7))
    down(img, k).save(os.path.join(OUT, 'headlamp.png'))


def taillamp():
    w = h = 256
    img, k = ss(w, h, bg=(60, 6, 8))
    d = ImageDraw.Draw(img)
    c = w / 2
    _radial(d, c, c, 126, [(1.0, (40, 4, 6)), (0.94, (150, 14, 16)), (0.86, (205, 30, 26)), (0.72, (160, 16, 18)),
                           (0.66, (220, 40, 34)), (0.50, (175, 20, 20)), (0.44, (235, 60, 50)), (0.30, (190, 28, 26)),
                           (0.22, (250, 90, 70))], k)
    for a in range(0, 360, 15):
        x2 = c + math.cos(math.radians(a)) * 118
        y2 = c + math.sin(math.radians(a)) * 118
        d.line([(c * k, c * k), (x2 * k, y2 * k)], fill=(120, 10, 12), width=k)
    img = img.filter(ImageFilter.GaussianBlur(k * 0.6))
    down(img, k).save(os.path.join(OUT, 'taillamp.png'))


# atlas cells of lamps.png: name → (u0, v0, u1, v1) in UV (v up)
CELLS = {
    'indicator_front': (0.0, 0.75, 0.5, 1.0),
    'amber': (0.5, 0.75, 1.0, 1.0),
    'reverse': (0.0, 0.5, 0.25, 0.75),
    'fog': (0.25, 0.5, 0.5, 0.75),
    'stop': (0.5, 0.5, 1.0, 0.75),
    'reflector': (0.0, 0.25, 0.5, 0.5),
    'amber_round': (0.5, 0.25, 0.75, 0.5),
}


def lamps():
    s = 512
    img, k = ss(s, s, bg=(30, 30, 32))
    d = ImageDraw.Draw(img)

    def box(name):
        u0, v0, u1, v1 = CELLS[name]
        return u0 * s, (1 - v1) * s, u1 * s, (1 - v0) * s

    # front indicator: clear prismatic lens, amber bulb shell in the middle third, chrome reflector
    x0, y0, x1, y1 = box('indicator_front')
    d.rectangle([x0 * k, y0 * k, x1 * k, y1 * k], fill=(214, 218, 222))
    for i in range(int(x0), int(x1), 6):
        d.line([(i * k, y0 * k), (i * k, y1 * k)], fill=(236, 238, 240), width=2 * k)
    cx, cy = (x0 + x1) / 2 - 20, (y0 + y1) / 2
    _radial(d, cx, cy, 48, [(1.0, (190, 120, 40)), (0.8, (255, 150, 30)), (0.5, (255, 200, 90))], k)
    # amber lens
    x0, y0, x1, y1 = box('amber')
    d.rectangle([x0 * k, y0 * k, x1 * k, y1 * k], fill=(235, 120, 20))
    for i in range(int(y0), int(y1), 8):
        d.line([(x0 * k, i * k), (x1 * k, i * k)], fill=(255, 160, 50), width=2 * k)
    # reverse: clear round lens with rings
    x0, y0, x1, y1 = box('reverse')
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    d.rectangle([x0 * k, y0 * k, x1 * k, y1 * k], fill=(40, 40, 44))
    _radial(d, cx, cy, 63, [(1.0, (170, 174, 180)), (0.9, (225, 228, 232)), (0.7, (196, 200, 206)),
                            (0.5, (240, 242, 245)), (0.3, (210, 214, 220)), (0.15, (250, 250, 252))], k)
    # fog lamp: clear lens over a chrome bowl
    x0, y0, x1, y1 = box('fog')
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    d.rectangle([x0 * k, y0 * k, x1 * k, y1 * k], fill=(40, 40, 44))
    _radial(d, cx, cy, 63, [(1.0, (120, 124, 130)), (0.88, (230, 233, 236)), (0.55, (250, 250, 245)), (0.2, (255, 252, 230))], k)
    for i in range(int(x0) + 8, int(x1) - 4, 9):
        d.line([(i * k, (y0 + 10) * k), (i * k, (y1 - 10) * k)], fill=(205, 208, 212), width=k)
    # high-mount stop lamp: red strip with LED-like dots
    x0, y0, x1, y1 = box('stop')
    d.rectangle([x0 * k, y0 * k, x1 * k, y1 * k], fill=(110, 10, 12))
    for i in range(14):
        cx = x0 + (i + 0.5) * (x1 - x0) / 14
        _radial(d, cx, (y0 + y1) / 2, 8, [(1.0, (200, 30, 26)), (0.5, (250, 80, 60))], k)
    # red reflector
    x0, y0, x1, y1 = box('reflector')
    d.rectangle([x0 * k, y0 * k, x1 * k, y1 * k], fill=(140, 12, 14))
    for i in range(int(x0), int(x1), 10):
        for j in range(int(y0), int(y1), 10):
            d.polygon([(i * k, (j + 5) * k), ((i + 5) * k, j * k), ((i + 10) * k, (j + 5) * k), ((i + 5) * k, (j + 10) * k)],
                      fill=(175, 22, 22))
    # amber round (rear indicator)
    x0, y0, x1, y1 = box('amber_round')
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    d.rectangle([x0 * k, y0 * k, x1 * k, y1 * k], fill=(60, 30, 6))
    _radial(d, cx, cy, 63, [(1.0, (170, 80, 10)), (0.9, (240, 130, 25)), (0.7, (205, 105, 20)), (0.5, (250, 150, 40)),
                            (0.3, (215, 115, 25)), (0.15, (255, 175, 70))], k)
    img = img.filter(ImageFilter.GaussianBlur(k * 0.5))
    down(img, k).save(os.path.join(OUT, 'lamps.png'))


def tyre():
    w, h = 512, 256
    img, k = ss(w, h, bg=(22, 22, 23))
    d = ImageDraw.Draw(img)
    # v (rows, top = v 1 = outer bead): sidewall 0-0.3, shoulder, tread 0.36-0.64, shoulder, sidewall 0.7-1
    def row(v):
        return (1 - v) * h
    for v0, v1, c in ((0.0, 0.30, (27, 27, 28)), (0.70, 1.0, (27, 27, 28))):
        d.rectangle([0, row(v1) * k, w * k, row(v0) * k], fill=c)
        for t in range(6):
            vv = v0 + (v1 - v0) * (0.15 + 0.13 * t)
            d.line([(0, row(vv) * k), (w * k, row(vv) * k)], fill=(33, 33, 34), width=k)
    # tread: blocks across 4 ribs, staggered; grooves darker
    d.rectangle([0, row(0.70) * k, w * k, row(0.30) * k], fill=(31, 31, 32))
    ribs = [(0.30, 0.40), (0.43, 0.49), (0.52, 0.58), (0.61, 0.70)]
    pitch = w / 8
    for ri, (a, b) in enumerate(ribs):
        for i in range(9):
            x = i * pitch + (pitch / 2 if ri % 2 else 0) - pitch
            d.line([(x * k, row(b) * k), ((x + pitch * 0.25) * k, row(a) * k)], fill=(14, 14, 15), width=3 * k)
    for a, b in ((0.40, 0.43), (0.49, 0.52), (0.58, 0.61)):
        d.rectangle([0, row(b) * k, w * k, row(a) * k], fill=(12, 12, 13))
    img = img.filter(ImageFilter.GaussianBlur(k * 0.5))
    down(img, k).save(os.path.join(OUT, 'tyre.png'))


def main():
    os.makedirs(OUT, exist_ok=True)
    plate()
    headlamp()
    taillamp()
    lamps()
    tyre()
    print('wrote', sorted(os.listdir(OUT)))


if __name__ == '__main__':
    main()
