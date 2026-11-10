"""
sheet.py: the fit sheet for the owner: each photo beside our render from its solved camera and the outlines
(photo mask green, model magenta), the silhouette numbers, the lamp panel close-ups (photo | outlines | render) with
their numbers, and the check renders.

  py sheet.py <cams.json> <workdir> <shape.json> <renders_dir> <lamps_dir> <out.jpg> [--title T] [--note N]
      [--photos c07,c04,c12] [--extra hero,rear34,night,metal]
"""
import json, os, sys

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import sil

FONT = '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'
BOLD = '/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc'
CROPS = {'c07': (250, 380, 1650, 1150), 'c04': (80, 545, 1400, 715), 'c12': (900, 480, 1600, 1060),
         'c09': (500, 300, 1920, 1000), 'c01': (300, 300, 1600, 1100)}
W = 2400


def font(size, bold=False):
    try:
        return ImageFont.truetype(BOLD if bold else FONT, size)
    except OSError:
        return ImageFont.load_default()


def fit_w(im, w):
    return im.resize((w, max(1, round(im.height * w / im.width))), Image.LANCZOS)


def main():
    a = sys.argv[1:]

    def opt(k, d=None):
        return a[a.index(k) + 1] if k in a else d
    cams_p, wd, shape_p, rdir, ldir, out = a[:6]
    cams = json.load(open(cams_p))['cams']
    sil.load_shape(shape_p)
    photos = opt('--photos', 'c07,c04,c12').split(',')
    extra = [e for e in opt('--extra', '').split(',') if e]
    rows = []
    # title
    title = opt('--title', 'L0 series (L0系) — fit sheet')
    note = opt('--note', '')
    hdr = Image.new('RGB', (W, 150 + 34 * max(1, note.count('|') + 1)), 'white')
    d = ImageDraw.Draw(hdr)
    d.text((30, 20), title, fill='black', font=font(48, True))
    for i, line in enumerate(note.split('|')):
        d.text((30, 95 + 34 * i), line.strip(), fill=(40, 40, 40), font=font(26))
    rows.append(hdr)
    # photo pairs
    table = []
    for p in photos:
        c = cams[p]
        Wp, Hp = c[7]
        x0, y0, x1, y1 = CROPS[p]
        photo = Image.open(os.path.join(wd, 'work', p + '.jpg')).convert('RGB')
        rp = os.path.join(rdir, f'photo_{p}.png')
        render = Image.open(rp).convert('RGB') if os.path.exists(rp) else Image.new('RGB', (Wp // 2, Hp // 2), 'grey')
        render = render.resize((Wp, Hp), Image.LANCZOS)
        m = sil.raster(c[:7], Wp, Hp)
        mp = os.path.join(wd, 'masks', p + '.png')
        mask = cv2.imread(mp, cv2.IMREAD_GRAYSCALE) if os.path.exists(mp) else None
        ov = sil.overlay(os.path.join(wd, 'work', p + '.jpg'), m, mask)
        ov = Image.fromarray(cv2.cvtColor(ov, cv2.COLOR_BGR2RGB))
        if mask is not None:
            r = sil.compare(m, mask)
            table.append((p, r))
        tiles = [im.crop((x0, y0, x1, y1)) for im in (photo, render, ov)]
        tw = (W - 40) // 3
        tiles = [fit_w(t, tw) for t in tiles]
        row = Image.new('RGB', (W, tiles[0].height + 50), 'white')
        dd = ImageDraw.Draw(row)
        labels = (f'{p}: photo (Commons, see ref/list.json)', f'{p}: our model, solved camera', 'outlines: photo mask green, model magenta (grey: ignored)')
        for i, t in enumerate(tiles):
            row.paste(t, (10 + i * (tw + 10), 45))
            dd.text((10 + i * (tw + 10), 8), labels[i], fill='black', font=font(26))
        rows.append(row)
    # silhouette table
    tb = Image.new('RGB', (W, 70 + 40 * len(table)), 'white')
    d = ImageDraw.Draw(tb)
    d.text((30, 10), 'Silhouette against the photo masks (shell only; px of the 1920-wide working copy)', fill='black', font=font(30, True))
    for i, (p, r) in enumerate(table):
        d.text((50, 55 + 40 * i), f'{p}:   IoU {r["iou"]:.3f}    outline p95 {r["p95"]:.1f} px    max {r["max"]:.1f} px    mean {r["mean"]:.1f} px',
               fill=(30, 30, 30), font=font(28))
    rows.append(tb)
    # lamps
    ls = os.path.join(ldir, 'lampscore.json')
    if os.path.exists(ls):
        scores = json.load(open(ls))
        for p in sorted({s[0] for s in scores}):
            ims = []
            for k in ('photo', 'lines'):
                f = os.path.join(ldir, f'lamp_{p}_{k}.png')
                ims.append(Image.open(f).convert('RGB') if os.path.exists(f) else None)
            rc = os.path.join(rdir, f'photo_{p}_crop.png')
            ims.append(Image.open(rc).convert('RGB') if os.path.exists(rc) else None)
            ims = [im for im in ims if im is not None]
            tw = (W - 40) // 3
            ims = [fit_w(im, tw) for im in ims]
            hgt = max(im.height for im in ims)
            sc = [s for s in scores if s[0] == p]
            row = Image.new('RGB', (W, hgt + 60 + 34 * len(sc)), 'white')
            dd = ImageDraw.Draw(row)
            labels = (f'{p} lamp panel: photo', 'traced (green) and ours (magenta)', 'our render, same camera')
            for i, im in enumerate(ims):
                row.paste(im, (10 + i * (tw + 10), 45))
                dd.text((10 + i * (tw + 10), 8), labels[i], fill='black', font=font(26))
            for j, (_, name, iou, p95, mx) in enumerate(sc):
                dd.text((30, hgt + 55 + 34 * j), f'{name}: IoU {iou:.3f}   outline p95 {p95:.2f} px   max {mx:.2f} px',
                        fill=(30, 30, 30), font=font(26))
            rows.append(row)
    # extra renders, two a row
    ex = [os.path.join(rdir, e + '.png') for e in extra if os.path.exists(os.path.join(rdir, e + '.png'))]
    for i in range(0, len(ex), 2):
        pair = [Image.open(f).convert('RGB') for f in ex[i:i + 2]]
        tw = (W - 30) // 2
        pair = [fit_w(im, tw) for im in pair]
        row = Image.new('RGB', (W, max(im.height for im in pair) + 50), 'white')
        dd = ImageDraw.Draw(row)
        for j, im in enumerate(pair):
            row.paste(im, (10 + j * (tw + 10), 45))
            dd.text((10 + j * (tw + 10), 8), os.path.basename(ex[i + j])[:-4], fill='black', font=font(26))
        rows.append(row)
    H = sum(r.height for r in rows)
    sheet = Image.new('RGB', (W, H), 'white')
    y = 0
    for r in rows:
        sheet.paste(r, (0, y))
        y += r.height
    sheet.save(out, quality=88)
    print(out, sheet.size)


if __name__ == '__main__':
    main()
