"""backproj.py <fit.json> <state.json> <photo> <points.json> : ray-cast photo pixels onto the fitted body (final
coordinates), then map back through the build's deformation (lattices, then ends) to the undeformed design
coordinates the build code uses. points.json: {name: [[u, v], ...]}. Prints per name: final (x,y,z) and base (x,y,z)."""
import json, os, sys
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import fitlib as F
cfg = json.load(open(sys.argv[1])); st = json.load(open(sys.argv[2])); n = sys.argv[3]
pts = json.load(open(sys.argv[4]))
mesh = np.load(cfg['mesh'])
V = mesh['body_v'].copy(); T = mesh['body_t']
Ls = []
for L in cfg['lattices']:
    Lt = F.Lattice(L['lo'], L['hi'], L['seg']); Lt.D = np.array(L['D'] if 'D' in L else st['D'], float); Ls.append(Lt)
for Lt in Ls:
    V = Lt.apply(V)
FFD = json.load(open('/home/dev/Desktop/service/internal/webgame-by-claude/frontend/tools/blender/cars/fitdata/shiden/ffd.json'))
def ends(P):
    P = P.copy()
    for o in FFD.get('post', []):
        for z0, w, k in ((o['front'][0], o['front'][1], o['front'][2]), (-o['rear'][0], o['rear'][1], -o['rear'][2])):
            u = np.maximum((P[:, 2] - z0) * np.sign(z0), 0.0)
            P[:, 2] += k * np.where(u < w, u * u / (2 * w), u - w / 2)
    return P
def build_deform(P):
    for Lt in Ls:
        P = Lt.apply(P)
    return ends(P)
def to_base(P):
    B = P.copy()
    for _ in range(6):
        B = B - (build_deform(B) - P)
    return B
c = st['cams'][n]; W, H = c[7]
d, r, u = F.basis(*c[3:6]); f = c[6]; C = np.array(c[:3])
A, Bv, Cv = V[T[:, 0]], V[T[:, 1]], V[T[:, 2]]
E1, E2 = Bv - A, Cv - A
def cast(px):
    D = d * f + r * (px[0] - W / 2) - u * (px[1] - H / 2); D /= np.linalg.norm(D)
    P = np.cross(D, E2); det = (E1 * P).sum(1)
    ok = np.abs(det) > 1e-12
    inv = np.where(ok, 1.0 / np.where(ok, det, 1), 0)
    S = C - A; uu = (S * P).sum(1) * inv
    Q = np.cross(S, E1); vv = (Q @ D) * inv; t = (E2 * Q).sum(1) * inv
    hit = ok & (uu >= 0) & (vv >= 0) & (uu + vv <= 1) & (t > 0)
    if not hit.any():
        return None
    return C + D * t[hit].min()
ENV = sys.argv[5] if len(sys.argv) > 5 else None
if ENV:
    import cv2
    sg = 1 if ENV == 'front' else -1
    sel = V[:, 2] * sg > 0.8
    xs = np.round((V[sel, 0] + 1.0) / 0.01).astype(int); ys = np.round(V[sel, 1] / 0.01).astype(int)
    Z = np.full((140, 201), -9.0, np.float32)
    np.maximum.at(Z, (ys, xs), (V[sel, 2] * sg).astype(np.float32))
    k = np.ones((7, 7), np.uint8)
    Z = cv2.erode(cv2.dilate(Z, k), k)          # closing: fills openings and recesses
    def zf(x, y):
        i = np.clip(np.round(y / 0.01).astype(int), 0, 139); j = np.clip(np.round((x + 1.0) / 0.01).astype(int), 0, 200)
        return Z[i, j] * sg
    def cast(px):
        D = d * f + r * (px[0] - W / 2) - u * (px[1] - H / 2); D /= np.linalg.norm(D)
        t = np.arange(0.5, 25, 0.002)
        P = C[None] + t[:, None] * D[None]
        gap = (P[:, 2] - zf(P[:, 0], P[:, 1])) * sg
        k = np.nonzero(gap < 0)[0]
        return P[k[0]] if len(k) else None
out = {}
for name, lst in pts.items():
    fin = [cast(p) for p in lst]
    good = [p for p in fin if p is not None]
    base = to_base(np.array(good)) if good else np.zeros((0, 3))
    out[name] = {'final': np.round(np.array(good), 4).tolist(), 'base': np.round(base, 4).tolist(), 'miss': sum(p is None for p in fin)}
    print(name, 'miss', out[name]['miss'])
    for a, b in zip(good, base):
        print('   final', np.round(a, 3).tolist(), ' base', np.round(b, 3).tolist())
json.dump(out, open(sys.argv[4].replace('.json', '_3d.json'), 'w'))
