"""
handmask.py <fit dir> [photos]: photo masks that owe nothing to the model (fitdata/<id>/masks/<photo>.png: white = the
tank, black = not, grey 128 = not judged). GrabCut from a box around the tank, steered by hand-drawn hints, then
overruled by hand-outlined parts; all of it from `<fit dir>/handmask.json`:
  {"<photo>": {"rect": [x0, y0, x1, y1],            the tank lies inside (outside = certainly not)
               "fg": [[[u, v], …], …],              polygons certainly tank (strokes: a polygon of 2 points = a line
               "bg": [[[u, v], …], …],              of width `w`), certainly not tank
               "w": 9,
               "ign": [[x0, y0, x1, y1], …],        boxes not judged (people in front, another tank, the ground line)
               "ignpoly": [[[u, v], …], …],         polygons not judged
               "hand": [[[x0, y0, x1, y1], [[u, v], …]], …]}}   inside the box the tank is the polygon, the rest not
Photos: PHOTOS (default ~/.local/opt/carfit/tanks/<id>/ref). Also writes CHK/<photo>_chk.jpg (default <photos>/../chk,
never in the repository: it is the photo; outline green,
unjudged dimmed, hand boxes blue). Masks made this way do not lean on the model, so the gate can judge it.
"""
import json
import os
import sys

import cv2
import numpy as np


def poly(m, pts, val, w):
    p = np.round(np.array(pts, float) * 8).astype(np.int32)
    if len(pts) == 2:
        cv2.line(m, tuple(p[0]), tuple(p[1]), val, w, shift=3)
    else:
        cv2.fillPoly(m, [p], val, shift=3)


def main():
    fit = sys.argv[1].rstrip('/')
    only = sys.argv[2].split(',') if len(sys.argv) > 2 else None
    tid = os.path.basename(fit)
    photos_dir = os.environ.get('PHOTOS', os.path.expanduser(f'~/.local/opt/carfit/tanks/{tid}/ref'))
    cfg = json.load(open(fit + '/handmask.json'))
    os.makedirs(fit + '/masks', exist_ok=True)
    chk_dir = os.environ.get('CHK', os.path.join(os.path.dirname(photos_dir.rstrip('/')), 'chk'))
    os.makedirs(chk_dir, exist_ok=True)
    for ph, c in cfg.items():
        if ph.startswith('_') or (only and ph not in only):
            continue
        im = cv2.imread(f'{photos_dir}/{ph}.jpg')
        H, W = im.shape[:2]
        x0, y0, x1, y1 = c['rect']
        gc = np.full((H, W), cv2.GC_BGD, np.uint8)
        gc[y0:y1, x0:x1] = cv2.GC_PR_FGD
        w = c.get('w', 9)
        for p in c.get('bg', []):
            poly(gc, p, int(cv2.GC_BGD), w)
        for p in c.get('fg', []):
            poly(gc, p, int(cv2.GC_FGD), w)
        bgd, fgd = np.zeros((1, 65), np.float64), np.zeros((1, 65), np.float64)
        pad = 20
        X0, Y0, X1, Y1 = max(0, x0 - pad), max(0, y0 - pad), min(W, x1 + pad), min(H, y1 + pad)
        sub = gc[Y0:Y1, X0:X1].copy()
        # GrabCut's k-means starts from the process-wide random state: seeded per photo, the same hints give the same
        # mask whichever photos are made in one run, and in what order
        cv2.setRNGSeed(0)
        np.random.seed(0)
        cv2.grabCut(im[Y0:Y1, X0:X1], sub, None, bgd, fgd, 8, cv2.GC_INIT_WITH_MASK)
        gc[Y0:Y1, X0:X1] = sub
        tank = np.isin(gc, (cv2.GC_FGD, cv2.GC_PR_FGD)).astype(np.uint8)
        n, lab, st, _ = cv2.connectedComponentsWithStats(tank)
        if n > 1:
            tank = (lab == 1 + int(np.argmax(st[1:, cv2.CC_STAT_AREA]))).astype(np.uint8)
        # holes inside the tank smaller than 0.2 % of it are filled (shadowed recesses)
        inv = (1 - tank).astype(np.uint8)
        n, lab, st, _ = cv2.connectedComponentsWithStats(inv)
        for k in range(1, n):
            x, y, ww, hh, a = st[k]
            if a < 0.002 * tank.sum() and x > 0 and y > 0 and x + ww < W and y + hh < H:
                tank[lab == k] = 1
        m = tank * 255
        judged = np.ones((H, W), np.uint8)
        for bx in c.get('ign', []):
            judged[bx[1]:bx[3], bx[0]:bx[2]] = 0
        for p in c.get('ignpoly', []):
            poly(judged, p, 0, w)
        for bx, pg in c.get('hand', []):
            box = np.zeros((H, W), np.uint8)
            poly(box, pg, 255, w)
            m[bx[1]:bx[3], bx[0]:bx[2]] = box[bx[1]:bx[3], bx[0]:bx[2]]
            judged[bx[1]:bx[3], bx[0]:bx[2]] = 1
        m = m.astype(np.uint8)
        m[judged == 0] = 128
        cv2.imwrite(f'{fit}/masks/{ph}.png', m)
        chk = im.copy()
        dim = judged == 0
        chk[dim] = (chk[dim] * 0.35).astype(np.uint8)
        e = cv2.morphologyEx((m == 255).astype(np.uint8) * 255, cv2.MORPH_GRADIENT, np.ones((3, 3), np.uint8)) > 0
        chk[cv2.dilate(e.astype(np.uint8), np.ones((3, 3), np.uint8)) > 0] = (60, 255, 60)
        for bx, _ in c.get('hand', []):
            cv2.rectangle(chk, tuple(bx[:2]), tuple(bx[2:]), (255, 120, 0), 2)
        cv2.imwrite(f'{chk_dir}/{ph}_chk.jpg', chk, [cv2.IMWRITE_JPEG_QUALITY, 85])
        print(ph, 'tank', int((m == 255).sum()), 'px, not judged', int((m == 128).sum()), 'px')


if __name__ == '__main__':
    main()
