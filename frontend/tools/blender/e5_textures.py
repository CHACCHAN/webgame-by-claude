"""
E5 series signs: the side LED destination display and the cars' body numbers, drawn with Noto Sans CJK (OFL) into
one atlas, tools/blender/textures/e5/e5_signs.png. Deterministic (fixed fonts, sizes and positions; no randomness).

  python3 tools/blender/e5_textures.py [outdir]      → textures/e5/ (E5) and textures/e5/h5/ (H5, --variant h5)

The display follows the layout of the real ones (photos "JREast seriesE5train direction infomation board.JPG",
"Gran ikisaki.jpg"; layout only, no pixels): a green box with the service's name in white on the left, then on the
right the line's name (owner's rule: the game's displays show the line, not a station): 東北新幹線 in white and
"Tohoku Shinkansen" in green, all as LED dots on a black panel (the Gran Class "G" is left out).
The body numbers carry the JR mark in front, as on the cars ("JRE Series-E5-E523-1 Outside-Door.jpg": "JR E523-1" in
dark grey, the mark as tall as the digits, a gap of ≈ 0.6 of their height): our own letters (Noto Sans CJK Bold,
sheared 12° to the mark's slant), not a copy of the logo artwork. Logos are allowed (owner's decision 2026-11-04).

Variants: e5 (JR East: 東北新幹線, numbers E5xx) and h5 (JR Hokkaido: 北海道新幹線, numbers H5xx; same layout).

Service logos (e5_logo.png, one per variant; logos allowed by the owner's decision 2026-11-04), our own drawings
from measured points (smooth curves through them; nothing cut or traced from a photo), on the body's green:
  e5  the E5's falcon over three waves, upright, 0.47 × 0.58 m (1 px = 1 mm): "JRE Series-E5-E523-1 Outside-Door.jpg"
      (Commons, CC BY-SA 4.0; measured on a 1 × 1 grid over the logo); the small logotype under it is left out.
  h5  the H5's white falcon (シロハヤブサ) in a broken ellipse with speed streaks, "JR HOKKAIDO RAILWAY COMPANY"
      under it, 2.2 × 1.0 m (1 px = 2 mm): measured on "H5系 ロゴマーク.JPG" and "2016-08-13 H5系ロゴマーク.jpg"
      (Commons, CC BY-SA 4.0) in a 1200 × 800 frame (the points below are in that frame).

Atlas (1024 × 512):
  (0, 0, 768, 192)        the side display (aspect 4 : 1, the panel 0.64 × 0.16 m inside its frame)
  (0, 256 + 64 k, 512, 64) body numbers with the JR mark, k = 0 E523-1, 1 E525-101, 2 E514-1 (dark grey on the
                          body's white); the text's width in pixels is printed (e5_body.NUMBER_PX)
"""
import os
import sys

from PIL import Image, ImageDraw, ImageFont

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, 'textures', 'e5')
BOLD = '/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc'
MEDIUM = '/usr/share/fonts/opentype/noto/NotoSansCJK-Medium.ttc'
JP = 0          # the .ttc's face index for Japanese (Noto Sans CJK JP)

W, H = 1024, 512
DOTS = (192, 48)        # the display's LED grid
PITCH = 4               # pixels per dot in the atlas
NUMBERS = ('E523-1', 'E525-101', 'E514-1')
VARIANTS = {
    'e5': dict(line='東北新幹線', line_en='Tohoku Shinkansen', prefix='E', sub=''),
    'h5': dict(line='北海道新幹線', line_en='Hokkaido Shinkansen', prefix='H', sub='h5'),
}
GREEN = (47, 149, 128)          # the body's green as e5_body paints it (sRGB 0.185, 0.585, 0.500)

LED_GREEN_BOX = (40, 170, 60)
LED_WHITE = (235, 235, 225)
LED_GREEN = (90, 220, 90)
PANEL = (14, 15, 16)


def _text_mask(size, items):
    """an L-mode mask at the dot grid's resolution: items = [(text, font, px, (x, y), anchor, squeeze)]"""
    m = Image.new('L', size, 0)
    for text, font, px, pos, anchor, squeeze in items:
        f = ImageFont.truetype(font, px, index=JP)
        box = f.getbbox(text, anchor='lt')
        w, h = box[2] - box[0], box[3] - box[1]
        tile = Image.new('L', (w + 4, h + 4), 0)
        ImageDraw.Draw(tile).text((2 - box[0], 2 - box[1]), text, font=f, fill=255, anchor='lt')
        if squeeze != 1.0:
            tile = tile.resize((max(1, round(tile.width * squeeze)), tile.height), Image.LANCZOS)
        x, y = pos
        if anchor == 'c':
            x -= tile.width // 2
            y -= tile.height // 2
        m.paste(tile, (x, y), tile)
    return m.point(lambda v: 255 if v >= 110 else 0)


def display(v):
    """the side display as LED dots: 192 × 48 dots, 4 px each"""
    gw, gh = DOTS
    box_w = 70
    name = _text_mask((gw, gh), [('はやぶさ', BOLD, 17, (box_w // 2, gh // 2), 'c', 0.95)])
    sq = 0.85 if len(v['line']) <= 5 else 0.72
    dest = _text_mask((gw, gh), [(v['line'], BOLD, 20, (box_w + (gw - box_w) // 2, 15), 'c', sq)])
    seat = _text_mask((gw, gh), [(v['line_en'], MEDIUM, 13, (box_w + (gw - box_w) // 2, 36), 'c', 0.85 if len(v['line_en']) < 18 else 0.78)])
    img = Image.new('RGB', (gw * PITCH, gh * PITCH), PANEL)
    d = ImageDraw.Draw(img)
    for j in range(gh):
        for i in range(gw):
            x0, y0 = i * PITCH, j * PITCH
            in_box = i < box_w and 1 <= j < gh - 1
            if name.getpixel((i, j)) and in_box:
                c = LED_WHITE
            elif in_box:
                c = LED_GREEN_BOX
            elif dest.getpixel((i, j)):
                c = LED_WHITE
            elif seat.getpixel((i, j)):
                c = LED_GREEN
            else:
                c = (24, 25, 26)            # a dot that is off
            d.rectangle((x0, y0, x0 + PITCH - 2, y0 + PITCH - 2), fill=c)
    return img


def jr_mark(cap):
    """the JR mark as tall as the digits' capitals (cap px): bold letters, sheared to the mark's slant; an L mask"""
    f = ImageFont.truetype(BOLD, round(cap / 0.733), index=JP)
    box = f.getbbox('JR', anchor='ls')
    w, h = box[2] - box[0] + 8, box[3] - box[1] + 8
    m = Image.new('L', (w, h), 0)
    ImageDraw.Draw(m).text((4 - box[0], 4 - box[1]), 'JR', font=f, fill=255, anchor='ls')
    k = 0.21                                    # tan 12°: the top leans forward (to the right)
    m = m.transform((w + round(k * h), h), Image.AFFINE, (1, k, -k * h, 0, 1, 0), Image.BICUBIC)
    return m.crop(m.getbbox())


def numbers(v):
    """[(tile, text width px)]"""
    tiles = []
    ink = (70, 72, 75)
    for text in NUMBERS:
        text = v['prefix'] + text[1:]
        t = Image.new('RGB', (512, 64), (217, 220, 221))
        f = ImageFont.truetype(MEDIUM, 46, index=JP)
        cap = f.getbbox('E', anchor='ls')
        cap_h = cap[3] - cap[1]
        mark = jr_mark(cap_h)
        base = 32 + cap_h // 2                  # the digits' baseline (their capitals centred in the row)
        t.paste(Image.new('RGB', mark.size, ink), (8, base - mark.height), mark)
        x = 8 + mark.width + round(0.6 * cap_h)
        d = ImageDraw.Draw(t)
        d.text((x, base), text, font=f, fill=ink, anchor='ls')
        tiles.append((t, round(d.textbbox((x, base), text, font=f, anchor='ls')[2]) + 8))
    return tiles


# ---------------------------------------------------------------- service logos

def _spline(pts, closed, n=10):
    """Catmull-Rom through the points"""
    m = len(pts)
    out = []
    segs = m if closed else m - 1
    for i in range(segs):
        p0 = pts[(i - 1) % m] if closed or i > 0 else pts[0]
        p1, p2 = pts[i], pts[(i + 1) % m]
        p3 = pts[(i + 2) % m] if closed or i + 2 < m else pts[-1]
        for k in range(n):
            t = k / n
            out.append(tuple(0.5 * (2 * p1[j] + (-p0[j] + p2[j]) * t + (2 * p0[j] - 5 * p1[j] + 4 * p2[j] - p3[j]) * t * t
                                    + (-p0[j] + 3 * p1[j] - 3 * p2[j] + p3[j]) * t ** 3) for j in (0, 1)))
    if not closed:
        out.append(tuple(pts[-1]))
    return out


def _ribbon(pts, w0, w1, n=10):
    """a closed outline round a curve through pts, its half width from w0 to w1"""
    c = _spline(pts, False, n)
    left, right = [], []
    for k, (x, y) in enumerate(c):
        a, b = c[max(k - 1, 0)], c[min(k + 1, len(c) - 1)]
        dx, dy = b[0] - a[0], b[1] - a[1]
        L = (dx * dx + dy * dy) ** 0.5 or 1.0
        w = w0 + (w1 - w0) * k / (len(c) - 1)
        left.append((x - dy / L * w, y + dx / L * w))
        right.append((x + dy / L * w, y - dx / L * w))
    return left + right[::-1]


class _Pen:
    """polygons drawn 4× oversized, then reduced (anti-aliased); points given in the source frame"""

    def __init__(self, size, frame, scale, offset, bg):
        self.ss = 4
        self.size = size
        self.img = Image.new('RGB', (size[0] * self.ss, size[1] * self.ss), bg)
        self.d = ImageDraw.Draw(self.img)
        self.k = scale * self.ss
        self.o = offset

    def P(self, pts, dx=0.0, dy=0.0):
        return [((x - self.o[0] + dx) * self.k, (y - self.o[1] + dy) * self.k) for x, y in pts]

    def poly(self, pts, colour, dx=0.0, dy=0.0):
        self.d.polygon(self.P(pts, dx, dy), fill=colour)

    def done(self):
        return self.img.resize(self.size, Image.LANCZOS)


# E5: (u, v) on the logo's box (u right, v down), measured on a 1 × 1 grid
E5_WING = [(0.73, 0.007), (0.58, 0.19), (0.47, 0.37), (0.40, 0.55), (0.37, 0.71), (0.40, 0.82), (0.20, 0.79),
           (0.0, 0.72), (0.07, 0.62), (0.19, 0.46), (0.33, 0.28), (0.51, 0.12)]
E5_TAIL = [(0.18, 0.79), (0.42, 0.80), (0.50, 0.84), (0.46, 0.99)]
E5_ARC = [(0.07, 0.30), (0.12, 0.17), (0.25, 0.06), (0.45, 0.01), (0.66, 0.0), (0.62, 0.03), (0.45, 0.045),
          (0.28, 0.10), (0.16, 0.20), (0.10, 0.31)]
E5_WAVES = [[(0.35, 0.52), (0.58, 0.53), (0.79, 0.48), (0.93, 0.38)],
            [(0.37, 0.62), (0.63, 0.64), (0.84, 0.58), (0.98, 0.48)],
            [(0.40, 0.71), (0.65, 0.74), (0.86, 0.69), (1.00, 0.61)]]


def logo_e5():
    W_, H_ = 470, 580                       # 1 px = 1 mm
    pad = 0.04
    pen = _Pen((W_, H_), None, 1.0, (0, 0), GREEN)
    sx, sy = W_ * (1 - 2 * pad), H_ * (1 - 2 * pad)
    U = lambda pts: [(pad * W_ + u * sx, pad * H_ + v * sy) for u, v in pts]     # noqa: E731
    white, blue = (227, 232, 237), (56, 110, 194)
    shapes = [_spline(U(E5_WING), True), U(E5_TAIL)] + [_ribbon(U(w), 0.026 * sy, 0.016 * sy) for w in E5_WAVES]
    for sh in shapes:
        pen.poly(sh, blue, -6, 10)          # the blue shading along the lower left edges
    for sh in shapes:
        pen.poly(sh, white)
    pen.poly(_spline(U(E5_ARC), True), blue)
    return pen.done()


# H5: points in the 1200 × 800 frame of the close-up photo (the logo spans x 45..1160, y 130..615)
H5_BODY = [(275, 400), (340, 385), (420, 355), (447, 318), (455, 293), (472, 287), (462, 312), (470, 333), (500, 338),
           (560, 318), (625, 268), (672, 210), (705, 150), (738, 133), (718, 175), (702, 230), (705, 285), (735, 330),
           (800, 362), (900, 382), (1000, 392), (1058, 396), (1058, 405), (275, 405)]
H5_HEAD = [(128, 472), (148, 433), (198, 417), (330, 412), (330, 421), (205, 428), (168, 446), (160, 470)]
H5_STREAKS = [([(198, 420), (450, 417), (700, 416), (1005, 416)], 4.5, 4.0),
              ([(62, 550), (200, 497), (400, 455), (700, 440), (1005, 438)], 6.0, 4.5),
              ([(102, 566), (270, 525), (500, 478), (800, 458), (1010, 456)], 6.0, 4.5),
              ([(482, 602), (525, 540), (660, 498), (850, 471), (1012, 463)], 7.0, 4.5)]
H5_DASH_Y = (400, 418, 439, 457)
H5_ARC_R = [(1130, 368), (1080, 296), (1000, 233), (900, 191), (760, 164)]
H5_ARC_L = [(655, 155), (500, 158), (330, 185), (180, 240), (85, 315), (47, 385), (56, 450), (82, 512)]


def logo_h5():
    W_, H_ = 1100, 500                      # 1 px = 2 mm: 2.2 × 1.0 m
    k = 1080 / 1115.0
    pen = _Pen((W_, H_), None, k, (45 - 10 / k, 130 - 10 / k), GREEN)
    silver, shade, arc = (214, 214, 228), (66, 76, 104), (150, 156, 182)
    shapes = [H5_BODY, H5_HEAD] + [_ribbon(p, w0, w1) for p, w0, w1 in H5_STREAKS]
    for y, j in zip(H5_DASH_Y, range(4)):
        x0 = 1022 + 12 * (3 - j) - 14
        for n, (a, w) in enumerate(((x0, 26), (x0 + 38, 20), (x0 + 70, 15))):
            h = 7 - n
            shapes.append([(a + 6, y - h), (a + w + 6, y - h), (a + w - 6, y + h), (a - 6, y + h)])
    arcs = [_ribbon(H5_ARC_R, 1.5, 6.0), _ribbon(H5_ARC_L, 6.5, 2.0)]
    for sh in shapes + arcs:
        pen.poly(sh, shade, 4, 5)           # the dark relief under each part
    for sh in arcs:
        pen.poly(sh, arc)
    for sh in shapes:
        pen.poly(sh, silver)
    img = pen.done()
    # "JR  HOKKAIDO RAILWAY COMPANY" under the streaks (our letters)
    cap = round(18 * k)
    f = ImageFont.truetype(MEDIUM, round(cap / 0.733), index=JP)
    d = ImageDraw.Draw(img)
    x_jr, base = round((615 - 45) * k + 10), round((611 - 130) * k + 10)
    mark = jr_mark(cap)
    img.paste(Image.new('RGB', mark.size, (226, 232, 234)), (x_jr, base - mark.height), mark)
    d.text((round((695 - 45) * k + 10), base), 'HOKKAIDO RAILWAY COMPANY', font=f, fill=(226, 232, 234), anchor='ls')
    return img


def main():
    for name, v in VARIANTS.items():
        out = os.path.join(OUT, v['sub']) if v['sub'] else OUT
        os.makedirs(out, exist_ok=True)
        atlas = Image.new('RGB', (W, H), (217, 220, 221))
        atlas.paste(display(v), (0, 0))
        for k, (t, w) in enumerate(numbers(v)):
            atlas.paste(t, (0, 256 + 64 * k))
            print(name, 'number', v['prefix'] + NUMBERS[k][1:], 'width px', w)
        path = os.path.join(out, 'e5_signs.png')
        atlas.save(path, optimize=True)
        logo = logo_e5() if name == 'e5' else logo_h5()
        logo.save(os.path.join(out, 'e5_logo.png'), optimize=True)
        print('wrote', path, atlas.size, 'logo', logo.size)


if __name__ == '__main__':
    main()
