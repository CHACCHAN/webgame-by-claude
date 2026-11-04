#!/usr/bin/env python3
"""Signage textures for the E231-0 Blender model, two variants (e231.py --variant):
  musashino  Musashino Line (MU sets): run 1304E, set plate "MU 2" white on red (photos p02, p03, p12, p17)
  joban      Jōban rapid / Narita Line: run 1050H, 常磐線 / Joban Line, set plate 111 white on blue
  tozai      E231-800, Tōzai Line through service: run 03K, 地下鉄東西線直通 / Tozai Line, set K5
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
  jr_mark.png            RGBA, the JR mark (white on transparent, width : height 1.85), both variants
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
    # Jōban rapid / Narita Line (Matsudo, basic sets 101-): run numbers end in H ("JRE Series-E231-0 111.jpg");
    # the set number plate is a small white number on blue; car numbers our own pick
    'joban': dict(run='1050H', line='常磐線', line_en='Joban Line', side_colour=(40, 215, 175),
                  plate=('', '111', (30, 70, 160), (250, 250, 250)),
                  numbers={'car0': 'クハE231-71', 'car1': 'モハE231-131', 'car2': 'クハE230-71'}, sub='joban'),
    # E231-800 (Tōzai Line through service, K sets): the line-name display shows 地下鉄東西線直通 front and side;
    # the front run-number box shows the Tōzai Line's duty number (03K); sizes measured on Commons
    # "JRE-Series-E231-800 K5.jpg" (MaedaAkihiko, CC BY-SA 4.0; head-on, 271 px/m): run box 0.46 x 0.17, line box
    # 0.80 x 0.19; the side unit is a 3-colour LED showing the line in one orange row ("Tokyo Metro Tōzai Line 2024 1.jpg",
    # Smiley.toerist, CC BY-SA 4.0); the set number "K 5" is bare white lettering behind the door window
    'tozai': dict(run='03K', line='地下鉄東西線直通', line_en='Tozai Line', side_colour=ORANGE,
                  plate=('K', '5', (14, 15, 17), (236, 238, 240)), plate_style='bare',
                  dest_box=(0.80, 0.19, 128, 32), run_box=(0.46, 0.17, 64, 24), side_one_row=True,
                  numbers={'car0': 'クハE231-805', 'car1': 'モハE231-813', 'car2': 'クハE230-805'}, sub='tozai'),
}


def led_runno(v):
    W, H, C, R = v.get('run_box', (0.42, 0.17, 56, 24))
    m = KT.Matrix(W, H, C, R)
    run = v['run']
    n = len(run)
    pitch, cw = 0.074, 0.062
    total = (n - 1) * pitch + cw
    m.text_latin(run, (W - total) / 2, H / 2 + 0.062, 0.124, cw, pitch, ORANGE)
    m.dots_from_layers()
    return m


def _line_name(m, text, en, W, top, cw, ch, pitch, colour, en_y, en_h, en_w):
    total = (len(text) - 1) * pitch + cw
    m.text_cjk(text, (W - total) / 2, top, cw, ch, pitch, colour)
    m.text_fit(en, (W - en_w) / 2, en_y, en_w, en_h, GREEN, track=0.05)


def led_dest(v):
    """3-colour LED: the line name in orange, its English name in green under it (a name of 8 characters or more
    fills the box in one row); the box is v['dest_box'] = (w, h, columns, rows), the 0番台's 0.78 x 0.20 m by default"""
    W, H, C, R = v.get('dest_box', (0.78, 0.20, 128, 32))
    m = KT.Matrix(W, H, C, R)
    n = len(v['line'])
    if n <= 4:
        _line_name(m, v['line'], v['line_en'], W, 0.012, 0.122, 0.122, 0.150, ORANGE, 0.148, 0.040, 0.40)
    elif n <= 7:
        _line_name(m, v['line'], v['line_en'], W, 0.016, 0.096, 0.118, 0.104, ORANGE, 0.148, 0.040, 0.40)
    else:
        pitch = (W - 0.03) / n
        ch = min(H * 0.78, pitch * 1.1)
        cw = min(ch, pitch * 0.94)
        m.text_cjk(v['line'], (W - (n - 1) * pitch - cw) / 2, (H - ch) / 2, cw, ch, pitch, ORANGE)
    m.dots_from_layers()
    return m


def led_side(v):
    """full-colour side unit: the line name over its English name (side_one_row: the name alone, one orange row)"""
    W, H, C, R = 0.62, 0.138, 160, 36
    m = KT.Matrix(W, H, C, R)
    n = len(v['line'])
    if v.get('side_one_row'):
        return _side_one_row(m, v['line'], W, H)
    if n <= 4:
        _line_name(m, v['line'], v['line_en'], W, 0.008, 0.084, 0.088, 0.104, v['side_colour'], 0.104, 0.026, 0.30)
    elif n <= 7:
        _line_name(m, v['line'], v['line_en'], W, 0.010, 0.074, 0.084, 0.080, v['side_colour'], 0.104, 0.026, 0.30)
    else:
        _line_name(m, v['line'], v['line_en'], W, 0.012, 0.068, 0.080, 0.0715, v['side_colour'], 0.104, 0.026, 0.24)
    m.dots_from_layers()
    return m


def _side_one_row(m, text, W, H):
    """E231-800 side unit: the line name alone in one row of orange characters filling the box"""
    n = len(text)
    pitch = (W - 0.02) / n
    ch = min(H * 0.80, pitch * 1.25)
    cw = min(ch, pitch * 0.94)
    m.text_cjk(text, (W - (n - 1) * pitch - cw) / 2, (H - ch) / 2, cw, ch, pitch, ORANGE)
    m.dots_from_layers()
    return m


def _plate_bare(v):
    """E231-800: the set number as bare white letters ("K 5", both the same size) on the dark glass, 0.26 x 0.12 m"""
    S = 4
    w, h = 260 * S, 120 * S
    letters, num, bg, fg = v['plate']
    im = Image.new('RGB', (w, h), bg)
    d = ImageDraw.Draw(im)
    f = ImageFont.truetype(FONT_BOLD, 64 * S, index=0)
    d.text((w // 2, 88 * S), f'{letters} {num}', font=f, fill=fg, anchor='ms')
    return im.resize((260, 120), Image.LANCZOS)


def set_plate(v):
    """0.26 x 0.12 m at 1000 px/m: the set's letters (small, lower left) and number; Musashino: white on red,
    Chūō-Sōbu: dark on yellow (q44 crop); plate_style 'bare': _plate_bare"""
    if v.get('plate_style') == 'bare':
        return _plate_bare(v)
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


def jr_mark(h=240, ratio=1.85):
    """the JR mark as on the E231's bands: the letters J R, white on transparent, drawn with Noto Sans CJK Medium and
    stretched to the mark's proportions measured on the photos (width : height ≈ 1.85 on p04, q42)"""
    S = 4
    f = ImageFont.truetype(FONT_MED, h * S, index=0)
    tmp = Image.new('L', (h * S * 3, h * S * 2), 0)
    d = ImageDraw.Draw(tmp)
    d.text((h * S // 4, h * S // 4), 'J', font=f, fill=255)
    jb = tmp.getbbox()
    d.text((jb[2] + int(0.12 * h * S), h * S // 4), 'R', font=f, fill=255)
    tmp = tmp.crop(tmp.getbbox())
    tmp = tmp.resize((int(h * ratio), h), Image.LANCZOS)
    out = Image.new('RGBA', tmp.size, (255, 255, 255, 0))
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
    jr_mark().save(os.path.join(OUT, 'jr_mark.png'), optimize=False)


if __name__ == '__main__':
    main()
