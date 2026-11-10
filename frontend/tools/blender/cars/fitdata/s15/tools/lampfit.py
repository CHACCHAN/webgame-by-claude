"""lampfit.py: the lamps' outlines, measured per lamp. The traced lens outlines (lamps.json) against the model's lamp
lenses in loop.py's material-id renders (same camera and pose): IoU, and the outline deviation both ways (max and
p95, px at 1280 width). Also a close-up per lamp: the photo crop with both outlines (green = photo, magenta =
model), next to the render crop (<name>_lamps.png in the render dir when there is one, else the shaded render).

  py lampfit.py <lamps.json> <renderdir> <photodir> <outdir> [--photos r29,r07] [--hi <photodir at a higher resolution>]  -> <outdir>/lamps.json + crops
"""
import json, os, sys

import cv2
import numpy as np
from PIL import Image

a = sys.argv[1:]
lj, rdir, pdir, out = a[:4]
only = a[a.index('--photos') + 1].split(',') if '--photos' in a else None
HI = a[a.index('--hi') + 1] if '--hi' in a else None
CLOSE = int(a[a.index('--close') + 1]) if '--close' in a else 1
_hi = {}


def hi_img(ph, W, H):
    if ph not in _hi:
        p = os.path.join(HI, f'{ph}.jpg') if HI else None
        if p and os.path.exists(p):
            _hi[ph] = np.array(Image.open(p).convert('RGB'))
        else:
            _hi[ph] = np.array(Image.open(os.path.join(pdir, f'{ph}.jpg')).convert('RGB').resize((W, H), Image.LANCZOS))
    return _hi[ph]
os.makedirs(out, exist_ok=True)
DB = json.load(open(lj))
db = DB['photos']
# lamp kind (the name's prefix before '_') -> the model's materials that make up that lens (lamps.json 'kinds')
MATS = {k: set(v) for k, v in DB.get('kinds', {'hl': ['headlight'], 'ind': ['lens_clear', 'amber'], 'tl': ['taillight']}).items()}
pal = json.load(open(os.path.join(rdir, 'palette.json')))
names = sorted(pal)
cols = np.array([pal[k] for k in names], float)


def edge(m):
    return (m ^ (cv2.erode(m.astype(np.uint8), np.ones((3, 3), np.uint8)) > 0))


res = {}
rows = []
for ph, lamps in db.items():
    if only and ph not in only:
        continue
    ids_p = os.path.join(rdir, f'{ph}_ids.png')
    if not os.path.exists(ids_p):
        continue
    ids = np.array(Image.open(ids_p).convert('RGBA'))
    H, W = ids.shape[:2]
    photo = np.array(Image.open(os.path.join(pdir, f'{ph}.jpg')).convert('RGB').resize((W, H), Image.LANCZOS))
    rp = os.path.join(rdir, f'{ph}_lamps.png')
    rimg = None
    for cand in (rp, os.path.join(rdir, f'{ph}_full.png'), os.path.join(rdir, f'{ph}_shade.png')):
        if os.path.exists(cand):
            rimg = np.array(Image.open(cand).convert('RGB').resize((W, H), Image.LANCZOS))
            break
    sil = ids[:, :, 3] > 127
    rgb = ids[:, :, :3].reshape(-1, 3).astype(float)
    lab = np.argmin(((rgb[:, None, :] - cols[None]) ** 2).sum(-1), 1).reshape(H, W)
    lab[~sil] = -1
    for lamp, d in lamps.items():
        poly = np.array(d['poly'], float)
        tm = np.zeros((H, W), np.uint8)
        cv2.fillPoly(tm, [np.round(poly * 4).astype(np.int32)], 1, shift=2)
        tm = tm > 0
        x0, y0 = poly.min(0)
        x1, y1 = poly.max(0)
        pad = max(25, 0.6 * max(x1 - x0, y1 - y0))
        X0, Y0, X1, Y1 = int(max(0, x0 - pad)), int(max(0, y0 - pad)), int(min(W, x1 + pad)), int(min(H, y1 + pad))
        roi = np.zeros((H, W), bool)
        roi[Y0:Y1, X0:X1] = True
        kind = lamp.split('_')[0]
        mm = np.isin(lab, [names.index(k) for k in MATS[kind] if k in names]) & roi
        # a lens split into cells by thin bars (the model's frame between them): close the bars, keep every cell that
        # overlaps the traced lens
        mm = cv2.morphologyEx(mm.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((CLOSE, CLOSE), np.uint8)) > 0
        n, cl = cv2.connectedComponents(mm.astype(np.uint8))
        if n > 1:
            ov = [((cl == i) & tm).sum() for i in range(1, n)]
            if max(ov) > 0:
                keep = [i + 1 for i, o in enumerate(ov) if o > 0.15 * max(ov)]
            else:
                c = poly.mean(0)
                dist = []
                for i in range(1, n):
                    yy, xx = np.nonzero(cl == i)
                    dist.append(np.hypot(xx.mean() - c[0], yy.mean() - c[1]))
                keep = [int(np.argmin(dist)) + 1]
            mm = np.isin(cl, keep)
        inter, uni = (mm & tm).sum(), (mm | tm).sum()
        iou = inter / max(uni, 1)
        et, em = edge(tm), edge(mm)
        if em.sum() and et.sum():
            dt_m = cv2.distanceTransform((~em).astype(np.uint8), cv2.DIST_L2, 5)
            dt_t = cv2.distanceTransform((~et).astype(np.uint8), cv2.DIST_L2, 5)
            dd = np.concatenate([dt_m[et], dt_t[em]])
            mx, p95 = float(dd.max()), float(np.percentile(dd, 95))
        else:
            mx = p95 = float('nan')
        # centroid and size differences (px)
        def stats(m):
            yy, xx = np.nonzero(m)
            return (xx.mean(), yy.mean(), xx.max() - xx.min() + 1, yy.max() - yy.min() + 1) if len(xx) else (np.nan,) * 4
        st, sm = stats(tm), stats(mm)
        r = {'iou': round(float(iou), 4), 'max_px': round(mx, 1), 'p95_px': round(p95, 1),
             'dc_px': [round(float(sm[0] - st[0]), 1), round(float(sm[1] - st[1]), 1)],
             'size_px': [round(float(st[2]), 1), round(float(st[3]), 1)],
             'dsize_px': [round(float(sm[2] - st[2]), 1), round(float(sm[3] - st[3]), 1)]}
        res.setdefault(ph, {})[lamp] = r
        rows.append((ph, lamp, r))
        # close-up: photo with outlines | render (photo from --hi when given: the same photo at a higher resolution)
        S = 240 / max(1, (Y1 - Y0))
        cw, ch = int((X1 - X0) * S), 240
        src = hi_img(ph, W, H)
        k = src.shape[1] / W
        crop = cv2.resize(src[int(Y0 * k):int(Y1 * k), int(X0 * k):int(X1 * k)], (cw, ch), interpolation=cv2.INTER_AREA if S < k else cv2.INTER_CUBIC)
        ov = crop.copy()
        for m_, col in ((tm, (0, 255, 0)), (mm, (255, 0, 255))):
            cs, _ = cv2.findContours(m_.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
            cs = [np.round((c.astype(float) + 0.5 - [X0, Y0]) * S).astype(np.int32) for c in cs]
            cv2.polylines(ov, cs, True, col, 2, cv2.LINE_AA)
        tiles = [crop, ov] + ([cv2.resize(rimg[Y0:Y1, X0:X1], (cw, ch), interpolation=cv2.INTER_CUBIC)] if rimg is not None else [])
        gap = np.full((240, 6, 3), 255, np.uint8)
        row = tiles[0]
        for t in tiles[1:]:
            row = np.concatenate([row, gap, t], 1)
        Image.fromarray(row).save(os.path.join(out, f'{ph}_{lamp}.png'))
json.dump(res, open(os.path.join(out, 'lamps.json'), 'w'), indent=1)
print(f'{"photo":5s} {"lamp":6s} {"IoU":>6s} {"max":>6s} {"p95":>6s}  {"dcentre px":>14s}  {"size px":>13s}  {"dsize px":>13s}')
for ph, lamp, r in rows:
    print(f'{ph:5s} {lamp:6s} {r["iou"]:6.3f} {r["max_px"]:6.1f} {r["p95_px"]:6.1f}  {r["dc_px"][0]:+6.1f} {r["dc_px"][1]:+6.1f}  '
          f'{r["size_px"][0]:6.1f} {r["size_px"][1]:6.1f}  {r["dsize_px"][0]:+6.1f} {r["dsize_px"][1]:+6.1f}')
