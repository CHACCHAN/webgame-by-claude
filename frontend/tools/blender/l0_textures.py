"""
L0 series: our own drawing of the side logo (a blue swoosh "L" crossing a silver ring with "L0" in it, as the cars
carry it after their windows), on the body's white. Run with a Python that has Pillow:

  python3 tools/blender/l0_textures.py   ->  tools/blender/textures/l0/l0_logo.png

The plate is 1.64 m × 0.65 m on the car (parts/l0_body.py LOGO); the drawing is 1024 × 406 px, drawn 4× and reduced.
The white must stay the body's (l0_body.WHITE), since the plate sits on the painted shell.
"""
import math
import os

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'textures', 'l0', 'l0_logo.png')
WHITE = tuple(round(c * 255) for c in (0.925, 0.933, 0.940))
BLUE_DEEP = (22, 70, 160)
BLUE_LIGHT = (70, 140, 220)
SILVER = (150, 158, 166)
FONT = '/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc'

W, H = 1024, 406
SS = 4


def main():
    w, h = W * SS, H * SS
    im = Image.new('RGB', (w, h), WHITE)
    d = ImageDraw.Draw(im)
    # the ring: an ellipse leaning back, drawn as a thick polyline
    cx, cy, ax, ay, rot = 0.42 * w, 0.55 * h, 0.105 * w, 0.43 * h, math.radians(24)
    pts = []
    for k in range(361):
        t = math.radians(k)
        x, y = ax * math.cos(t), ay * math.sin(t)
        pts.append((cx + x * math.cos(rot) - y * math.sin(rot), cy + x * math.sin(rot) + y * math.cos(rot)))
    d.line(pts, fill=SILVER, width=int(0.010 * w), joint='curve')
    # the "L": a rising blade (thin at its top) and a long foot tapering to the right, shaded deep → light blue
    blade = [(0.050 * w, 0.66 * h), (0.150 * w, 0.06 * h), (0.172 * w, 0.07 * h), (0.105 * w, 0.62 * h)]
    foot = [(0.050 * w, 0.66 * h), (0.105 * w, 0.58 * h), (0.86 * w, 0.585 * h), (0.86 * w, 0.605 * h),
            (0.12 * w, 0.71 * h)]
    for poly, c in ((foot, BLUE_LIGHT), (blade, BLUE_DEEP)):
        d.polygon([(int(x), int(y)) for x, y in poly], fill=c)
    # a highlight along the foot
    d.polygon([(int(0.13 * w), int(0.625 * h)), (int(0.80 * w), int(0.592 * h)), (int(0.80 * w), int(0.598 * h)),
               (int(0.13 * w), int(0.645 * h))], fill=(130, 180, 235))
    # "L0" in the ring, leaning like the swoosh
    try:
        font = ImageFont.truetype(FONT, int(0.20 * h))
    except OSError:
        font = ImageFont.load_default()
    txt = Image.new('L', (int(0.30 * w), int(0.30 * h)), 0)
    ImageDraw.Draw(txt).text((int(0.02 * w), 0), 'L0', font=font, fill=255)
    shear = 0.25
    txt = txt.transform(txt.size, Image.AFFINE, (1, shear, -shear * txt.size[1] * 0.5, 0, 1, 0), Image.BICUBIC)
    im.paste(Image.new("RGB", txt.size, SILVER), (int(0.40 * w), int(0.27 * h)), txt)
    im = im.resize((W, H), Image.LANCZOS)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    im.save(OUT)
    print(OUT, im.size)


if __name__ == '__main__':
    main()
