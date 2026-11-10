"""
wheelign.py <cams.json> <fit.json> <out_fit.json>: the tyres are rigid and anchored by the hub points, so where the
photo's outline runs round a tyre it says nothing about the body (and the traced polygons are least sure there, in the
shadows): each photo's mask gets the tyres' projection (both faces' hull, from the solved camera) added as car (255,
not ignore: grey inside the car would make outline pixels of its own) -> <mask>_w.png, and a fit.json pointing at them.
"""
import json, math, sys
import numpy as np, cv2
sys.path.insert(0, __file__.rsplit('/', 3)[0] + '/../..')

cams = json.load(open(sys.argv[1]))
fit = json.load(open(sys.argv[2]))
TRACK = {'f': 1.73, 'r': 1.70}
TW = {'f': 0.275, 'r': 0.325}
R, YC, AX = 0.366, 0.358, 1.45


def basis(yaw, pitch, roll):
    d = np.array([math.sin(yaw) * math.cos(pitch), math.sin(pitch), math.cos(yaw) * math.cos(pitch)])
    r = np.cross(d, [0, 1, 0]); r /= np.linalg.norm(r); u = np.cross(r, d)
    c, s = math.cos(roll), math.sin(roll)
    return d, c * r + s * u, -s * r + c * u


def proj(c, P):
    d, r, u = basis(*c[3:6]); W, H = c[7]; f = c[6]
    Q = np.asarray(P) - np.asarray(c[:3]); z = Q @ d
    return np.stack([W / 2 + f * (Q @ r) / z, H / 2 - f * (Q @ u) / z], 1)


for n, ph in fit['photos'].items():
    c = cams['cams'].get(n)
    if c is None:
        continue
    m = cv2.imread(ph['mask'], cv2.IMREAD_GRAYSCALE)
    ign = np.zeros_like(m)
    for ax in ('f', 'r'):
        for s in (1, -1):
            xc = s * TRACK[ax] / 2
            z = AX if ax == 'f' else -AX
            pts = []
            for x in (xc - TW[ax] / 2, xc + TW[ax] / 2):
                for a in np.linspace(0, 2 * math.pi, 73):
                    pts.append((x, YC + R * math.sin(a), z + R * math.cos(a)))
            P = proj(c, np.array(pts))
            hull = cv2.convexHull(np.round(P).astype(np.int32))
            cv2.fillConvexPoly(ign, hull, 1)
    m[ign.astype(bool)] = 255
    out = ph['mask'].replace('.png', '_w.png')
    cv2.imwrite(out, m)
    ph['mask'] = out
json.dump(fit, open(sys.argv[3], 'w'), indent=1)
