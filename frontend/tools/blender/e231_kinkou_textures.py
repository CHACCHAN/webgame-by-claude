#!/usr/bin/env python3
"""Signage textures for the E231 近郊タイプ (1000番台, Shōnan colours) Blender model, e231.py --variant kinkou
(parts/e231_kinkou_build.py). The service: an Ueno-Tokyo Line train (displays show the line name, never a station):

  led_dest.png  / _off   0.80 x 0.20 m  128 x 32 dots  front 3-colour LED: 上野東京ライン over Ueno-Tōkyō Line, both
                                                       orange (Commons "Ueno tokyo line E231 the front indicate.JPG",
                                                       "JRE Series-E231 K04.jpg", "Treinstel E231 U514 ... 2026":
                                                       the English line is the same orange)
  led_runno.png / _off   0.42 x 0.12 m   64 x 16 dots  front run-number box, lower left of the windscreen: 1871E
                                                       (E-suffix runs are the Tōhoku / Takasaki line through trains)
  led_side.png  / _off   0.62 x 0.14 m  128 x 24 dots  side 3-colour LED: 上野東京ライン in one row of orange
                                                       (Commons "E231系 側面方向幕 東海道線.JPG": one row, dark panel)
  set_plate.png          0.26 x 0.10 m                 Kōzu add-on set plate behind the windscreen: "S-35" (a white
                                                       plate with black lettering as on S-13 / K-04 / K-38; the real
                                                       add-on sets end at S-34, so the number is our own)
  jr_mark.png            RGBA, the JR mark (white on transparent), drawn with Noto Sans CJK Bold, w:h ≈ 1.75
  numbers_<car>.png      RGBA, black lettering on transparent, 1000 px/m: クハE231-8072, モハE231-1172,
                         クハE230-6072 (the add-on set's 15 / 13 / 11号車; numbers our own, beyond the built ranges)

Host python3 + PIL only (no numpy). Deterministic: no random numbers, same bytes every run.
    python3 frontend/tools/blender/e231_kinkou_textures.py [outdir]
Default output: frontend/tools/blender/textures/e231/kinkou/.
Fonts: Noto Sans CJK JP (SIL OFL 1.1) only. The LED dot-matrix helpers come from keikyu1000_textures.py.
"""
import os
import sys

sys.dont_write_bytecode = True
from PIL import Image, ImageDraw, ImageFont  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import keikyu1000_textures as KT  # noqa: E402

OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, 'textures', 'e231', 'kinkou')

ORANGE = (255, 96, 10)        # the 3-colour LED's orange (reads red-orange on photos)
FONT_BOLD = '/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc'
FONT_MED = '/usr/share/fonts/opentype/noto/NotoSansCJK-Medium.ttc'

LINE = '上野東京ライン'
LINE_EN = 'Ueno-Tōkyō Line'
RUN = '1871E'
SET = 'S-35'
NUMBERS = {'car0': 'クハE231-8072', 'car1': 'モハE231-1172', 'car2': 'クハE230-6072'}


def led_dest():
    """the line name over its English name, both orange; 7 characters fill the width"""
    W, H, C, R = 0.80, 0.20, 128, 32
    m = KT.Matrix(W, H, C, R)
    n = len(LINE)
    pitch = 0.104
    cw, ch = 0.098, 0.124
    total = (n - 1) * pitch + cw
    m.text_cjk(LINE, (W - total) / 2, 0.010, cw, ch, pitch, ORANGE)
    m.text_fit(LINE_EN, (W - 0.46) / 2, 0.150, 0.46, 0.038, ORANGE, track=0.06)
    m.dots_from_layers()
    return m


def led_runno():
    W, H, C, R = 0.42, 0.12, 64, 16
    m = KT.Matrix(W, H, C, R)
    n = len(RUN)
    pitch, cw = 0.074, 0.060
    total = (n - 1) * pitch + cw
    m.text_latin(RUN, (W - total) / 2, H / 2 + 0.046, 0.092, cw, pitch, ORANGE)
    m.dots_from_layers()
    return m


def led_side():
    W, H, C, R = 0.62, 0.14, 128, 24
    m = KT.Matrix(W, H, C, R)
    n = len(LINE)
    pitch = 0.084
    cw, ch = 0.080, 0.112
    total = (n - 1) * pitch + cw
    m.text_cjk(LINE, (W - total) / 2, (H - ch) / 2, cw, ch, pitch, ORANGE)
    m.dots_from_layers()
    return m


def set_plate():
    """0.26 x 0.10 m at 1000 px/m: white plate, a thin dark rim, the set number in black"""
    S = 4
    w, h = 260 * S, 100 * S
    im = Image.new('RGB', (w, h), (238, 240, 236))
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, w - 1, h - 1), outline=(70, 74, 72), width=4 * S)
    f = ImageFont.truetype(FONT_BOLD, 74 * S, index=0)
    d.text((w // 2, 80 * S), SET, font=f, fill=(24, 26, 26), anchor='ms')
    return im.resize((260, 100), Image.LANCZOS)


def car_number(text, ppm=1000, cap=0.075):
    """black lettering on transparent; text height `cap` m (JR East stainless cars: ~75 mm, est.)"""
    S = 4
    size = int(cap * ppm * S * 1.32)
    f = ImageFont.truetype(FONT_MED, size, index=0)
    tmp = Image.new('L', (size * (len(text) + 2), size * 2), 0)
    d = ImageDraw.Draw(tmp)
    d.text((size // 2, size // 2), text, font=f, fill=255)
    bb = tmp.getbbox()
    tmp = tmp.crop((bb[0] - 4 * S, bb[1] - 4 * S, bb[2] + 4 * S, bb[3] + 4 * S))
    tmp = tmp.resize((max(1, tmp.width // S), max(1, tmp.height // S)), Image.LANCZOS)
    out = Image.new('RGBA', tmp.size, (20, 20, 22, 0))
    out.putalpha(tmp)
    return out


def jr_mark(h=240, ratio=1.75):
    """the JR mark: the letters J R in Noto Sans CJK Bold, set close and stretched to the mark's proportions on the
    E231-1000's face and side bands (w : h ≈ 1.75 on "JRE Series-E231-1000 S-13.jpg")"""
    S = 4
    f = ImageFont.truetype(FONT_BOLD, h * S, index=0)
    tmp = Image.new('L', (h * S * 3, h * S * 2), 0)
    d = ImageDraw.Draw(tmp)
    d.text((h * S // 4, h * S // 4), 'J', font=f, fill=255)
    jb = tmp.getbbox()
    d.text((jb[2] + int(0.06 * h * S), h * S // 4), 'R', font=f, fill=255)
    tmp = tmp.crop(tmp.getbbox())
    tmp = tmp.resize((int(h * ratio), h), Image.LANCZOS)
    out = Image.new('RGBA', tmp.size, (255, 255, 255, 0))
    out.putalpha(tmp)
    return out


def main():
    os.makedirs(OUT, exist_ok=True)

    def save(img, fname):
        img.save(os.path.join(OUT, fname), optimize=False)

    for fname, fn in (('led_runno', led_runno), ('led_dest', led_dest), ('led_side', led_side)):
        m = fn()
        save(m.render(lit=True), fname + '.png')
        save(m.render(lit=False), fname + '_off.png')
    save(set_plate(), 'set_plate.png')
    for car, text in NUMBERS.items():
        save(car_number(text), f'numbers_{car}.png')
    save(jr_mark(), 'jr_mark.png')
    print('wrote', OUT)


if __name__ == '__main__':
    main()
