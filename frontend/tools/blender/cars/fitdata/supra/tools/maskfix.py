"""
maskfix.py <masks.json> <name> <cams.json> <base_mask.png> <photo> <out.png> [dbg.png]: hand fixes on a GrabCut photo mask (255 car, 0 not,
128 ignore). masks.json: {name: {"bottom": [[x,y],...] (cut below it in its x range),
"top": [...] (cut above), "cut": [poly...] (not car), "add": [poly...] (car), "ignore_polys": [poly...],
"ignore": [[x0,y0,x1,y1]...], "tyres": hull scale (1.06; 0 = off), "tyres_full": ids whose whole hull is ignored
(default: the near side), other tyres only below the bottom line}}. Order: base, cuts, cut, add, tyres + ignore.
"""
import json, math, sys
import numpy as np, cv2

cfg = json.load(open(sys.argv[1]))[sys.argv[2]]
cam = json.load(open(sys.argv[3]))['cams'][sys.argv[2]]
m = cv2.imread(sys.argv[4], cv2.IMREAD_GRAYSCALE)
h, w = m.shape
m = np.where(m > 127, 255, 0).astype(np.uint8)
X = np.arange(w)


def line_y(P):
    P = np.array(P, float)
    o = np.argsort(P[:, 0])
    P = P[o]
    x0, x1 = int(math.ceil(P[0, 0])), int(math.floor(P[-1, 0]))
    return x0, x1, np.interp(np.arange(x0, x1 + 1), P[:, 0], P[:, 1])


below = np.zeros((h, w), bool)
if cfg.get('bottom'):
    x0, x1, ys = line_y(cfg['bottom'])
    for i, x in enumerate(range(max(x0, 0), min(x1, w - 1) + 1)):
        below[int(math.ceil(ys[x - x0])):, x] = True
m[below] = 0
if cfg.get('top'):
    x0, x1, ys = line_y(cfg['top'])
    for x in range(max(x0, 0), min(x1, w - 1) + 1):
        m[:int(ys[x - x0]), x] = 0
poly = lambda P: [np.round(np.array(P, float)).astype(np.int32)]
for P in cfg.get('cut', []):
    cv2.fillPoly(m, poly(P), 0)
for P in cfg.get('add', []):
    cv2.fillPoly(m, poly(P), 255)

# projected tyre hulls
x, y, z, yaw, pitch, roll, f = cam[:7]
d = np.array([math.sin(yaw) * math.cos(pitch), math.sin(pitch), math.cos(yaw) * math.cos(pitch)])
r = np.cross(d, [0, 1, 0]); r /= np.linalg.norm(r)
u = np.cross(r, d)
r, u = r * math.cos(roll) + u * math.sin(roll), u * math.cos(roll) - r * math.sin(roll)
C = np.array([x, y, z])


def proj(Q):
    q = np.asarray(Q, float) - C
    zz = q @ d
    return np.stack([w / 2 + f * (q @ r) / zz, h / 2 - f * (q @ u) / zz], -1)


ign = np.zeros((h, w), np.uint8)
sc = cfg.get('tyres', 1.06)
if sc:
    full = cfg.get('tyres_full') or (['fr', 'rr'] if x < 0 else ['fl', 'rl'])
    for tid in ('fl', 'fr', 'rl', 'rr'):
        front = tid[0] == 'f'
        side = 1 if tid[1] == 'l' else -1
        T, R, W = (1.52, 0.3216, 0.235) if front else (1.525, 0.318, 0.255)
        cx, cz = side * T / 2, 1.275 if front else -1.275
        a = np.linspace(0, 2 * math.pi, 48, endpoint=False)
        pts = [(cx + s * W / 2 * sc, 0.318 + R * sc * math.sin(t), cz + R * sc * math.cos(t)) for s in (-1, 1) for t in a]
        hull = cv2.convexHull(proj(pts).astype(np.float32)).astype(np.int32)
        t = np.zeros((h, w), np.uint8)
        cv2.fillPoly(t, [hull], 1)
        if tid not in full:
            t[~below] = 0
        ign |= t
for P in cfg.get('ignore_polys', []):
    cv2.fillPoly(ign, poly(P), 1)
for b in cfg.get('ignore', []):
    ign[int(b[1]):int(b[3]), int(b[0]):int(b[2])] = 1
m[ign.astype(bool)] = 128
cv2.imwrite(sys.argv[6], m)
if len(sys.argv) > 7:
    ph = cv2.imread(sys.argv[5])
    o = ph.copy()
    o[m == 255] = (0.5 * o[m == 255] + (0, 127, 0)).astype(np.uint8)
    o[m == 128] = (0.5 * o[m == 128] + (127, 0, 0)).astype(np.uint8)
    cv2.imwrite(sys.argv[7], o)
print(sys.argv[2], 'car', int((m == 255).sum()), 'ignore', int((m == 128).sum()))
