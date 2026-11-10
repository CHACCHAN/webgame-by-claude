"""lampfit.py: the lamps' outlines, measured per lamp. The traced lens outlines (lamps.json) against the model's lamp
lenses in loop.py's material-id renders (same camera and pose): IoU, and the outline deviation both ways (max and
p95, px at 1280 width). Also a close-up per lamp: the photo crop with both outlines (green = photo, magenta =
model), next to the render crop (<name>_lamps.png in the render dir when there is one, else the shaded render).

  py lampfit.py <lamps.json> <renderdir> <photodir> <outdir> [--photos r29,r07]  -> <outdir>/lamps.json + crops
"""
import json, os, sys

import cv2
import numpy as np
from PIL import Image

a = sys.argv[1:]
lj, rdir, pdir, out = a[:4]
only = a[a.index('--photos') + 1].split(',') if '--photos' in a else None
os.makedirs(out, exist_ok=True)
MATS = {'hl': {'headlight'}, 'ind': {'lens_clear', 'amber'}, 'tl': {'taillight'}}
db = json.load(open(lj))['photos']
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
    for cand in (rp, os.path.join(rdir, f'{ph}_shade.png')):
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
        n, cl = cv2.connectedComponents(mm.astype(np.uint8))
        if n > 1:
            ov = [((cl == i) & tm).sum() for i in range(1, n)]
            if max(ov) > 0:
                keep = [int(np.argmax(ov)) + 1]
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
        # close-up: photo with outlines | render
        crop = photo[Y0:Y1, X0:X1].copy()
        ov = crop.copy()
        ov[et[Y0:Y1, X0:X1]] = (0, 255, 0)
        ov[em[Y0:Y1, X0:X1]] = (255, 0, 255)
        tiles = [crop, ov] + ([rimg[Y0:Y1, X0:X1]] if rimg is not None else [])
        s = 240 / max(1, (Y1 - Y0))
        tiles = [cv2.resize(t, (int((X1 - X0) * s), 240), interpolation=cv2.INTER_CUBIC if s > 1 else cv2.INTER_AREA) for t in tiles]
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
