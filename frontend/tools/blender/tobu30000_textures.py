#!/usr/bin/env python3
"""Signage textures for the Tobu 30000 series Blender model (tools/blender/tobu30000.py).

Host python3 + PIL only (no numpy). Deterministic: no random numbers, same bytes every run.
    python3 frontend/tools/blender/tobu30000_textures.py [outdir]
Default output: frontend/tools/blender/textures/tobu30000/

Two variants (tobu30000.py --variant): the Tojo Line today, 急行 東上線 / TOJO LINE (the display shows the line name),
and the Isesaki Line era (1996-2011), 急行 伊勢崎線 on 3-colour LEDs (files *_isesaki.png, the same pixel sizes so the atlas
and the UVs stay identical). Tojo displays, on the full-colour LED displays the 10-car Tojo sets
carry today (photos 2024-2026: "Tobu-Series30000 31612.jpg", "Tobu railway 31613 at Ikebukuro Station 20240629",
"Tobu Series30000-32401 Outside-LED.jpg"). Layouts are read off those photos; their pixels are not used.

  led_type.png / _off   0.600 x 0.170 m (1400 px/m; the side display 2000 px/m: the atlas stays within 4096 px)  front type display behind the left windscreen: red field, 急行 + EXPRESS
  led_dest.png / _off   0.770 x 0.200 m  front destination display over the gangway door: 東上線 + TOJO LINE, white on black
  led_side.png / _off   0.980 x 0.160 m  side display: red type block 急行 / EXPRESS, then 東上線 / TOJO LINE
  numbers.json          car numbers as outlines (metres, cap height 0.130 m; the sides scale them to 0.093 m), traced
                        from a 4000 px/m raster of the digits (pixel-edge loops, Douglas-Peucker 1.6 px)
LED matrices: Matrix from keikyu1000_textures (dark panel, unlit dots visible, lit dots with a glow).
Fonts: Noto Sans CJK JP (SIL OFL 1.1), Medium for the LED characters and the car numbers.
"""
import json
import math
import os
import sys

sys.dont_write_bytecode = True
from PIL import Image, ImageDraw, ImageFont  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import keikyu1000_textures as KT  # noqa: E402

OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, 'textures', 'tobu30000')
FONT_NUM = '/usr/share/fonts/opentype/noto/NotoSansCJK-Medium.ttc'

WHITE = (240, 244, 255)
RED = (232, 26, 30)          # 急行 field (Tojo Line full-colour LED; 31612 photo)
RED3 = (255, 38, 24)         # 3-colour LED (Isesaki Line era): red
ORANGE3 = (255, 128, 16)     #   and orange
NUMBERS = ('31612', '32612', '34412')
CONDENSE = 0.90         # the train's digits are a little narrower than Noto's


def led_type():
    # 0.60 x 0.17 m, pitch ~3.5 mm: 172 x 48 dots. Red field over the whole panel; 急行 0.105 high, EXPRESS 0.026
    m = KT.Matrix(0.60, 0.17, 172, 48)
    m.fill(RED)
    cw, ch, pitch = 0.112, 0.102, 0.20
    m.text_cjk('急行', (0.60 - pitch - cw) / 2, 0.012, cw, ch, pitch, WHITE)
    m.text_fit('EXPRESS', 0.195, 0.128, 0.21, 0.028, WHITE)
    m.dots_from_layers()
    return m


def led_dest():
    # 0.77 x 0.20 m: 220 x 57 dots; the line name widely spaced, its romanisation under it
    m = KT.Matrix(0.77, 0.20, 220, 57)
    cw, ch, pitch = 0.118, 0.112, 0.20
    m.text_cjk('東上線', (0.77 - 2 * pitch - cw) / 2, 0.016, cw, ch, pitch, WHITE)
    m.text_fit('TOJO LINE', 0.27, 0.146, 0.23, 0.030, WHITE)
    m.dots_from_layers()
    return m


def led_side():
    # 0.98 x 0.16 m: 392 x 64 dots (2.5 mm, as the close-up of 32401 shows); type block on the left 0.31 m
    m = KT.Matrix(0.98, 0.16, 392, 64)
    fw = round(0.31 / 0.98 * 392)
    m.fill(RED, 0, 2, fw, 62)
    m.text_cjk('急行', 0.050, 0.014, 0.090, 0.098, 0.115, WHITE)
    m.text_fit('EXPRESS', 0.040, 0.123, 0.23, 0.026, WHITE)
    m.text_cjk('東上線', 0.423, 0.012, 0.104, 0.100, 0.18, WHITE)
    m.text_fit('TOJO LINE', 0.535, 0.123, 0.24, 0.027, WHITE)
    m.dots_from_layers()
    return m


# ---- Isesaki Line era (1996-2011, Hanzomon line through service): 3-colour LED, coarse dots, Japanese only.
# ja.wikipedia: the type display showed 急行 in red characters, from March 2006 in a red frame ("赤枠に急行");
# destinations in orange. Layouts after the 2007 / 2012 photos ("Tobu-30000.jpg", LERK, CC BY 2.5; "Tobu 30000
# Series.jpg", T. Hanami, CC0), whose displays are too small to read: dot counts and text sizes are estimates.

def _frame(m, colour, i0, j0, i1, j1):
    m.fill(colour, i0, j0, i1, j0 + 1)
    m.fill(colour, i0, j1 - 1, i1, j1)
    m.fill(colour, i0, j0, i0 + 1, j1)
    m.fill(colour, i1 - 1, j0, i1, j1)


def led_type_isesaki():
    m = KT.Matrix(0.60, 0.17, 96, 28)          # ~6 mm pitch
    _frame(m, RED3, 6, 1, 90, 27)
    cw, ch, pitch = 0.125, 0.125, 0.19
    m.text_cjk('急行', (0.60 - pitch - cw) / 2, 0.023, cw, ch, pitch, RED3)
    m.dots_from_layers()
    return m


def led_dest_isesaki():
    m = KT.Matrix(0.77, 0.20, 128, 32)         # 6 mm pitch
    cw, ch, pitch = 0.150, 0.150, 0.175
    m.text_cjk('伊勢崎線', (0.77 - 3 * pitch - cw) / 2, 0.025, cw, ch, pitch, ORANGE3)
    m.dots_from_layers()
    return m


def led_side_isesaki():
    m = KT.Matrix(0.98, 0.16, 192, 32)         # 5 mm pitch
    fw = round(0.30 / 0.98 * 192)
    _frame(m, RED3, 2, 1, fw, 31)
    m.text_cjk('急行', 0.045, 0.025, 0.105, 0.110, 0.12, RED3)
    m.text_cjk('伊勢崎線', 0.36, 0.022, 0.120, 0.116, 0.150, ORANGE3)
    m.dots_from_layers()
    return m


def _mask(text, cap, ppm, track):
    """1-bit raster of the digits, cap height `cap` m at `ppm` px/m, no padding"""
    F = 400
    f = ImageFont.truetype(FONT_NUM, F, index=0)
    im = Image.new('L', (F * (len(text) + 2), F * 2), 0)
    d = ImageDraw.Draw(im)
    x = F // 2
    for c in text:
        d.text((x, F // 2), c, font=f, fill=255)
        x += d.textlength(c, font=f) + track * F
    im = im.crop(im.getbbox())
    s = cap * ppm / im.height
    im = im.resize((max(1, round(im.width * s * CONDENSE)), round(im.height * s)), Image.LANCZOS)
    return im.point(lambda v: 1 if v >= 128 else 0, mode='1')


def _loops(mask):
    """closed pixel-edge loops round the set pixels (counter-clockwise round ink with y up), as vertex lists"""
    W, H = mask.size
    px = mask.load()

    def ink(i, j):
        return 0 <= i < W and 0 <= j < H and px[i, j]
    nxt = {}
    # vertex (i, j) = pixel corner; image rows go down, we flip to y up later. Edges keep ink on their left (y down
    # frame: on the right), consistently, so loops close.
    for j in range(H):
        for i in range(W):
            if not px[i, j]:
                continue
            if not ink(i, j - 1):
                nxt.setdefault((i + 1, j), []).append((i, j))
            if not ink(i, j + 1):
                nxt.setdefault((i, j + 1), []).append((i + 1, j + 1))
            if not ink(i - 1, j):
                nxt.setdefault((i, j), []).append((i, j + 1))
            if not ink(i + 1, j):
                nxt.setdefault((i + 1, j + 1), []).append((i + 1, j))
    loops = []
    while nxt:
        start = min(nxt)
        loop = [start]
        cur = start
        prev = None
        while True:
            outs = nxt[cur]
            if len(outs) > 1 and prev is not None:
                # at a pinch: take the turn that keeps the ink pixel connected (rightmost turn in the y-down frame)
                dx, dy = cur[0] - prev[0], cur[1] - prev[1]
                outs.sort(key=lambda q: -((dx * (q[1] - cur[1]) - dy * (q[0] - cur[0]))))
            q = outs.pop(0)
            if not outs:
                del nxt[cur]
            prev, cur = cur, q
            if cur == start:
                break
            loop.append(cur)
        loops.append(loop)
    return loops


def _dp(pts, tol):
    """Douglas-Peucker on a closed loop (split at the two farthest-apart points)"""
    n = len(pts)
    if n < 6:
        return pts
    a = 0
    b = max(range(n), key=lambda k: (pts[k][0] - pts[0][0]) ** 2 + (pts[k][1] - pts[0][1]) ** 2)

    def rec(seg):
        (x0, y0), (x1, y1) = seg[0], seg[-1]
        L = math.hypot(x1 - x0, y1 - y0) or 1e-9
        dmax, k = 0.0, 0
        for t in range(1, len(seg) - 1):
            x, y = seg[t]
            dd = abs((x1 - x0) * (y0 - y) - (x0 - x) * (y1 - y0)) / L
            if dd > dmax:
                dmax, k = dd, t
        if dmax > tol:
            return rec(seg[:k + 1])[:-1] + rec(seg[k:])
        return [seg[0], seg[-1]]
    first = rec(pts[a:b + 1])
    second = rec(pts[b:] + [pts[0]])
    return first[:-1] + second[:-1]


def number_contours(text, cap=0.130, ppm=4000, track=0.10):
    """outlines (metres, y up, origin at the ink's bottom-left) of the dark digits; even-odd fill"""
    m = _mask(text, cap, ppm, track)
    H = m.size[1]
    out = []
    for loop in _loops(m):
        pts = _dp(loop, 1.6)
        if len(pts) >= 3:
            out.append([[round(x / ppm, 5), round((H - y) / ppm, 5)] for x, y in pts])
    return out, (m.size[0] / ppm, H / ppm)


def main():
    os.makedirs(OUT, exist_ok=True)

    def save(img, name):
        img.save(os.path.join(OUT, name), optimize=True)
        print(f'{name:22s} {img.width}x{img.height} {img.mode}')

    for name, fn, ppm in (('led_type', led_type, 1400), ('led_dest', led_dest, 1400), ('led_side', led_side, 2000),
                          ('led_type_isesaki', led_type_isesaki, 1400), ('led_dest_isesaki', led_dest_isesaki, 1400),
                          ('led_side_isesaki', led_side_isesaki, 2000)):
        m = fn()
        save(m.render(True, ppm), name + '.png')
        save(m.render(False, ppm), name + '_off.png')
    res = {}
    for n in NUMBERS:
        cont, size = number_contours(n)
        res[n] = {'size': [round(size[0], 5), round(size[1], 5)], 'contours': cont}
        print(f'numbers {n}: {len(cont)} contours, {sum(len(c) for c in cont)} points, {size[0]:.3f} x {size[1]:.3f} m')
    with open(os.path.join(OUT, 'numbers.json'), 'w') as f:
        json.dump(res, f, separators=(',', ':'), sort_keys=True)

if __name__ == '__main__':
    main()
