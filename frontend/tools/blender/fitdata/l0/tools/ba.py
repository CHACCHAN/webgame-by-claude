"""
ba.py <annot.json> <out.json> [--photos a,b] [--verbose]: bundle adjustment for the L0: the camera of every photo and
the 3D positions of the named livery / fitting points together, from points read off the photos (annot.json).

Frame: the train frame of cam.py (car0's: x = left, y up, z forward, nose tip at z = +20.75). Every photo is solved
against the nearest end car (both end cars are the same; the far end's photos see "car0" from its own end). The
train is symmetric: a point <name> is solved once for the left side (x > 0); annotations <name>_l / <name>_r are its
left and mirrored right copies, <name>_c lies on the centre line (x = 0).

annot.json: {"_points": {name: [x, y, z] initial guess}, "_fixed": {name: {"x"|"y"|"z": value}},
             "_prior": {name: [sx, sy, sz] prior sigma (m), default 0.6 each},
             "<photo>": {"size": [W, H], "f": focal guess px, "pts": {"lw_ot_l": [u, v], ...}, "sigma": px,
                         "weights": {pt: w}, "f_exif": px, "f_sig": 0.05}}  (f_exif: the focal length from the
                         photo's EXIF for the working copy's width, a prior in log f)
Writes {"cams": {photo: [x, y, z, yaw, pitch, roll, f, [W, H]]}, "points": {name: [x, y, z]},
        "rms": {photo: px}, "res": {photo: {pt: px}}}.
"""
import json, math, sys

import numpy as np

sys.dont_write_bytecode = True
sys.path.insert(0, __import__('os').path.dirname(__file__))
import cam as C


def obs_point(name):
    base, side = name.rsplit('_', 1)
    return base, side


def main():
    a = sys.argv[1:]
    A = json.load(open(a[0]))
    A.setdefault('_lines', {})
    out = a[1]
    only = a[a.index('--photos') + 1].split(',') if '--photos' in a else None
    verbose = '--verbose' in a
    P0 = {k: np.array(v, float) for k, v in A['_points'].items()}
    fixed = A.get('_fixed', {})
    prior = A.get('_prior', {})
    photos = [k for k in A if not k.startswith('_') and (not only or k in only)]
    names = sorted(P0)
    # unknowns per point: the free coordinates
    free = {n: [i for i, c in enumerate('xyz') if c not in fixed.get(n, {})] for n in names}
    seen = {n: [obs_point(o)[1] for p in photos for o in list(A[p]['pts']) + list(A[p].get('lines', {})) if obs_point(o)[0] == n]
            for n in names}
    centre_only = {n for n in names if seen[n] and all(s == 'c' for s in seen[n])}
    for n in centre_only:
        free[n] = [i for i in free[n] if i != 0]
    # cameras: initial from PnP at the guessed focal length (searching f if not given)
    cams = {}
    for p in photos:
        W, H = A[p]['size']
        obs = A[p]['pts']
        P3, P2 = [], []
        for o, uv in obs.items():
            b, s = obs_point(o)
            if b not in P0:
                continue
            q = P0[b].copy()
            if s == 'r':
                q[0] = -q[0]
            elif s == 'c':
                q[0] = 0.0
            P3.append(q)
            P2.append(uv)
        P3, P2 = np.array(P3), np.array(P2, float)
        if 'cam0' in A[p]:
            cams[p] = A[p]['cam0']
            print(f'init {p}: given', flush=True)
            continue
        best = None
        fs = [A[p].get('f', A[p].get('f_exif'))] if ('f' in A[p] or 'f_exif' in A[p]) else list(np.geomspace(0.6 * W, 8 * W, 40))
        for f in fs:
            cam, e = C.from_pnp(P3, P2, W, H, f)
            if cam is not None and cam[2] > -200 and (best is None or e < best[1]):
                best = (cam, e)
        cams[p] = best[0]
        print(f'init {p}: f {best[0][6]:.0f} err {best[1]:.1f} px ({len(P2)} pts)', flush=True)

    # parameter vector: cameras (7 each, log f), then the free point coordinates
    def pack(cams, P):
        v = []
        for p in photos:
            c = cams[p]
            v += [c[0], c[1], c[2], c[3], c[4], c[5], math.log(c[6])]
        for n in names:
            v += [P[n][i] for i in free[n]]
        return np.array(v, float)

    def unpack(v):
        cs, P = {}, {}
        k = 0
        for p in photos:
            cs[p] = list(v[k:k + 6]) + [math.exp(v[k + 6])]
            k += 7
        for n in names:
            q = P0[n].copy()
            for c, val in fixed.get(n, {}).items():
                q['xyz'.index(c)] = val
            if n in centre_only:
                q[0] = 0.0
            for i in free[n]:
                q[i] = v[k]
                k += 1
            P[n] = q
        return cs, P

    def residuals(v, robust=True):
        cs, P = unpack(v)
        r = []
        for p in photos:
            W, H = A[p]['size']
            sig = A[p].get('sigma', 1.5)
            wts = A[p].get('weights', {})
            for o, uv in A[p]['pts'].items():
                b, s = obs_point(o)
                if b not in P:
                    continue
                q = P[b].copy()
                if s == 'r':
                    q[0] = -q[0]
                elif s == 'c':
                    q[0] = 0.0
                pr = C.project(cs[p], q[None], W, H)[0, :2]
                e = (pr - np.array(uv)) / sig * wts.get(o, 1.0)
                if robust:
                    n = np.hypot(*e)
                    if n > 2.5:
                        e = e * math.sqrt(2 * 2.5 * n - 2.5 * 2.5) / n
                r += list(e)
            for o, uvs in A[p].get('lines', {}).items():
                b, s = obs_point(o)
                if b not in P:
                    continue
                q = P[b].copy()
                if s == 'r':
                    q[0] = -q[0]
                elif s == 'c':
                    q[0] = 0.0
                ax = np.zeros(3)
                ax['xyz'.index(A['_lines'][b])] = 1.0
                pr = C.project(cs[p], np.array([q - 3 * ax, q + 3 * ax]), W, H)[:, :2]
                t = pr[1] - pr[0]
                t /= np.linalg.norm(t)
                nrm = np.array([-t[1], t[0]])
                for uv in uvs:
                    e = float((np.array(uv) - pr[0]) @ nrm) / sig
                    if robust and abs(e) > 2.5:
                        e = math.copysign(math.sqrt(2 * 2.5 * abs(e) - 2.5 * 2.5), e)
                    r.append(e)
        for n in names:
            sg = prior.get(n, [0.6, 0.6, 0.6])
            for i in free[n]:
                r.append((P[n][i] - P0[n][i]) / sg[i])
        # a camera's roll is small (the photos are levelled): a weak prior; the focal length from the EXIF
        for p in photos:
            r.append(cs[p][5] / 0.15)
            if 'f_exif' in A[p]:
                r.append(math.log(cs[p][6] / A[p]['f_exif']) / A[p].get('f_sig', 0.05))
        return np.array(r)

    v0 = pack(cams, P0)
    v, cost = C.lm(residuals, v0, steps=200, verbose=verbose)
    cs, P = unpack(v)
    res = {}
    rms = {}
    for p in photos:
        W, H = A[p]['size']
        res[p] = {}
        e2 = []
        for o, uv in A[p]['pts'].items():
            b, s = obs_point(o)
            if b not in P:
                continue
            q = P[b].copy()
            if s == 'r':
                q[0] = -q[0]
            elif s == 'c':
                q[0] = 0.0
            pr = C.project(cs[p], q[None], W, H)[0, :2]
            e = float(np.hypot(*(pr - np.array(uv))))
            res[p][o] = round(e, 2)
            e2.append(e * e)
        rms[p] = round(math.sqrt(sum(e2) / len(e2)), 2)
    outd = {'cams': {p: [round(float(x), 5) for x in cs[p]] + [A[p]['size']] for p in photos},
            'points': {n: [round(float(x), 4) for x in P[n]] for n in names}, 'rms': rms, 'res': res}
    json.dump(outd, open(out, 'w'), indent=1)
    for p in photos:
        c = cs[p]
        print(f'{p}: rms {rms[p]:.2f} px  eye ({c[0]:.2f}, {c[1]:.2f}, {c[2]:.2f}) f {c[6]:.0f}  worst ' +
              ', '.join(f'{k} {e:.1f}' for k, e in sorted(res[p].items(), key=lambda t: -t[1])[:4]))
    for n in names:
        print(f'  {n:10s} ' + ' '.join(f'{x:7.3f}' for x in P[n]) + '   (guess ' + ' '.join(f'{x:7.3f}' for x in P0[n]) + ')')


if __name__ == '__main__':
    main()
