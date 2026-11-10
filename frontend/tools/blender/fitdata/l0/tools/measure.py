"""
measure.py: where pixels of a photo land on the fitted shell (ray from the solved camera to the first hit), to
read the livery off the photos in the train frame.

  py measure.py <cams.json> <photo> <shape.json> u,v [u,v ...] [--plane x=1.45]
      -> per pixel: x y z (train frame) and d (distance from car0's nose tip); with --plane, the hit on that
         plane instead (e.g. the flat body side)
"""
import json, os, sys

import numpy as np

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, '..', '..', '..', 'parts'))
import cam as C
import l0_shape as S


def ray(cam, W, H, u, v):
    eye = np.array(cam[:3], float)
    d, r, up = C.basis(*cam[3:6])
    f = cam[6]
    w = d * f + r * (u - W / 2) - up * (v - H / 2)
    return eye, w / np.linalg.norm(w)


def hit_mesh(o, w, V, F):
    """first hit of the ray o + t w on the triangles (Möller–Trumbore, all at once)"""
    A, B, Cc = V[F[:, 0]], V[F[:, 1]], V[F[:, 2]]
    e1, e2 = B - A, Cc - A
    p = np.cross(w, e2)
    det = (e1 * p).sum(1)
    ok = np.abs(det) > 1e-12
    inv = np.where(ok, 1 / np.where(ok, det, 1), 0)
    s = o - A
    uu = (s * p).sum(1) * inv
    q = np.cross(s, e1)
    vv = (q @ w) * inv
    t = (e2 * q).sum(1) * inv
    good = ok & (uu >= 0) & (vv >= 0) & (uu + vv <= 1) & (t > 0.1)
    if not good.any():
        return None
    t = np.where(good, t, np.inf)
    return o + w * t.min()


def main():
    a = sys.argv[1:]
    cams = json.load(open(a[0]))['cams']
    photo = a[1]
    sh = json.load(open(a[2]))
    S.load_shape(sh)
    plane = None
    if '--plane' in a:
        k, val = a[a.index('--plane') + 1].split('=')
        plane = ('xyz'.index(k), float(val))
    pts = [tuple(map(float, t.split(','))) for t in a[3:] if ',' in t and not t.startswith('x=')]
    c = cams[photo]
    W, H = c[7]
    V, F = S.train_mesh()
    for u, v in pts:
        o, w = ray(c[:7], W, H, u, v)
        if plane:
            i, val = plane
            t = (val - o[i]) / w[i] if abs(w[i]) > 1e-9 else -1
            h = o + w * t if t > 0 else None
        else:
            h = hit_mesh(o, w, V, F)
        if h is None:
            print(f'{u:.1f},{v:.1f}: miss')
        else:
            print(f'{u:.1f},{v:.1f}: x {h[0]:+.3f} y {h[1]:.3f} z {h[2]:+.3f}  d {S.NOSE_TIP - h[2]:.3f}')


if __name__ == '__main__':
    main()
