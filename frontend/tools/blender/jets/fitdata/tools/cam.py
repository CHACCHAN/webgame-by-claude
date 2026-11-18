"""
cam.py: a camera per photo from points whose place on the aircraft is known (the wheels: wheelbase, track, tyre radii,
plus any feature listed in known.json), then rays through other annotated points cut with a plane.

  py.sh cam.py <annot.json> <known.json> <out cams.json> photo[,photo...]

known.json: {"wheel": {"wb", "track", "rn", "rm"}, "pts": {"name[_l|_r]": [x, y, z]}, "init": {photo: {"eye", "target", "f"}},
             "planes": {"name": ["x"|"y"|"z", value]}}   (a point named in planes is reported as ray x plane)
"""
import json
import math
import sys

import numpy as np


def rodrigues(w):
    th = float(np.linalg.norm(w))
    if th < 1e-12:
        return np.eye(3)
    k = w / th
    K = np.array([[0, -k[2], k[1]], [k[2], 0, -k[0]], [-k[1], k[0], 0]])
    return np.eye(3) + math.sin(th) * K + (1 - math.cos(th)) * K @ K


def look(eye, target):
    d = np.array(target, float) - eye
    d /= np.linalg.norm(d)
    r = np.cross(d, [0, 1, 0])
    r /= np.linalg.norm(r)
    u = np.cross(r, d)
    return np.array([r, -u, d])


def project(C, M, f, P, W, H):
    Q = (P - C) @ M.T
    return np.stack([W / 2 + f * Q[:, 0] / Q[:, 2], H / 2 + f * Q[:, 1] / Q[:, 2]], 1)


def known_points(K):
    wh = K['wheel']
    WB, TR = wh['wb'], wh['track']
    P = {'na': [0, wh['rn'], WB / 2], 'nc': [0, 0, WB / 2]}
    for s, sg in (('l', 1), ('r', -1)):
        P['ma_' + s] = [sg * TR / 2, wh['rm'], -WB / 2]
        P['mc_' + s] = [sg * TR / 2, 0, -WB / 2]
    for n, p in K.get('pts', {}).items():
        P[n] = p
    return P


def solve(photo, A, K, verbose=True):
    W, H = A[photo]['size']
    P = known_points(K)
    names = [n for n in A[photo]['pts'] if n in P]
    X = np.array([P[n] for n in names], float)
    ob = np.array([A[photo]['pts'][n] for n in names], float)
    ini = K['init'][photo]
    best = None
    for f0 in (ini['f'] * 0.5, ini['f'], ini['f'] * 2):
        eye = np.array(ini['target'], float) + (np.array(ini['eye'], float) - ini['target']) * (f0 / ini['f'])
        M0 = look(eye, ini['target'])
        x = np.concatenate([eye, np.zeros(3), [math.log(f0)]])

        def res(x):
            M = M0 @ rodrigues(x[3:6]).T
            uv = project(x[:3], M, math.exp(x[6]), X, W, H)
            # (a weak pull on the focal length: the wheels alone leave distance / focal nearly free for a long lens)
            r = [(uv - ob).ravel(), [(x[6] - math.log(ini['f'])) * K.get('fprior', 2.0)]]
            # half-known points: on the plane x = c their ray must pass at the height y (the published height)
            for n, hk in K.get('semi', {}).get(photo, {}).items():
                u_, v_ = A[photo]['pts'][n]
                fl = math.exp(x[6])
                d = M.T @ np.array([(u_ - W / 2) / fl, (v_ - H / 2) / fl, 1.0])
                ax = 'xyz'.index(hk.get('on', 'x'))
                t = (hk['at'] - x[ax]) / d[ax]
                r.append([(x[1] + d[1] * t - hk['y']) * fl / abs(t) * hk.get('w', 1.0)])
            return np.concatenate(r)

        lam = 1e-3
        r = res(x)
        cost = r @ r
        for it in range(300):
            J = np.zeros((len(r), 7))
            for j in range(7):
                h = 1e-5 * max(1.0, abs(x[j]))
                xp = x.copy(); xp[j] += h
                xm = x.copy(); xm[j] -= h
                J[:, j] = (res(xp) - res(xm)) / (2 * h)
            g, Hm = J.T @ r, J.T @ J
            ok = False
            for _ in range(20):
                dx = -np.linalg.solve(Hm + lam * np.diag(np.diag(Hm) + 1e-9), g)
                rn = res(x + dx)
                if rn @ rn < cost:
                    x, r, cost, lam, ok = x + dx, rn, rn @ rn, lam * 0.3, True
                    break
                lam *= 10
            if not ok or np.abs(dx).max() < 1e-10:
                break
        if best is None or cost < best[0]:
            best = (cost, x.copy(), M0 @ rodrigues(x[3:6]).T)
    cost, x, M = best
    f = math.exp(x[6])
    uv = project(x[:3], M, f, X, W, H)
    err = np.linalg.norm(uv - ob, axis=1)
    if verbose:
        print(f'{photo}: C {np.round(x[:3], 2)} f {f:.0f} dist {np.linalg.norm(x[:3]):.1f} rms {math.sqrt((err ** 2).mean()):.2f} px  '
              + ' '.join(f'{n}:{e:.1f}' for n, e in zip(names, err)))
    cam = {'C': x[:3].tolist(), 'R': M.tolist(), 'f': f, 'size': [W, H]}
    # rays of the other points cut with their planes
    out = {}
    for n, (u, v) in A[photo]['pts'].items():
        base = n[:-2] if n[-2:] in ('_l', '_r') else n
        pl = K.get('planes', {}).get(n) or K.get('planes', {}).get(base)
        if not pl:
            continue
        d = M.T @ np.array([(u - W / 2) / f, (v - H / 2) / f, 1.0])
        ax = 'xyz'.index(pl[0])
        val = pl[1] * (-1 if (pl[0] == 'x' and n.endswith('_r')) else 1)
        t = (val - x[ax]) / d[ax]
        p = x[:3] + d * t
        out[n] = p.tolist()
        if verbose:
            print(f'    {n:8s} on {pl[0]}={val:+.3f}: ({p[0]:+.3f}, {p[1]:.3f}, {p[2]:+.3f})')
    for n, p in K.get('check', {}).get(photo, {}).items():
        q = project(x[:3], M, f, np.array([p], float), W, H)[0]
        print(f'    check {n}: {p} -> ({q[0]:.1f}, {q[1]:.1f})')
    return cam, out


if __name__ == '__main__':
    A = json.load(open(sys.argv[1]))
    K = json.load(open(sys.argv[2]))
    res = {'cams': {}, 'pts': {}}
    for p in sys.argv[4].split(','):
        res['cams'][p], res['pts'][p] = solve(p, A, K)
    json.dump(res, open(sys.argv[3], 'w'), indent=1)
