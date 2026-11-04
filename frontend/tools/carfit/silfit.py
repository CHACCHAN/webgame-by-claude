"""
silfit.py: score a car model's silhouette against a photo, from the same (solved) camera.

  $PY silfit.py <photo.jpg> <render.png> <outdir> [--name tag] [--band 0.06] [--ignore x0,y0,x1,y1 ...]
               [--ids ids.png] [--mask photo_mask.png]

  PY = PYTHONPATH=<scratchpad>/pyfit /home/dev/.local/opt/blender-5.2.3-linux-x64/5.2/python/bin/python3.13

Render both images with silrender.py (Blender, from your solved cameras): <render.png> = <name>_sil.png,
--ids <name>_ids.png. <render.png> is an RGBA render of the model alone (Cycles/EEVEE with film_transparent = True, no ground plane, no
shadow catcher) from the camera solved for <photo>, at the photo's aspect ratio. It is resized to the photo.

The car in the photo is segmented by GrabCut, seeded by the render: far outside the render's silhouette is background,
deep inside it is car, the band in between (±band × the car's bbox size) is left for GrabCut to decide. So the photo mask
does not depend on the model except near its outline, and a model edge that is off by less than the band is found.
Check the photo mask in the overlay once per photo; if GrabCut got it wrong (a shadow, a car behind, a kerb), paint a
mask by hand (white = car, black = not, grey 128 = ignore) and pass it with --mask, or exclude areas with --ignore.

Outputs in <outdir>:
  <tag>_overlay.png  photo dimmed; render-only area red, photo-only area blue, photo outline green, render outline
                     red, the model's feature lines (--ids: borders between materials: glass, lamps, openings,
                     trim) yellow, so window, lamp and intake outlines can be compared with the photo
  <tag>_mask.png     the photo mask used (reuse with --mask after fixing it)
  <tag>.json         IoU, boundary distances in % of the car's bbox width, and per-zone signed offsets
Signed offset: + where the render's outline lies outside the photo's (model too big there), - inside (too small).
Zones: 3 columns (left / middle / right third of the car's bbox in the image) × 2 rows (top / bottom half).
"""
import json
import os
import sys

import cv2
import numpy as np
from PIL import Image


def args():
    a = sys.argv[1:]
    if len(a) < 3:
        print(__doc__)
        sys.exit(1)
    o = {'photo': a[0], 'render': a[1], 'out': a[2], 'name': None, 'band': 0.06, 'ignore': [], 'ids': None, 'mask': None}
    i = 3
    while i < len(a):
        k = a[i].lstrip('-')
        if k == 'ignore':
            o['ignore'].append([float(v) for v in a[i + 1].split(',')])
        elif k == 'band':
            o['band'] = float(a[i + 1])
        else:
            o[k] = a[i + 1]
        i += 2
    o['name'] = o['name'] or os.path.splitext(os.path.basename(o['photo']))[0]
    return o


def largest(mask):
    n, lab, stats, _ = cv2.connectedComponentsWithStats(mask.astype(np.uint8), 8)
    if n <= 1:
        return mask.astype(bool)
    k = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    m = lab == k
    # fill holes (windows seen through, wheel spokes)
    inv = (~m).astype(np.uint8)
    n2, lab2, stats2, _ = cv2.connectedComponentsWithStats(inv, 4)
    h, w = m.shape
    for j in range(1, n2):
        x, y, ww, hh = stats2[j, :4]
        if x > 0 and y > 0 and x + ww < w and y + hh < h:
            m[lab2 == j] = True
    return m


def outline(m):
    m8 = m.astype(np.uint8)
    return (m8 - cv2.erode(m8, np.ones((3, 3), np.uint8))).astype(bool)


def main():
    o = args()
    os.makedirs(o['out'], exist_ok=True)
    photo = np.array(Image.open(o['photo']).convert('RGB'))
    h, w = photo.shape[:2]
    rimg = Image.open(o['render']).convert('RGBA')
    if rimg.size != (w, h):
        ra, pa = rimg.size[0] / rimg.size[1], w / h
        if abs(ra - pa) / pa > 0.01:
            print(f'warning: render aspect {ra:.4f} != photo aspect {pa:.4f}: the render is stretched')
        rimg = rimg.resize((w, h), Image.LANCZOS)
    R = np.array(rimg)[:, :, 3] > 127
    if not R.any():
        sys.exit('render has no alpha silhouette: render with film_transparent and no ground')
    ys, xs = np.nonzero(R)
    bw = xs.max() - xs.min() + 1
    bh = ys.max() - ys.min() + 1
    band = max(4, int(round(o['band'] * max(bw, bh))))
    ignore = np.zeros((h, w), bool)
    for x0, y0, x1, y1 in o['ignore']:
        ignore[int(y0):int(y1), int(x0):int(x1)] = True

    if o['mask']:
        mm = np.array(Image.open(o['mask']).convert('L').resize((w, h), Image.NEAREST))
        P = mm > 192
        ignore |= (mm > 64) & (mm <= 192)
    else:
        k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * band + 1, 2 * band + 1))
        dil = cv2.dilate(R.astype(np.uint8), k).astype(bool)
        ero = cv2.erode(R.astype(np.uint8), k).astype(bool)
        gc = np.full((h, w), cv2.GC_BGD, np.uint8)
        gc[dil] = cv2.GC_PR_BGD
        gc[R] = cv2.GC_PR_FGD
        gc[ero] = cv2.GC_FGD
        bgd = np.zeros((1, 65), np.float64)
        fgd = np.zeros((1, 65), np.float64)
        bgr = cv2.cvtColor(photo, cv2.COLOR_RGB2BGR)
        cv2.grabCut(bgr, gc, None, bgd, fgd, 6, cv2.GC_INIT_WITH_MASK)
        P = largest((gc == cv2.GC_FGD) | (gc == cv2.GC_PR_FGD))
    R = largest(R)

    valid = ~ignore
    inter = (R & P & valid).sum()
    union = ((R | P) & valid).sum()
    iou = float(inter / max(union, 1))

    # boundary distances: render outline → photo outline, signed by inside/outside the photo mask
    eR, eP = outline(R) & valid, outline(P) & valid
    dtP = cv2.distanceTransform((~eP).astype(np.uint8), cv2.DIST_L2, 5)
    ry, rx = np.nonzero(eR)
    d = dtP[ry, rx]
    sign = np.where(P[ry, rx], -1.0, 1.0)
    sd = d * sign / bw * 100.0
    dtR = cv2.distanceTransform((~eR).astype(np.uint8), cv2.DIST_L2, 5)
    py_, px_ = np.nonzero(eP)
    dp = dtR[py_, px_] / bw * 100.0
    x0, y0 = xs.min(), ys.min()
    zones = {}
    for ci, cn in enumerate(['left', 'middle', 'right']):
        for ri, rn in enumerate(['top', 'bottom']):
            sel = (rx >= x0 + ci * bw / 3) & (rx < x0 + (ci + 1) * bw / 3) & (ry >= y0 + ri * bh / 2) & (ry < y0 + (ri + 1) * bh / 2)
            if sel.sum() > 5:
                zones[f'{rn}-{cn}'] = {'mean_signed_pct': round(float(sd[sel].mean()), 2), 'p90_abs_pct': round(float(np.percentile(np.abs(sd[sel]), 90)), 2)}
    res = {
        'photo': o['photo'], 'render': o['render'], 'iou': round(iou, 4),
        'render_to_photo_mean_pct': round(float(np.abs(sd).mean()), 2),
        'render_to_photo_p95_pct': round(float(np.percentile(np.abs(sd), 95)), 2),
        'photo_to_render_mean_pct': round(float(dp.mean()), 2),
        'photo_to_render_p95_pct': round(float(np.percentile(dp, 95)), 2),
        'max_pct': round(float(max(np.abs(sd).max(), dp.max())), 2),
        'band_px': band, 'car_bbox_px': [int(bw), int(bh)], 'zones': zones,
        'note': 'pct = % of the car bbox width in the image; signed + = model outline outside the photo outline',
    }
    with open(os.path.join(o['out'], f"{o['name']}.json"), 'w') as f:
        json.dump(res, f, indent=1)
    Image.fromarray((P * 255).astype(np.uint8)).save(os.path.join(o['out'], f"{o['name']}_mask.png"))

    ov = (photo.astype(np.float32) * 0.55).astype(np.float32)
    only_r = R & ~P
    only_p = P & ~R
    ov[only_r] = ov[only_r] * 0.4 + np.array([255, 40, 40]) * 0.6
    ov[only_p] = ov[only_p] * 0.4 + np.array([40, 110, 255]) * 0.6
    thick = np.ones((3, 3), np.uint8)
    ov[cv2.dilate(outline(P).astype(np.uint8), thick).astype(bool)] = [60, 255, 60]
    ov[cv2.dilate(outline(R).astype(np.uint8), thick).astype(bool)] = [255, 50, 50]
    if o['ids']:
        L = np.array(Image.open(o['ids']).convert('RGBA').resize((w, h), Image.NEAREST)).astype(np.int32)
        c = L[:, :, :3]
        a = L[:, :, 3] > 127
        lm = np.zeros((h, w), bool)
        dx = np.abs(c[:, 1:] - c[:, :-1]).sum(axis=2) > 24
        dy = np.abs(c[1:] - c[:-1]).sum(axis=2) > 24
        lm[:, 1:] |= dx & a[:, 1:] & a[:, :-1]
        lm[1:] |= dy & a[1:] & a[:-1]
        ov[lm] = [255, 230, 40]
    ov[ignore] = ov[ignore] * 0.5
    Image.fromarray(np.clip(ov, 0, 255).astype(np.uint8)).save(os.path.join(o['out'], f"{o['name']}_overlay.png"))
    print(json.dumps({k: res[k] for k in ['iou', 'render_to_photo_mean_pct', 'render_to_photo_p95_pct', 'photo_to_render_p95_pct', 'max_pct']}))
    for z, v in zones.items():
        print(f'  {z:14s} signed {v["mean_signed_pct"]:+6.2f}%  p90 {v["p90_abs_pct"]:5.2f}%')


if __name__ == '__main__':
    main()
