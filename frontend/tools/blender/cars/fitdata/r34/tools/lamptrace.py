"""lamptrace.py: the round tail lamps' red lenses traced on a photo: inside a disc round each rough centre the red pixels
(R well above G and B) are segmented, holes (reflections, the amber centre) filled, and an ellipse fitted to the
outline of the part holding the centre (a circle seen at an angle). Prints the ellipses and writes them as
polygons into lamps.json (photo coordinates at 1280 px width) and a check image.

  py lamptrace.py <photo> <lamps.json> <name> <check.png> lamp=x,y,r [lamp=x,y,r ...] [--red 40] [--minr 60]
"""
import json, math, sys

import cv2
import numpy as np
from PIL import Image

a = sys.argv[1:]
red_t = float(a[a.index("--red") + 1]) if "--red" in a else 40.0
min_r = float(a[a.index("--minr") + 1]) if "--minr" in a else 60.0
photo, lj, name, chk = a[:4]
img = np.array(Image.open(photo).convert('RGB')).astype(float)
R, G, B = img[..., 0], img[..., 1], img[..., 2]
red = (R - np.maximum(G, B) > red_t) & (R > min_r)
vis = img.astype(np.uint8).copy()
db = json.load(open(lj))
out = db.setdefault('photos', {}).setdefault(name, {})
for spec in a[4:]:
    if '=' not in spec:
        continue
    k, v = spec.split('=')
    x, y, r = (float(t) for t in v.split(','))
    m = np.zeros(red.shape, np.uint8)
    cv2.circle(m, (int(x), int(y)), int(r * 1.35), 1, -1)
    lm = (red & (m > 0)).astype(np.uint8)
    lm = cv2.morphologyEx(lm, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    n, lab = cv2.connectedComponents(lm)
    # the component holding most of the inner disc
    inner = np.zeros_like(lm)
    cv2.circle(inner, (int(x), int(y)), int(r * 0.6), 1, -1)
    best = max(range(1, n), key=lambda i: ((lab == i) & (inner > 0)).sum())
    comp = (lab == best).astype(np.uint8)
    cs, _ = cv2.findContours(comp, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    c = max(cs, key=cv2.contourArea)
    hull = cv2.convexHull(c)
    (ex, ey), (w, h), ang = cv2.fitEllipse(hull)
    th = np.linspace(0, 2 * math.pi, 48, endpoint=False)
    ca, sa = math.cos(math.radians(ang)), math.sin(math.radians(ang))
    poly = [(ex + w / 2 * math.cos(t) * ca - h / 2 * math.sin(t) * sa, ey + w / 2 * math.cos(t) * sa + h / 2 * math.sin(t) * ca)
            for t in th]
    out[k] = {'ellipse': [round(ex, 2), round(ey, 2), round(w, 2), round(h, 2), round(ang, 2)],
              'poly': [[round(p, 2) for p in q] for q in poly]}
    print(f'{name} {k}: centre ({ex:.1f}, {ey:.1f}) axes {w:.1f} x {h:.1f} angle {ang:.1f}')
    cv2.polylines(vis, [np.round(np.array(poly)).astype(np.int32)], True, (0, 255, 0), 1)
    cv2.drawContours(vis, [c], -1, (255, 0, 255), 1)
json.dump(db, open(lj, 'w'), indent=1)
ys, xs = np.nonzero(red)
Image.fromarray(vis).save(chk)
