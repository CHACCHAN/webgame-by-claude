#!/usr/bin/env python3
"""Signage textures for the E231-0 Blender model, two variants (e231.py --variant):
  musashino  Musashino Line (MU sets): run 1304E, set plate "MU 2" white on red (photos p02, p03, p12, p17)
  sobu       Chūō-Sōbu local (B sets, as built): run 1129B, set plate "B 11" dark on yellow (Commons "Kuha E230-11
             Mitaka Rolling Stock Center 20211101.jpg", Rsa, CC BY-SA 3.0)
The displays show the line name (owner's call): 武蔵野線 / Musashino Line, 総武線各駅停車 / Chuo-Sobu Line.

Host python3 + PIL only (no numpy). Deterministic: no random numbers, same bytes every run.
    python3 frontend/tools/blender/e231_textures.py [outdir]
Default output: frontend/tools/blender/textures/e231/ (Musashino) and textures/e231/sobu/ (Chūō-Sōbu).

  led_runno.png / _off   0.42 x 0.17 m   56 x 24 dots   3-colour LED: run number in orange
  led_dest.png  / _off   0.78 x 0.20 m  128 x 32 dots   3-colour LED: line name (orange) + English (green)
  led_side.png  / _off   0.62 x 0.138 m 160 x 36 dots   full-colour side unit: line name in the line colour + English
                                                        (sizes read off "JRE Kuha-E231-39 Outside-LED.jpg",
                                                        MaedaAkihiko, CC0)
  set_plate.png          0.26 x 0.12 m                  the set number plate behind the windscreen
  numbers_<car>.png      RGBA, black lettering on transparent, 1000 px/m: the car numbers painted on the sides
                         (Musashino: クハE231-22, ◆モハE231-85 (◆: cleared for the Takao tunnels), クハE230-22;
                         Chūō-Sōbu: クハE231-11, モハE231-21, クハE230-11; the motor cars' numbers are our own pick)

Fonts: Noto Sans CJK JP (SIL OFL 1.1) only. The LED dot-matrix helpers come from keikyu1000_textures.py.
"""
import os
import sys

sys.dont_write_bytecode = True
from PIL import Image, ImageDraw, ImageFont  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import keikyu1000_textures as KT  # noqa: E402

OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, 'textures', 'e231')

ORANGE = (255, 96, 10)        # the 3-colour LED's orange (reads red-orange on photos)
AMBER = (255, 150, 20)        # full-colour LED: destination
GREEN = (120, 220, 40)        # yellow-green of the romaji line
RED_LED = (255, 40, 60)
FONT_BOLD = '/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc'
FONT_MED = '/usr/share/fonts/opentype/noto/NotoSansCJK-Medium.ttc'

YELLOW = (255, 214, 0)        # full-colour LED: the Chūō-Sōbu local's yellow

# what the displays show: the front run number, the line name (front and side) with its English line under it
VARIANTS = {
    'musashino': dict(run='1304E', line='武蔵野線', line_en='Musashino Line', side_colour=ORANGE,
                      plate=('MU', '2', (196, 30, 40), (250, 250, 250)),
                      numbers={'car0': 'クハE231-22', 'car1': '◆モハE231-85', 'car2': 'クハE230-22'}, sub=''),
    'sobu': dict(run='1129B', line='総武線各駅停車', line_en='Chuo-Sobu Line', side_colour=YELLOW,
                 plate=('B', '11', (255, 212, 0), (30, 30, 30)),
                 numbers={'car0': 'クハE231-11', 'car1': 'モハE231-21', 'car2': 'クハE230-11'}, sub='sobu'),
}


def led_runno(v):
    m = KT.Matrix(0.42, 0.17, 56, 24)
    run = v['run']
    n = len(run)
    pitch, cw = 0.074, 0.062
    total = (n - 1) * pitch + cw
    m.text_latin(run, (0.42 - total) / 2, 0.17 / 2 + 0.062, 0.124, cw, pitch, ORANGE)
    m.dots_from_layers()
    return m


def _line_name(m, text, en, W, top, cw, ch, pitch, colour, en_y, en_h, en_w):
    total = (len(text) - 1) * pitch + cw
    m.text_cjk(text, (W - total) / 2, top, cw, ch, pitch, colour)
    m.text_fit(en, (W - en_w) / 2, en_y, en_w, en_h, GREEN, track=0.05)


def led_dest(v):
    """3-colour LED: the line name in orange, its English name in green under it"""
    m = KT.Matrix(0.78, 0.20, 128, 32)
    if len(v['line']) <= 4:
        _line_name(m, v['line'], v['line_en'], 0.78, 0.012, 0.122, 0.122, 0.150, ORANGE, 0.148, 0.040, 0.40)
    else:
        _line_name(m, v['line'], v['line_en'], 0.78, 0.016, 0.096, 0.118, 0.104, ORANGE, 0.148, 0.040, 0.40)
    m.dots_from_layers()
    return m


def led_side(v):
    """full-colour side unit: the line name over its English name"""
    W, H, C, R = 0.62, 0.138, 160, 36
    m = KT.Matrix(W, H, C, R)
    if len(v['line']) <= 4:
        _line_name(m, v['line'], v['line_en'], W, 0.008, 0.084, 0.088, 0.104, v['side_colour'], 0.104, 0.026, 0.30)
    else:
        _line_name(m, v['line'], v['line_en'], W, 0.010, 0.074, 0.084, 0.080, v['side_colour'], 0.104, 0.026, 0.30)
    m.dots_from_layers()
    return m


def set_plate(v):
    """0.26 x 0.12 m at 1000 px/m: the set's letters (small, lower left) and number; Musashino: white on red,
    Chūō-Sōbu: dark on yellow (q44 crop)"""
    S = 4
    w, h = 260 * S, 120 * S
    letters, num, bg, fg = v['plate']
    im = Image.new('RGB', (w, h), bg)
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, w - 1, h - 1), outline=(60, 10, 14), width=3 * S)
    f_small = ImageFont.truetype(FONT_BOLD, 30 * S, index=0)
    f_big = ImageFont.truetype(FONT_MED, 92 * S, index=0)
    d.text((22 * S, 108 * S), letters, font=f_small, fill=fg, anchor='ls')
    d.text((160 * S, 108 * S), num, font=f_big, fill=fg, anchor='ms')
    return im.resize((260, 120), Image.LANCZOS)


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


def main():
    for name, v in VARIANTS.items():
        out = os.path.join(OUT, v['sub']) if v['sub'] else OUT
        os.makedirs(out, exist_ok=True)

        def save(img, fname):
            img.save(os.path.join(out, fname), optimize=False)

        for fname, fn in (('led_runno', led_runno), ('led_dest', led_dest), ('led_side', led_side)):
            m = fn(v)
            save(m.render(lit=True), fname + '.png')
            save(m.render(lit=False), fname + '_off.png')
        save(set_plate(v), 'set_plate.png')
        for car, text in v['numbers'].items():
            save(car_number(text), f'numbers_{car}.png')
        print('wrote', name, out)


if __name__ == '__main__':
    main()
