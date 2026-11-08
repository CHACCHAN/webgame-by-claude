"""partfit.py <fit.json> <state.json> <part> [photos] : move / scale one rigid part of the (deformed) body to the photo
masks by coordinate descent on the summed XOR area (valid pixels, per photo normalised by the car's area).
part: mirror | wing. Shifts are in game coordinates, mirrored in x (dx > 0 = outwards)."""
import json, os, sys
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cv2, numpy as np
import fitlib as F
cfg = json.load(open(sys.argv[1])); st = json.load(open(sys.argv[2])); part = sys.argv[3]
names = sys.argv[4].split(',') if len(sys.argv) > 4 else list(cfg['photos'])
mesh = np.load(cfg['mesh'])
V0 = mesh['body_v']; T = mesh['body_t']
V = V0.copy()
for i, L in enumerate(cfg['lattices']):
    Lt = F.Lattice(L['lo'], L['hi'], L['seg'])
    Lt.D = np.array(L['D'] if 'D' in L else st['D'], float)
    V = Lt.apply(V)
ax = np.abs(V0[:, 0])
REG = {'mirror': (ax > 0.765) & (V0[:, 1] > 0.83) & (V0[:, 1] < 1.0) & (V0[:, 2] > 0.18) & (V0[:, 2] < 0.45),
       'wing': (V0[:, 1] > 0.86) & (V0[:, 2] < -1.55) & (V0[:, 2] > -2.3)}[part]
inpart = REG[T].all(1)
print(part, 'verts', int(REG.sum()), 'tris', int(inpart.sum()))
Ts, Tp = T[~inpart], T[inpart]
pv = np.nonzero(REG)[0]
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


def moved(p):
    dx, dy, dz, sx, sy, sz = p
    Q = V[pv].copy()
    side = np.sign(Q[:, 0])
    cen = np.array([0.0, Q[:, 1].mean(), Q[:, 2].mean()])
    cx = np.abs(Q[:, 0]).mean()
    Q[:, 0] = side * (cx + (np.abs(Q[:, 0]) - cx) * sx + dx)
    Q[:, 1] = cen[1] + (Q[:, 1] - cen[1]) * sy + dy
    Q[:, 2] = cen[2] + (Q[:, 2] - cen[2]) * sz + dz
    out = V.copy(); out[pv] = Q
    return out


def score(p, per=False):
    Vm = moved(p); tot = 0.0; res = {}
    for n, (c, W, H, Ms, P, valid, A) in data.items():
        M = np.zeros((H, W), np.uint8)
        uv, _ = F.project(c[:7], Vm, W, H); F.raster(uv, Tp, W, H, M)
        R = Ms | (M > 0)
        x = float(((R ^ P) & valid).sum()) / A * 100
        res[n] = round(x, 3); tot += x
    return (tot, res) if per else tot


p = np.array([0.0, 0.0, 0.0, 1.0, 1.0, 1.0])
print('centre', np.abs(V[pv, 0]).mean(), V[pv, 1].mean(), V[pv, 2].mean(), 'bbox', V[pv].min(0), V[pv].max(0))
best = score(p); print('start', round(best, 3), score(p, True)[1], flush=True)
for step, ss in ((0.02, 0.15), (0.01, 0.08), (0.005, 0.04), (0.0025, 0.02)):
    improved = True
    while improved:
        improved = False
        for k, h in ((0, step), (1, step), (2, step), (3, ss), (4, ss), (5, ss)):
            for sgn in (1, -1):
                q = p.copy(); q[k] += sgn * h
                sc = score(q)
                if sc < best - 1e-4:
                    best, p, improved = sc, q, True
                    break
    print('step', step, 'p', np.round(p, 4).tolist(), 'score', round(best, 3), flush=True)
print('final', np.round(p, 4).tolist(), score(p, True)[1])
