#!/usr/bin/env python3
"""Signage textures for the JR East E235 series 0 (Yamanote Line) Blender model.

Host python3 + PIL only (no numpy). Deterministic: no random numbers, same bytes every run.
    python3 frontend/tools/blender/e235_textures.py [outdir]
Default output: frontend/tools/blender/textures/e235/

The dot-matrix renderer (`Matrix`: unlit dots visible, lit dots with a glow) is keikyu1000_textures.Matrix, imported.
Fonts: Noto Sans CJK JP (index 0 of the .ttc; SIL OFL 1.1), as there. Images: u to the right, v down.

  led_front.png    1.070 x 0.160 m  full-colour LED above the windscreen, "山手線 Yamanote Line" in white over the
                   line colour bar (as on every head-on photo: 524875 / 612879 / f57682 in the scratch list.json).
                   Measured on the head-on photo (626 px/m): lit area x -0.52..+0.55, y 3.25..3.41; 山手線 0.42 m
                   wide, 0.115 m tall; "Yamanote Line" cap height 0.064 m; the green bar the bottom 0.05 m.
  led_runno.png    0.420 x 0.120 m  white LED run number behind the windscreen's top left ("1308G" on the photo,
                   characters 0.096 m tall over x -1.126..-0.757). Ours: 1215G (a plausible Yamanote run number).
  led_setno.png    0.110 x 0.060 m  the set number at the windscreen's bottom left (small grey-white figures, "23"
                   on the photo). Ours: 17.
  led_side.png     0.540 x 0.130 m  side destination unit (full colour): line colour field with 山手線, then
                   "渋谷・新宿方面" white on black (the inner loop's way of showing it; English alternates, not shown).
  (and *_off.png: every dot dark)
  num_<car>.png    car numbers as painted on the side below the windows (black Noto Sans CJK JP Medium on white,
                   2,000 px/m, the lettering 0.085 m tall as on the line-scan photo "クハE235-9"): クハE235-17,
                   モハE235-49 (the 9th car of set 17), クハE234-17. The model samples them into the side texture.
"""
import os
import sys

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.dont_write_bytecode = True
import keikyu1000_textures as KT  # noqa: E402

OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, 'textures', 'e235')

WHITE = (236, 242, 255)
LINE_GREEN = (128, 200, 40)       # the Yamanote line colour as the LEDs show it (yellow-green)
GREY = (150, 156, 160)


def led_front():
    # 1.07 x 0.16 m, pitch ~4 mm: 268 x 40 dots
    W, H = 1.07, 0.16
    m = KT.Matrix(W, H, 268, 40)
    # the line colour bar: the bottom 0.05 m (12 rows), as wide as the lit area
    m.fill(LINE_GREEN, 0, 29, 268, 40)
    # 山手線: 0.42 wide, 0.115 tall, from x 0.01; its foot dips into the bar a little (photo)
    m.text_cjk('山手線', 0.014, 0.008, 0.122, 0.112, 0.143, WHITE)
    # Yamanote Line: cap height 0.064 m, from x 0.445 to 1.05
    m.text_fit('Yamanote Line', 0.452, 0.034, 0.590, 0.064, WHITE, track=0.02)
    m.dots_from_layers()
    return m


def led_runno(text='1215G'):
    # 0.42 x 0.12 m, white figures 0.096 tall; pitch 4 mm: 105 x 30 dots
    m = KT.Matrix(0.42, 0.12, 105, 30)
    m.text_fit(text, 0.04, 0.012, 0.33, 0.096, WHITE, track=0.08)
    m.dots_from_layers()
    return m


def led_setno(text='17'):
    m = KT.Matrix(0.11, 0.06, 37, 20)
    m.text_fit(text, 0.012, 0.010, 0.080, 0.042, GREY, track=0.10)
    m.dots_from_layers()
    return m


def led_side():
    # 0.54 x 0.13 m (measured on the line-scan photo), pitch 2.5 mm: 216 x 52 dots. The line name only (the owner's
    # choice): 山手線 large, "Yamanote Line" beside it, the line colour bar under both as on the front display
    m = KT.Matrix(0.54, 0.13, 216, 52)
    m.text_cjk('山手線', 0.022, 0.016, 0.076, 0.082, 0.080, WHITE)
    m.text_fit('Yamanote Line', 0.272, 0.044, 0.246, 0.046, WHITE, track=0.02)
    m.fill(LINE_GREEN, 6, 43, 210, 48)
    m.dots_from_layers()
    return m


# ---------------------------------------------------------------- E235-1000 (Yokosuka / Sobu Rapid line)
SOBU_BLUE = (52, 92, 230)       # 青20号 (#2440c3) as LEDs show it, a little lighter
SOBU_CREAM = (255, 236, 196)    # クリーム1号 (#fff4d5)


def sobu_front():
    """横須賀・総武快速線 over "Yokosuka-Sobu Rapid Line", the two line colours as a bar under them"""
    m = KT.Matrix(1.07, 0.16, 268, 40)
    m.text_cjk('横須賀', 0.085, 0.006, 0.092, 0.088, 0.100, WHITE)
    m.text_cjk('・', 0.392, 0.039, 0.022, 0.022, 0.03, WHITE)       # the glyph is scaled to its box: drawn small
    m.text_cjk('総武快速線', 0.425, 0.006, 0.092, 0.088, 0.100, WHITE)
    m.text_fit('Yokosuka-Sobu Rapid Line', 0.150, 0.102, 0.770, 0.034, WHITE, track=0.03)
    m.fill(SOBU_CREAM, 20, 37, 134, 40)
    m.fill(SOBU_BLUE, 134, 37, 248, 40)
    m.dots_from_layers()
    return m


def sobu_side():
    m = KT.Matrix(0.54, 0.13, 216, 52)
    m.text_cjk('横須賀', 0.012, 0.008, 0.054, 0.058, 0.0575, WHITE)
    m.text_cjk('・', 0.189, 0.030, 0.013, 0.013, 0.02, WHITE)
    m.text_cjk('総武快速線', 0.212, 0.008, 0.054, 0.058, 0.0575, WHITE)
    m.text_fit('Yokosuka-Sobu Rapid Line', 0.040, 0.078, 0.460, 0.026, WHITE, track=0.02)
    m.fill(SOBU_CREAM, 6, 46, 108, 50)
    m.fill(SOBU_BLUE, 108, 46, 210, 50)
    m.dots_from_layers()
    return m


NUMBERS = {'kuha235': 'クハE235-17', 'moha235': 'モハE235-49', 'kuha234': 'クハE234-17'}
# set F-35 of the 11-car basic set: 11号車 クハE235-1035, 10号車 モハE235-1035 (pantograph), 1号車 クハE234-1035
SOBU_NUMBERS = {'kuha235': 'クハE235-1035', 'moha235': 'モハE235-1035', 'kuha234': 'クハE234-1035'}


def car_number(text, ppm=2000, h_m=0.085):
    """black lettering on white: the katakana a little smaller than the type letters and figures, as painted"""
    from PIL import ImageDraw, ImageFont
    F = 400
    font = ImageFont.truetype(KT.FONT_CJK, F, index=0)
    small = ImageFont.truetype(KT.FONT_CJK, int(F * 0.72), index=0)
    pieces = []
    for ch in text:
        f = small if ch in 'クハモサ' else font
        pieces.append((ch, f))
    W = sum(int(f.getlength(ch)) for ch, f in pieces) + F
    im = Image.new('L', (W, int(F * 1.6)), 0)
    d = ImageDraw.Draw(im)
    x = F // 4
    base = int(F * 1.25)
    for ch, f in pieces:
        d.text((x, base), ch, font=f, fill=255, anchor='ls')
        x += f.getlength(ch) * (0.92 if f is small else 1.0)
    im = im.crop(im.getbbox())
    sc = h_m * ppm / im.height
    im = im.resize((max(1, round(im.width * sc)), max(1, round(im.height * sc))), Image.LANCZOS)
    pad = 8
    out = Image.new('L', (im.width + 2 * pad, im.height + 2 * pad), 0)
    out.paste(im, (pad, pad))
    return Image.eval(out, lambda v: 255 - v).convert('RGB')


def main():
    os.makedirs(OUT, exist_ok=True)

    def save(img, name):
        p = os.path.join(OUT, name)
        img.save(p, optimize=True)
        print(f'{name:22s} {img.width}x{img.height} {img.mode}')

    for name, m, ppm in (('led_front', led_front(), 1600), ('led_runno', led_runno(), 1600),
                         ('led_setno', led_setno(), 1600), ('led_side', led_side(), 2000),
                         ('sobu_led_front', sobu_front(), 1600), ('sobu_led_runno', led_runno('1452F'), 1600),
                         ('sobu_led_setno', led_setno('F-35'), 1600), ('sobu_led_side', sobu_side(), 2000)):
        save(m.render(True, ppm), name + '.png')
        save(m.render(False, ppm), name + '_off.png')
    for key, text in NUMBERS.items():
        save(car_number(text), f'num_{key}.png')
    for key, text in SOBU_NUMBERS.items():
        save(car_number(text), f'sobu_num_{key}.png')


if __name__ == '__main__':
    main()
