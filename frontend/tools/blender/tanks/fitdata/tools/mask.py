"""
mask.py <tris.npz> <fit dir> [photos]: the photo masks for the gate (fitdata/<id>/masks/<photo>.png: white = the tank,
black = not, grey 128 = not judged), by GrabCut seeded with the model's silhouette through the solved camera, then
overruled by hand where it matters (fit dir `maskcfg.json`).

The lesson of the cars (CLAUDE.md): a mask grown from the model's own outline agrees with the model's mistakes. So the
seed is loose (only a core well inside the model is sure tank, only far outside is sure not), GrabCut decides the band
by colour, and every part of the outline that the fit leans on is outlined by hand in `maskcfg.json`:
  {"<photo>": {"ign": [[x0, y0, x1, y1], …],          boxes not judged (people, another vehicle, a branch)
               "low": 0.06,                           share of the tank's height above its lowest line not judged
                                                      (tracks and their shadow on the ground look alike)
               "hand": [[[x0, y0, x1, y1], [[u, v], …]], …],   inside the box the tank is what the polygon holds,
                                                      the rest of the box is not tank (all judged)
               "cut": [[[u, v], …], …]}}              polygons that are certainly not tank (sky between gun and roof…)
Photos: PHOTOS (default ~/.local/opt/carfit/tanks/<id>/ref). Writes masks/<photo>.png and masks/<photo>_chk.jpg
(the mask's outline green, unjudged dimmed, the hand boxes blue).
"""
import json
import math
import os
import sys

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from ba import project, turret_pose, gun_pose  # noqa: E402
from gate import silhouette  # noqa: E402


def main():
    npz, fit = sys.argv[1], sys.argv[2].rstrip('/')
    only = sys.argv[3].split(',') if len(sys.argv) > 3 else None
    tid = os.path.basename(fit)
    photos_dir = os.environ.get('PHOTOS', os.path.expanduser(f'~/.local/opt/carfit/tanks/{tid}/ref'))
    Z = np.load(npz, allow_pickle=True)
    P = Z['P'].astype(np.float64)
    names = [str(n) for n in Z['names']]
    kind = np.array(['gun' if names[o].startswith('gun') else 'turret' if names[o].startswith('turret') else 'hull' for o in Z['O']])
    ba = json.load(open(fit + '/fit/ba.json'))
    if 'axis' in Z.files:
        tz, gy, gz = (float(v) for v in Z['axis'])
    else:
        tz, gy, gz = ba['axis']['tz'], ba['axis']['gy'], ba['axis']['gz']
    cfgp = fit + '/maskcfg.json'
    cfg = json.load(open(cfgp)) if os.path.exists(cfgp) else {}
    os.makedirs(fit + '/masks', exist_ok=True)
    for ph, cam in ba['cams'].items():
        if only and ph not in only:
            continue
        c = cfg.get(ph, {})
        W, H = cam[7]
        im = cv2.resize(cv2.imread(f'{photos_dir}/{ph}.jpg'), (W, H))
        pose = ba['pose'][ph]
        V = P.reshape(-1, 3).copy()
        k3 = np.repeat(kind, 3)
        g = k3 == 'gun'
        V[g] = gun_pose(V[g], math.radians(pose['theta_deg']), gy, gz)
        t = (k3 == 'turret') | g
        V[t] = turret_pose(V[t], math.radians(pose['psi_deg']), tz)
        uv = project(cam, V, W, H)
        sil = silhouette(uv.reshape(-1, 3, 2), W, H)
        ys, xs = np.nonzero(sil)
        size = max(xs.max() - xs.min(), ys.max() - ys.min())
        k = max(3, int(size * 0.035))
        core = cv2.erode(sil, np.ones((k, k), np.uint8))
        near = cv2.dilate(sil, np.ones((k * 2, k * 2), np.uint8))
        far = cv2.dilate(sil, np.ones((k * 5, k * 5), np.uint8))
        gc = np.full((H, W), cv2.GC_BGD, np.uint8)
        gc[far > 0] = cv2.GC_PR_BGD
        gc[near > 0] = cv2.GC_PR_FGD
        gc[core > 0] = cv2.GC_FGD
        bgd, fgd = np.zeros((1, 65), np.float64), np.zeros((1, 65), np.float64)
        x0, y0 = max(0, xs.min() - k * 6), max(0, ys.min() - k * 6)
        x1, y1 = min(W, xs.max() + k * 6), min(H, ys.max() + k * 6)
        sub = gc[y0:y1, x0:x1].copy()
        cv2.grabCut(im[y0:y1, x0:x1], sub, None, bgd, fgd, 6, cv2.GC_INIT_WITH_MASK)
        gc[y0:y1, x0:x1] = sub
        tank = np.isin(gc, (cv2.GC_FGD, cv2.GC_PR_FGD))
        # the largest blob only, holes filled
        n, lab, st, _ = cv2.connectedComponentsWithStats(tank.astype(np.uint8))
        if n > 1:
            tank = lab == 1 + int(np.argmax(st[1:, cv2.CC_STAT_AREA]))
        m = np.where(tank, 255, 0).astype(np.uint8)
        judged = np.ones((H, W), bool)
        # the tracks' feet and their shadow: not judged (by the model's lowest line in each column band)
        low = c.get('low', 0.06)
        ground = uv[:, 1].max()
        top = uv[:, 1].min()
        judged[int(ground - low * (ground - top)):, :] = False
        for bx in c.get('ign', []):
            judged[bx[1]:bx[3], bx[0]:bx[2]] = False
        for poly in c.get('cut', []):
            cv2.fillPoly(m, [np.round(np.array(poly) * 8).astype(np.int32)], 0, shift=3)
        for bx, poly in c.get('hand', []):
            box = np.zeros((H, W), np.uint8)
            cv2.fillPoly(box, [np.round(np.array(poly) * 8).astype(np.int32)], 255, shift=3)
            m[bx[1]:bx[3], bx[0]:bx[2]] = box[bx[1]:bx[3], bx[0]:bx[2]]
            judged[bx[1]:bx[3], bx[0]:bx[2]] = True
        m[~judged] = 128
        cv2.imwrite(f'{fit}/masks/{ph}.png', m)
        chk = im.copy()
        chk[~judged] = (chk[~judged] * 0.35).astype(np.uint8)
        e = cv2.morphologyEx((m == 255).astype(np.uint8) * 255, cv2.MORPH_GRADIENT, np.ones((3, 3), np.uint8)) > 0
        chk[cv2.dilate(e.astype(np.uint8), np.ones((3, 3), np.uint8)) > 0] = (60, 230, 60)
        for bx, _ in c.get('hand', []):
            cv2.rectangle(chk, tuple(bx[:2]), tuple(bx[2:]), (255, 120, 0), 2)
        cv2.imwrite(f'{fit}/masks/{ph}_chk.jpg', chk, [cv2.IMWRITE_JPEG_QUALITY, 85])
        print(ph, 'mask', int((m == 255).sum()), 'px tank,', int((m == 128).sum()), 'px not judged')


if __name__ == '__main__':
    main()
