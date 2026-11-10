"""
ba.py: bundle adjustment of the aircraft's feature points and the photo cameras (numpy only).

  $PY ba.py <annot.json> <feats.json> <out_cams.json> [--photos a,b] [--fix name,...] [--verbose]

annot.json: {photo: {"size": [W, H], "pts": {"<feature>[_l|_r]": [u, v]}}}   (u right, v down, pixels)
feats.json: {"wheel": {"wb": 5.42, "track": 2.75, "rn": [0.26, 0.03], "rm": [0.40, 0.03]},
             "feats": {"<name>": {"sym": true|false, "init": [x, y, z], "prior": {"x"|"y"|"z": [mean, sigma]}}}}
  Wheels (fixed frame): na = nose axle (0, rn, wb/2), nc = its contact point (0, 0, wb/2); ma_l/_r = main axles
  (+-track/2, rm, -wb/2), mc_l/_r = their contact points. Symmetric features share (|x|, y, z); _l has x > 0.
Unknowns: per camera C (3), rotation vector (3), log focal (1), principal point fixed at the image centre;
the free features; rn, rm.
Writes cams.json: {"cams": {photo: {"C": [...], "R": [[r], [u], [d]], "f": f, "size": [W, H]}}, "feats": {name: [x, y, z]},
"rms": {photo: px}} (r right, u up, d forward, game frame).
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


def inv_rodrigues(R):
    c = max(-1.0, min(1.0, (np.trace(R) - 1) / 2))
    th = math.acos(c)
    if th < 1e-9:
        return np.zeros(3)
    w = np.array([R[2, 1] - R[1, 2], R[0, 2] - R[2, 0], R[1, 0] - R[0, 1]]) / (2 * math.sin(th))
    return w * th


def project(cam, P, W, H):
    """cam: (C, M, f) with M rows (right, down, forward); P (N, 3) → (N, 2) pixels"""
    C, M, f = cam
    Q = (P - C) @ M.T
    return np.stack([W / 2 + f * Q[:, 0] / Q[:, 2], H / 2 + f * Q[:, 1] / Q[:, 2]], 1)


def dlt(X, uv, W, H):
    """camera from >= 6 correspondences: centre, rows (right, down, forward), focal (principal point ~ centre)"""
    T = np.array([[1, 0, -W / 2], [0, 1, -H / 2], [0, 0, 1.0]])
    A = []
    for (x, y, z), (u, v) in zip(X, uv):
        u, v = u - W / 2, v - H / 2
        A.append([x, y, z, 1, 0, 0, 0, 0, -u * x, -u * y, -u * z, -u])
        A.append([0, 0, 0, 0, x, y, z, 1, -v * x, -v * y, -v * z, -v])
    _, _, Vt = np.linalg.svd(np.array(A))
    P = Vt[-1].reshape(3, 4)
    Xh = np.hstack([X, np.ones((len(X), 1))])
    if np.mean(Xh @ P[2]) < 0:
        P = -P
    M3 = P[:, :3]
    C = -np.linalg.solve(M3, P[:, 3])
    Rf = np.flipud(np.eye(3))
    Q_, R_ = np.linalg.qr((Rf @ M3).T)
    K = Rf @ R_.T @ Rf
    R = Rf @ Q_.T
    D = np.diag(np.sign(np.diag(K)))
    K, R = K @ D, D @ R
    if np.linalg.det(R) < 0:
        R = -R
    K = K / K[2, 2]
    f = (abs(K[0, 0]) + abs(K[1, 1])) / 2
    return C, R, f


def main():
    a = sys.argv[1:]
    A = json.load(open(a[0]))
    F = json.load(open(a[1]))
    out = a[2]
    only = a[a.index('--photos') + 1].split(',') if '--photos' in a else None
    verbose = '--verbose' in a
    photos = [k for k in A if not k.startswith('_') and (only is None or k in only)]
    wh = F['wheel']
    WB, TR = wh['wb'], wh['track']
    feats = F['feats']
    fnames = sorted(feats)
    # parameter layout
    idx = {}
    x0 = []
    for n in fnames:
        s = feats[n]
        i = feats[n]['init']
        if s.get('sym'):
            idx[n] = (len(x0), 3)
            x0 += [abs(i[0]), i[1], i[2]]
        else:
            idx[n] = (len(x0), 2)
            x0 += [i[1], i[2]]
    i_rn = len(x0)
    x0 += [wh['rn'][0], wh['rm'][0]]

    def point(n, x):
        """3D of an observation name"""
        base, side = (n[:-2], n[-1]) if n[-2:] in ('_l', '_r') else (n, None)
        if base == 'na':
            return np.array([0, x[i_rn], WB / 2])
        if base == 'nc':
            return np.array([0, 0, WB / 2])
        if base in ('ma', 'mc'):
            return np.array([(1 if side == 'l' else -1) * TR / 2, x[i_rn + 1] if base == 'ma' else 0.0, -WB / 2])
        k, m = idx[base]
        if m == 3:
            return np.array([(1 if side == 'l' else -1) * x[k], x[k + 1], x[k + 2]])
        return np.array([0, x[k], x[k + 1]])

    # camera inits by DLT
    cams0 = {}
    for p in photos:
        W, H = A[p]['size']
        names = list(A[p]['pts'])
        X = np.array([point(n, np.array(x0)) for n in names])
        uv = np.array([A[p]['pts'][n] for n in names], float)
        if 'init' in A[p]:
            e, t, f = A[p]['init']['eye'], A[p]['init']['target'], A[p]['init']['f']
            d = np.array(t, float) - e
            d /= np.linalg.norm(d)
            r = np.cross(d, [0, 1, 0])
            r /= np.linalg.norm(r)
            u = np.cross(r, d)
            C, R = np.array(e, float), np.array([r, -u, d])
        else:
            C, R, f = dlt(X, uv, W, H)
        cams0[p] = (C, R, f)
        if verbose:
            print(p, 'init C', np.round(C, 2), 'f', round(f), 'd', np.round(R[2], 3))
    xc = []
    cidx = {}
    for p in photos:
        C, R, f = cams0[p]
        cidx[p] = len(x0) + len(xc)
        xc += list(C) + list(inv_rodrigues(R)) + [math.log(f)]
    x = np.array(x0 + xc, float)

    def cam_of(p, x):
        k = cidx[p]
        return x[k:k + 3], rodrigues(x[k + 3:k + 6]), math.exp(min(12.0, x[k + 6]))

    sig_px = 2.0

    def res(x, detail=False):
        r = []
        per = {}
        for p in photos:
            W, H = A[p]['size']
            names = list(A[p]['pts'])
            P = np.array([point(n, x) for n in names])
            uv = project(cam_of(p, x), P, W, H)
            ob = np.array([A[p]['pts'][n] for n in names], float)
            e = (uv - ob)
            r.append(e.ravel() / sig_px)
            per[p] = (names, uv, ob)
        for n in fnames:
            for key, (mu, sg) in feats[n].get('prior', {}).items():
                k, m = idx[n]
                j = {'x': 0, 'y': 1, 'z': 2}[key] if m == 3 else {'y': 0, 'z': 1}[key]
                r.append(np.array([(x[k + j] - mu) / sg]))
        r.append(np.array([(x[i_rn] - wh['rn'][0]) / wh['rn'][1], (x[i_rn + 1] - wh['rm'][0]) / wh['rm'][1]]))
        rr = np.concatenate(r)
        return (rr, per) if detail else rr

    lam = 1e-3
    r = res(x)
    cost = r @ r
    for it in range(400):
        J = np.zeros((len(r), len(x)))
        for j in range(len(x)):
            h = 1e-6 * max(1.0, abs(x[j]))
            xp = x.copy()
            xp[j] += h
            xm = x.copy()
            xm[j] -= h
            J[:, j] = (res(xp) - res(xm)) / (2 * h)
        g = J.T @ r
        Hm = J.T @ J
        ok = False
        for _ in range(25):
            dx = -np.linalg.solve(Hm + lam * np.diag(np.diag(Hm) + 1e-9), g)
            rn = res(x + dx)
            cn = rn @ rn
            if cn < cost:
                x, r, cost, lam, ok = x + dx, rn, cn, lam * 0.3, True
                break
            lam *= 10
        if not ok or np.abs(dx).max() < 1e-9:
            break
    rr, per = res(x, True)
    outc = {'cams': {}, 'feats': {}, 'rms': {}, 'wheel': {'rn': round(float(x[i_rn]), 4), 'rm': round(float(x[i_rn + 1]), 4)}}
    for p in photos:
        names, uv, ob = per[p]
        e = np.hypot(*(uv - ob).T)
        C, M, f = cam_of(p, x)
        R = np.array([M[0], -M[1], M[2]])
        W, H = A[p]['size']
        outc['cams'][p] = {'C': [round(float(v), 4) for v in C], 'R': np.round(R, 6).tolist(), 'f': round(f, 2), 'size': [W, H]}
        outc['rms'][p] = round(float(np.sqrt((e ** 2).mean())), 2)
        d = R[2]
        print(f'{p:5s} rms {outc["rms"][p]:5.2f} px  C ({C[0]:7.2f},{C[1]:6.2f},{C[2]:7.2f})  f {f:7.0f}  dir ({d[0]:+.2f},{d[1]:+.2f},{d[2]:+.2f})  dist {np.linalg.norm(C):.1f}')
        if verbose:
            for n, ee, u_, o_ in zip(names, e, uv, ob):
                print(f'     {n:8s} err {ee:5.1f}  model ({u_[0]:7.1f},{u_[1]:7.1f}) photo ({o_[0]:7.1f},{o_[1]:7.1f})')
    for n in fnames:
        P = point(n + ('_l' if feats[n].get('sym') else ''), x)
        outc['feats'][n] = [round(float(v), 4) for v in P]
        print(f'  {n:6s} ({P[0]:+7.3f}, {P[1]:6.3f}, {P[2]:+7.3f})')
    print('  wheels: rn', outc['wheel']['rn'], 'rm', outc['wheel']['rm'])
    json.dump(outc, open(out, 'w'), indent=1)


if __name__ == '__main__':
    main()
