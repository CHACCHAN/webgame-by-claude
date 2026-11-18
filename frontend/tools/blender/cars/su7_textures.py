"""
Textures of the SU7 (game id `su7`), drawn with PIL (deterministic; no photo pixels):

  python3 tools/blender/cars/su7_textures.py      -> tools/blender/textures/su7/*.png

Both lamp textures are drawn over the box of the lens's outline as su7_details lays it on the body (su7_data.HL in the
head lamp's frame, su7_data.TL from behind), so what is inside follows the outline when that is traced anew:

- headlamp.png   the 'water drop' lens (k12): a dark housing under clear glass, four lens units (two above, two
                 below the light guide that runs from the outer side to the inner tip), the bright hook at
                 the outer top and the bright strip down the outer side and along the bottom; every one of
                 them a traced point carried onto the body (su7_data HLU / HLG / HLS)
- taillamp.png   the full-width band: dark red under the cover, one thin bright line along the lower edge that turns
                 round each end and runs back along the top of the end lobe to where the lobe begins (k07, lit)
- plate.png      the game's plate (朧 300 さ 12-34, as on the other cars: a made-up registration)
"""
import math
import os
import sys

from PIL import Image, ImageDraw, ImageFilter, ImageFont

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import su7_data as D  # noqa: E402

OUT = os.path.join(os.path.dirname(HERE), 'textures', 'su7')
FONT = '/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc'
FONT_M = '/usr/share/fonts/opentype/noto/NotoSansCJK-Medium.ttc'


def _norm(v):
    n = math.sqrt(sum(c * c for c in v))
    return tuple(c / n for c in v)


def _dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _frame():
    d = _norm(D.HL_D)
    e1 = _norm(tuple(c - d[i] * _dot(D.HL_E1, d) for i, c in enumerate(D.HL_E1)))
    return d, e1, _norm(_cross(d, e1))


def head_uv(p):
    """a point of the lamp in its frame (su7_details.head_frame), metres (u toward the outer side, v up)"""
    _d, e1, e2 = _frame()
    q = tuple(p[i] - D.HL_C[i] for i in range(3))
    return (_dot(q, e1), _dot(q, e2))


def head_outline():
    return [head_uv(p) for p in D.HL]


class Box:
    """metres in the outline's box -> pixels (v up -> rows down)"""

    def __init__(self, uv, W, H):
        self.u0, self.u1 = min(p[0] for p in uv), max(p[0] for p in uv)
        self.v0, self.v1 = min(p[1] for p in uv), max(p[1] for p in uv)
        self.W, self.H = W, H

    def px(self, p):
        return ((p[0] - self.u0) / (self.u1 - self.u0) * self.W, (1 - (p[1] - self.v0) / (self.v1 - self.v0)) * self.H)

    def at(self, a, b):
        """a point by its share of the box (0..1 across, 0..1 up)"""
        return (self.u0 + (self.u1 - self.u0) * a, self.v0 + (self.v1 - self.v0) * b)

    def w(self, metres):
        """a line width in pixels (the box is not square: by the smaller scale)"""
        return max(1, int(round(metres * min(self.W / (self.u1 - self.u0), self.H / (self.v1 - self.v0)))))


def _inset(poly, d):
    """the closed outline moved inward by d metres, by its vertex normals"""
    n = len(poly)
    area = sum(poly[i - 1][0] * poly[i][1] - poly[i][0] * poly[i - 1][1] for i in range(n))
    sgn = 1 if area > 0 else -1
    out = []
    for i in range(n):
        a, b = poly[i - 1], poly[(i + 1) % n]
        tx, ty = b[0] - a[0], b[1] - a[1]
        L = math.hypot(tx, ty) or 1.0
        out.append((poly[i][0] - sgn * ty / L * d, poly[i][1] + sgn * tx / L * d))
    return out


def headlamp(w=512, h=256, k=3):
    poly = head_outline()
    bx = Box(poly, w * k, h * k)
    im = Image.new('RGB', (w * k, h * k), (16, 19, 24))
    dr = ImageDraw.Draw(im)
    dr.polygon([bx.px(p) for p in poly], fill=(34, 39, 47))
    dr.polygon([bx.px(p) for p in _inset(poly, 0.012)], fill=(21, 25, 31))
    # the light guide: a pale bar from the outer side, thinning to the inner tip
    g = [bx.px(head_uv(p)) for p in D.HLG]
    for i in range(len(g) - 1):
        wd = 0.017 - 0.011 * i / max(1, len(g) - 2)
        dr.line([g[i], g[i + 1]], fill=(196, 206, 220), width=bx.w(wd))
        r = bx.w(wd) / 2
        dr.ellipse([g[i + 1][0] - r, g[i + 1][1] - r, g[i + 1][0] + r, g[i + 1][1] + r], fill=(196, 206, 220))
    # the lens units: a bright frame, the lens in it
    sx, sy = w * k / (bx.u1 - bx.u0), h * k / (bx.v1 - bx.v0)
    for p in D.HLU:
        x, y = bx.px(head_uv(p))
        rx, ry = 0.021 * sx, 0.019 * sy
        dr.rounded_rectangle([x - rx, y - ry, x + rx, y + ry], radius=min(rx, ry) * 0.4, fill=(52, 58, 66),
                             outline=(206, 212, 220), width=max(2, int(1.3 * k)))
        dr.rounded_rectangle([x - rx * 0.62, y - ry * 0.6, x + rx * 0.62, y + ry * 0.6], radius=min(rx, ry) * 0.3,
                             fill=(150, 162, 178))
        dr.ellipse([x - rx * 0.3, y - ry * 0.34, x + rx * 0.12, y + ry * 0.1], fill=(236, 242, 250))
    # the bright lines: the hook at the outer top, the strip down the outer side and along the bottom
    for ln in D.HLS:
        if len(ln) > 1:
            dr.line([bx.px(head_uv(p)) for p in ln], fill=(255, 255, 255), width=bx.w(0.008), joint='curve')
    im = im.filter(ImageFilter.GaussianBlur(0.5 * k))
    return im.resize((w, h), Image.LANCZOS)


def taillamp(w=2048, h=128, k=2):
    za, r = D.TL_AXIS                                        # su7_details.Wrap: u = -r x bearing, the car's left at u < 0
    half = [(-r * math.atan2(x, za - z), y) for x, y, z in D.TL]
    full = half + [(-u, v) for u, v in reversed(half)][1:-1]
    bx = Box(full, w * k, h * k)
    im = Image.new('RGB', (w * k, h * k), (40, 4, 6))
    dr = ImageDraw.Draw(im)
    dr.polygon([bx.px(p) for p in full], fill=(74, 7, 9))
    # the light line: the outline moved in, from the kink of one end lobe round its tip, along the lower edge to the
    # other end, round that tip and back to its kink
    ins = _inset(full, 0.011)
    n = len(half)
    left = ins[D.TL_KINK:n]                                 # kink -> tip -> centre bottom (the left half)
    right = [(-u, v) for u, v in reversed(left)]
    dr.line([bx.px(p) for p in left + right[1:]], fill=(255, 46, 32), width=bx.w(0.009), joint='curve')
    im = im.filter(ImageFilter.GaussianBlur(0.5 * k))
    return im.resize((w, h), Image.LANCZOS)


def plate(k=4):
    w, h = 512, 256
    img = Image.new('RGB', (w * k, h * k), (246, 247, 244))
    d = ImageDraw.Draw(img)
    green = (18, 92, 52)
    d.rounded_rectangle([6 * k, 6 * k, (w - 6) * k, (h - 6) * k], radius=14 * k, outline=green, width=5 * k)
    for x in (130, 382):
        d.ellipse([(x - 9) * k, 26 * k, (x + 9) * k, 44 * k], fill=(200, 202, 200), outline=(150, 150, 150), width=k)
    d.text((256 * k, 52 * k), '朧 300', font=ImageFont.truetype(FONT_M, 58 * k, index=0), fill=green, anchor='mm')
    d.text((62 * k, 172 * k), 'さ', font=ImageFont.truetype(FONT_M, 64 * k, index=0), fill=green, anchor='mm')
    d.text((300 * k, 166 * k), '12-34', font=ImageFont.truetype(FONT, 150 * k, index=0), fill=green, anchor='mm')
    return img.resize((w, h), Image.LANCZOS)


def main():
    os.makedirs(OUT, exist_ok=True)
    headlamp().save(os.path.join(OUT, 'headlamp.png'))
    taillamp().save(os.path.join(OUT, 'taillamp.png'))
    plate().save(os.path.join(OUT, 'plate.png'))
    print('wrote', OUT)


if __name__ == '__main__':
    main()
