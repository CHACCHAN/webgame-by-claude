"""
lampscore.py: the Supra's lamps and openings measured per part. The outlines traced on the photos (lamps.json) against
the model's (lamps.py ids: the registered outlines as flat patches / discs, rendered from the same solved cameras and
poses): IoU, and the outline deviation both ways (p95 and max, px of the 1280-wide photo). Optionally a close-up sheet:
photo crop | outlines (green = photo, magenta = model) | the render from the same camera (<renders>/<photo>_render.png).

  py lampscore.py <lamps.json> <idsdir> <photodir> <out.json> [--renders dir] [--sheet out.png] [--before before.json]
      [--photos n07,n06] [--title text] [--flat (ids rendered without the overlaid pass)]
"""
import json, os, sys

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

a = sys.argv[1:]
lj, idd, pdir, outj = a[:4]


def opt(k, d=None):
    return a[a.index(k) + 1] if k in a else d


only = opt('--photos').split(',') if opt('--photos') else None
rdir, sheet, before = opt('--renders'), opt('--sheet'), opt('--before')
traces = json.load(open(lj))['photos']
pal = json.load(open(os.path.join(idd, 'lamps_palette.json')))
prev = json.load(open(before)) if before else {}


def edge(m):
    return m & ~(cv2.erode(m.astype(np.uint8), np.ones((3, 3), np.uint8)) > 0)


def model_key(key):
    parts = key.split('_')
    side = parts[1]
    lk = parts[0] + ('_' + parts[2] if len(parts) > 2 else '')
    if side == 'C':
        return f'lampid_{lk}_C', 'W' if lk == 'wing' else 'A'
    return f'lampid_{lk}_{side}', 'B' if len(parts) > 2 else ('C' if lk in OVERLAID else 'A')


OVERLAID = set() if '--flat' in sys.argv else {'ind'}      # as lamps.py (--flat: renders from before that pass)


res, rows = {}, []
for ph, lamps in traces.items():
    if only and ph not in only:
        continue
    imgs = {}
    for t in 'ABCW':
        p = os.path.join(idd, f'{ph}_lamps{t}.png')
        if os.path.exists(p):
            imgs[t] = np.array(Image.open(p).convert('RGBA')).astype(int)
    if not imgs:
        continue
    H, W = next(iter(imgs.values())).shape[:2]
    photo = np.array(Image.open(os.path.join(pdir, f'{ph}.jpg')).convert('RGB').resize((W, H), Image.LANCZOS))
    rend = None
    if rdir and os.path.exists(os.path.join(rdir, f'{ph}_render.png')):
        rend = np.array(Image.open(os.path.join(rdir, f'{ph}_render.png')).convert('RGB').resize((W, H), Image.LANCZOS))
    for key, tr in sorted(lamps.items()):
        mk, t = model_key(key)
        if mk not in pal or t not in imgs:
            continue
        im = imgs[t]
        col = np.array(pal[mk])
        mm = (np.abs(im[..., :3] - col).sum(-1) <= 6) & (im[..., 3] > 0)
        # holes (where the flat proxy dips under parts on a strongly curved surface) filled: the regions are simple
        cs, _ = cv2.findContours(mm.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
        fill = np.zeros(mm.shape, np.uint8)
        cv2.drawContours(fill, cs, -1, 1, -1)
        mm = fill > 0
        pm = np.zeros((H, W), np.uint8)
        if 'poly' in tr:
            pts = np.array([[q[0], q[1]] for q in tr['poly']], np.float32)
            cv2.fillPoly(pm, [np.round(pts * 4).astype(np.int32)], 1, lineType=cv2.LINE_8, shift=2)
        else:
            cx, cy, rx, ry = tr['ell']
            cv2.ellipse(pm, (int(round(cx * 4)), int(round(cy * 4))), (int(round(rx * 4)), int(round(ry * 4))), 0, 0, 360, 1, -1,
                        shift=2)
        pm = pm > 0
        inter, uni = (pm & mm).sum(), (pm | mm).sum()
        iou = inter / uni if uni else 0.0
        ep, em = edge(pm), edge(mm)
        if em.sum() and ep.sum():
            dm = cv2.distanceTransform((~em).astype(np.uint8), cv2.DIST_L2, 5)
            dp = cv2.distanceTransform((~ep).astype(np.uint8), cv2.DIST_L2, 5)
            d = np.concatenate([dm[ep], dp[em]])
            p95, mx = float(np.percentile(d, 95)), float(d.max())
        else:
            p95 = mx = float('nan')
        r = {'iou': round(float(iou), 4), 'p95': round(p95, 2), 'max': round(mx, 2), 'model_px': int(mm.sum()),
             'photo_px': int(pm.sum())}
        res.setdefault(ph, {})[key] = r
        b = prev.get(ph, {}).get(key)
        rows.append((ph, key, r, b, pm, mm, photo, rend))
json.dump(res, open(outj, 'w'), indent=1)
print(f'{"photo":5s} {"part":10s} {"IoU":>6s} {"p95":>6s} {"max":>6s}   before')
for ph, key, r, b, *_ in rows:
    bs = f'{b["iou"]:.3f} / {b["p95"]:.1f} / {b["max"]:.1f}' if b else ''
    print(f'{ph:5s} {key:10s} {r["iou"]:6.3f} {r["p95"]:6.1f} {r["max"]:6.1f}   {bs}')

if sheet:
    font = ImageFont.load_default(size=18)
    big = ImageFont.load_default(size=26)
    blocks = []
    if opt('--title'):
        t = Image.new('RGB', (1800, 50), (20, 20, 24))
        ImageDraw.Draw(t).text((14, 10), opt('--title'), fill='white', font=big)
        blocks.append(t)
    # one row per photo and outline part (discs drawn into their unit's row)
    groups = {}
    for row in rows:
        ph, key = row[0], row[1]
        parts = key.split('_')
        g = (ph, parts[0] + '_' + parts[1])
        groups.setdefault(g, []).append(row)
    for (ph, gk), rs in groups.items():
        allm = np.zeros_like(rs[0][4])
        for _, _, _, _, pm, mm, *_ in rs:
            allm |= pm | mm
        ys, xs = np.nonzero(allm)
        if not len(xs):
            continue
        x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
        m = int(0.25 * max(x1 - x0, y1 - y0)) + 6
        H, W = allm.shape
        x0, x1, y0, y1 = max(0, x0 - m), min(W, x1 + m), max(0, y0 - m), min(H, y1 + m)
        photo, rend = rs[0][6], rs[0][7]
        k = 560 / max(x1 - x0, 1)
        k = min(k, 360 / max(y1 - y0, 1))
        size = (int((x1 - x0) * k), int((y1 - y0) * k))
        crop = Image.fromarray(photo[y0:y1, x0:x1]).resize(size, Image.LANCZOS)
        over = Image.fromarray((photo[y0:y1, x0:x1] * 0.7).astype(np.uint8)).resize(size, Image.LANCZOS)
        ov = np.array(over)
        for _, _, _, _, pm, mm, *_ in rs:
            for msk, c in ((pm, (60, 255, 60)), (mm, (255, 60, 255))):
                e = cv2.resize(edge(msk[y0:y1, x0:x1]).astype(np.uint8), size, interpolation=cv2.INTER_NEAREST)
                e = cv2.dilate(e, np.ones((2, 2), np.uint8)) > 0
                ov[e] = c
        over = Image.fromarray(ov)
        pan = [crop, over]
        if rend is not None:
            pan.append(Image.fromarray(rend[y0:y1, x0:x1]).resize(size, Image.LANCZOS))
        lines = []
        for _, key, r, b, *_ in rs:
            s = f'{key}: IoU {r["iou"]:.3f}  p95 {r["p95"]:.1f}  max {r["max"]:.1f} px'
            if b:
                s = f'{key}: IoU {b["iou"]:.3f} -> {r["iou"]:.3f}   p95 {b["p95"]:.1f} -> {r["p95"]:.1f}   max {b["max"]:.1f} -> {r["max"]:.1f} px'
            lines.append(s)
        th = 30 + 22 * len(lines)
        row = Image.new('RGB', (max(1800, 3 * size[0] + 24), size[1] + th + 8), 'white')
        d = ImageDraw.Draw(row)
        d.text((8, 4), f'{ph} {gk}  (photo | outlines: green photo, magenta model | our render, same camera)', fill='black', font=font)
        for i, s in enumerate(lines):
            d.text((8, 26 + 22 * i), s, fill=(40, 40, 40), font=font)
        for i, p in enumerate(pan):
            row.paste(p, (i * (size[0] + 8), th))
        blocks.append(row)
    Wd = max(b.size[0] for b in blocks)
    S = Image.new('RGB', (Wd, sum(b.size[1] for b in blocks)), 'white')
    y = 0
    for b in blocks:
        S.paste(b, (0, y))
        y += b.size[1]
    S.save(sheet)
    print('sheet', S.size)
