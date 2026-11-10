"""
polymask.py <polys.json> <name> <out_mask.png> [dbg.png]: car mask from a coarse outline polygon refined by GrabCut in a
narrow band around it; uncertain stretches (vertex ranges) are marked ignore (128).
polys.json: {name: {"photo": p, "map": [ox, oy, scale], "poly": [[sx, sy], ...], "uncertain": [[i0, i1(, band)], ...],
             "band": px, "ignore_band": px, "holes": [[...poly...]] (not car, e.g. under a raised wheel), "ignore": [[x0,y0,x1,y1]],
             "ignore_polys": [[...poly...]]}}
"""
import json, sys
import numpy as np, cv2
from PIL import Image

cfg = json.load(open(sys.argv[1]))[sys.argv[2]]
photo = np.array(Image.open(cfg['photo']).convert('RGB'))
h, w = photo.shape[:2]
ox, oy, s = cfg.get('map', [0, 0, 1])
conv = lambda P: np.array([[ox + x / s, oy + y / s] for x, y in P], np.float32)
poly = conv(cfg['poly'])
band = int(cfg.get('band', 10))
inside = np.zeros((h, w), np.uint8)
cv2.fillPoly(inside, [np.round(poly).astype(np.int32)], 1)
for hole in cfg.get('holes', []):
    cv2.fillPoly(inside, [np.round(conv(hole)).astype(np.int32)], 0)
k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * band + 1, 2 * band + 1))
gc = np.full((h, w), cv2.GC_BGD, np.uint8)
gc[cv2.dilate(inside, k).astype(bool)] = cv2.GC_PR_BGD
gc[inside.astype(bool)] = cv2.GC_PR_FGD
gc[cv2.erode(inside, k).astype(bool)] = cv2.GC_FGD
bgd = np.zeros((1, 65), np.float64); fgd = np.zeros((1, 65), np.float64)
cv2.grabCut(cv2.cvtColor(photo, cv2.COLOR_RGB2BGR), gc, None, bgd, fgd, 6, cv2.GC_INIT_WITH_MASK)
P = (gc == cv2.GC_FGD) | (gc == cv2.GC_PR_FGD)
n, lab, st, _ = cv2.connectedComponentsWithStats(P.astype(np.uint8), 8)
if n > 1:
    P = lab == (1 + int(np.argmax(st[1:, cv2.CC_STAT_AREA])))
inv = (~P).astype(np.uint8)
n2, lab2, st2, _ = cv2.connectedComponentsWithStats(inv, 4)
for j in range(1, n2):
    x, y, ww, hh = st2[j, :4]
    if x > 0 and y > 0 and x + ww < w and y + hh < h:
        P[lab2 == j] = True
P = cv2.morphologyEx(P.astype(np.uint8), cv2.MORPH_OPEN, np.ones((3, 3), np.uint8)).astype(bool)
if cfg.get('polygon_only'):
    P = inside.astype(bool)
M = np.where(P, 255, 0).astype(np.uint8)
ib = int(cfg.get('ignore_band', 22))
for u in cfg.get('uncertain', []):
    i0, i1 = u[0], u[1]
    bw = int(u[2]) if len(u) > 2 else ib
    idx = list(range(i0, i1 + 1)) if i1 >= i0 else list(range(i0, len(poly))) + list(range(0, i1 + 1))
    seg = poly[idx]
    m = np.zeros((h, w), np.uint8)
    cv2.polylines(m, [np.round(seg).astype(np.int32)], False, 1, thickness=2 * bw + 1)
    M[m.astype(bool)] = 128
for x0, y0, x1, y1 in cfg.get('ignore', []):
    M[int(y0):int(y1), int(x0):int(x1)] = 128
for ip in cfg.get('ignore_polys', []):      # e.g. the wing: neither car nor background
    m = np.zeros((h, w), np.uint8)
    cv2.fillPoly(m, [np.round(conv(ip)).astype(np.int32)], 1)
    M[m.astype(bool)] = 128
Image.fromarray(M).save(sys.argv[3])
if len(sys.argv) > 4:
    ov = (photo * 0.65).astype(np.uint8)
    edge = cv2.morphologyEx(P.astype(np.uint8), cv2.MORPH_GRADIENT, np.ones((3, 3), np.uint8)).astype(bool)
    ov[M == 128] = (ov[M == 128] * 0.5 + np.array([0, 0, 120])).astype(np.uint8)
    ov[edge] = [60, 255, 60]
    cv2.polylines(ov, [np.round(poly).astype(np.int32)], True, (255, 60, 255), 1)
    Image.fromarray(ov).save(sys.argv[4])
