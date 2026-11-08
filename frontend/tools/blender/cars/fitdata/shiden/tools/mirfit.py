"""mirfit.py <fit.json> <state.json> [photos] : replace the model's door mirrors by a parametric head (ellipsoid with a
long rounded nose and a short back at the glass) + neck, fit X, Y, Z, rx, ry, rz (+ neck drop) to the photo masks by
coordinate descent on the XOR area (final, deformed coordinates). Prints the parameters."""
import json, math, os, sys
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cv2, numpy as np
import fitlib as F
cfg = json.load(open(sys.argv[1])); st = json.load(open(sys.argv[2]))
names = sys.argv[3].split(',') if len(sys.argv) > 3 else list(cfg['photos'])
mesh = np.load(cfg['mesh'])
V0 = mesh['body_v']; T = mesh['body_t']
V = V0.copy()
for L in cfg['lattices']:
    Lt = F.Lattice(L['lo'], L['hi'], L['seg']); Lt.D = np.array(L['D'] if 'D' in L else st['D'], float); V = Lt.apply(V)
ax = np.abs(V0[:, 0])
REG = (ax > 0.765) & (V0[:, 1] > 0.83) & (V0[:, 1] < 1.0) & (V0[:, 2] > 0.18) & (V0[:, 2] < 0.45)
Ts = T[~REG[T].all(1)]
NU, NV = 16, 9


def head(p, s):
    X, Y, Z, rx, ry, rz, drop = p
    hc = np.array([s * X, Y, Z])
    pts = [hc + (0, 0, rz * 1.25)]
    for j in range(1, NV):
        phi = math.pi * j / NV
        for i in range(NU):
            th = 2 * math.pi * i / NU
            x = rx * math.sin(phi) * math.cos(th)
            y = ry * math.sin(phi) * math.sin(th) * (0.85 if math.sin(th) > 0 else 1.0)
            z = rz * math.cos(phi) * (1.25 if phi < math.pi / 2 else 0.35)
            pts.append(hc + (s * x, y, z))
    pts.append(hc + (0, 0, -rz * 0.35))
    P = np.array(pts)
    tris = []
    for i in range(NU):
        tris.append((0, 1 + i, 1 + (i + 1) % NU))
    for j in range(NV - 2):
        for i in range(NU):
            a, b = 1 + j * NU + i, 1 + j * NU + (i + 1) % NU
            tris += [(a, b, b + NU), (a, b + NU, a + NU)]
    last = len(P) - 1
    for i in range(NU):
        tris.append((last, 1 + (NV - 2) * NU + (i + 1) % NU, 1 + (NV - 2) * NU + i))
    # neck: a slab from the head's inner underside down and in to the door
    top = hc + (-s * rx * 0.45, -ry * 0.6, 0.0)
    bot = np.array([s * (X - rx * 0.55 - 0.03), Y - ry - drop, Z + 0.01])
    w, d = 0.022, 0.03
    nk = [top + (s * w, 0, -d), top + (s * w, 0, d), top + (-s * w, 0, d), top + (-s * w, 0, -d),
          bot + (s * w, 0, -d), bot + (s * w, 0, d), bot + (-s * w, 0, d), bot + (-s * w, 0, -d)]
    o = len(P)
    P = np.vstack([P, nk])
    for k in range(4):
        k2 = (k + 1) % 4
        tris += [(o + k, o + k2, o + 4 + k2), (o + k, o + 4 + k2, o + 4 + k)]
    return P, np.array(tris)


data = {}
for n in names:
    c = st['cams'][n]; W, H = c[7]
    m = cv2.imread(cfg['photos'][n]['mask'], cv2.IMREAD_GRAYSCALE)
    M = np.zeros((H, W), np.uint8)
    uv, _ = F.project(c[:7], V, W, H); F.raster(uv, Ts, W, H, M)
    for w in F.WHEELS:
        uv, _ = F.project(c[:7], mesh[f'{w}_v'], W, H); F.raster(uv, mesh[f'{w}_t'], W, H, M)
    P = m > 192; valid = (m <= 64) | (m > 192)
    data[n] = (c, W, H, M > 0, P, valid, float(P.sum()))


def score(p, per=False):
    tot = 0.0; res = {}
    geo = [head(p, s) for s in (1, -1)]
    for n, (c, W, H, Ms, P, valid, A) in data.items():
        M = np.zeros((H, W), np.uint8)
        for Pg, Tg in geo:
            uv, z = F.project(c[:7], Pg, W, H); F.raster(uv, Tg, W, H, M)
        R = Ms | (M > 0)
        x = float(((R ^ P) & valid).sum()) / A * 100
        res[n] = round(x, 3); tot += x
    return (tot, res) if per else tot


p = np.array([float(v) for v in os.environ.get('P0', '0.838,0.912,0.30,0.086,0.052,0.056,0.05').split(',')])
best = score(p); print('start', np.round(p, 4).tolist(), round(best, 3), score(p, True)[1], flush=True)
for step in (0.02, 0.01, 0.005, 0.0025):
    improved = True
    while improved:
        improved = False
        for k in [k for k in range(7) if str(k) not in os.environ.get('FIX', '').split(',')]:
            h = step if k < 3 else step * 0.5
            for sgn in (1, -1):
                q = p.copy(); q[k] += sgn * h
                if q[3] < 0.03 or q[4] < 0.025 or q[5] < 0.025 or q[6] < 0.0:
                    continue
                sc = score(q)
                if sc < best - 1e-4:
                    best, p, improved = sc, q, True
                    break
    print('step', step, 'p', np.round(p, 4).tolist(), 'score', round(best, 3), flush=True)
print('final', np.round(p, 4).tolist(), score(p, True)[1])
