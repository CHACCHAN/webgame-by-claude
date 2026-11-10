"""
ba.py <annot.json> <out.json> [--photos a,b] [--fix name,...] [--verbose]: bundle adjustment for a tank: the cameras of
every photo, the turret's traverse and the gun's elevation in each photo, and the 3D positions of named features, from
points read off the photos (after cars/fitdata/cybertruck/tools/ba.py, with the turret and gun as moving frames).

Game frame: metres, x = the vehicle's left, y up (ground 0), z forward, origin on the ground at the middle of the track
contact length. A feature <name> is solved once for the left side (x > 0); annotations <name>_l / <name>_r are its
left and mirrored right copies, <name>_c a centre-line point (x = 0), <name>_a an asymmetric point (solved with its own
x). Each feature belongs to a frame (annot "_frames": {name: "hull"|"turret"|"gun"}, default hull):
  turret: rotates by the photo's traverse psi about the vertical axis x = 0, z = tz (left positive: +psi turns the gun
          towards +x);
  gun:    rotates by the photo's elevation theta (muzzle up positive) about the trunnion axis (y = gy, z = gz, at
          psi = 0), then with the turret.
annot.json:
  "_points": {name: [x, y, z]} initial guesses (at psi = theta = 0), "_frames": {...},
  "_prior": {"<name>.<x|y|z>": [value, sigma]} (published sizes: the widest point, ground contacts ...),
  "_axis": {"tz": [v, sig], "gy": [v, sig], "gz": [v, sig]},
  "<photo>": {"size": [W, H], "pts": {"<name>_l": [u, v], ...}, "sigma": px, "psi": [deg, sig], "theta": [deg, sig],
              "f_exif": px, "f_sig": 0.08}
Unknowns: per photo the camera (x, y, z, yaw, pitch, roll, log f), psi, theta; every free feature; tz, gy, gz. Robust
(Huber 2.5 sigma) reprojection residuals, weak priors (0.3 m) on the guesses. Writes {"cams": {photo: [x, y, z, yaw,
pitch, roll, f, [W, H]]}, "pose": {photo: {"psi_deg", "theta_deg"}}, "points": {name: [x, y, z]}, "axis": {...},
"rms": {photo: px}, "res": {photo: {pt: px}}}.
"""
import json, math, sys
import numpy as np
import cv2


def basis(yaw, pitch, roll):
    d = np.array([math.sin(yaw) * math.cos(pitch), math.sin(pitch), math.cos(yaw) * math.cos(pitch)])
    r = np.cross(d, [0, 1, 0]); r /= np.linalg.norm(r)
    u = np.cross(r, d)
    c, s = math.cos(roll), math.sin(roll)
    return d, c * r + s * u, -s * r + c * u


def project(cam, P, W, H):
    C = np.array(cam[:3]); d, r, u = basis(*cam[3:6]); f = cam[6]
    Q = P - C; z = Q @ d
    z = np.where(z < 0.05, 0.05, z)
    return np.stack([W / 2 + f * (Q @ r) / z, H / 2 - f * (Q @ u) / z], 1)


def cam_from_pnp(P3, P2, W, H, f):
    K = np.array([[f, 0, W / 2], [0, f, H / 2], [0, 0, 1]], float)
    try:
        ok, rv, tv = cv2.solvePnP(P3.astype(np.float64), P2.astype(np.float64), K, None, flags=cv2.SOLVEPNP_SQPNP)
    except cv2.error:
        return None, 1e9
    if not ok:
        return None, 1e9
    R, _ = cv2.Rodrigues(rv)
    C = (-R.T @ tv).ravel()
    d = R.T @ np.array([0, 0, 1.0]); right = R.T @ np.array([1.0, 0, 0])
    yaw = math.atan2(d[0], d[2]); pitch = math.asin(max(-1, min(1, d[1])))
    d0, r0, u0 = basis(yaw, pitch, 0.0)
    roll = math.atan2(right @ u0, right @ r0)
    cam = [*C, yaw, pitch, roll, f]
    e = np.sqrt(((project(cam, P3, W, H) - P2) ** 2).sum(1)).mean()
    return cam, e


def turret_pose(v, psi, tz):
    """rotate hull-frame points v (N, 3) of the turret by psi about the axis x = 0, z = tz"""
    c, s = math.cos(psi), math.sin(psi)
    x, y, z = v[:, 0], v[:, 1], v[:, 2] - tz
    return np.stack([c * x + s * z, y, -s * x + c * z + tz], 1)


def gun_pose(v, theta, gy, gz):
    """elevate gun points by theta (muzzle up) about the trunnion (y = gy, z = gz)"""
    c, s = math.cos(theta), math.sin(theta)
    y, z = v[:, 1] - gy, v[:, 2] - gz
    return np.stack([v[:, 0], c * y + s * z + gy, -s * y + c * z + gz], 1)


def main():
    a = sys.argv[1:]
    A = json.load(open(a[0])); out = a[1]
    only = a[a.index('--photos') + 1].split(',') if '--photos' in a else None
    fix = set(a[a.index('--fix') + 1].split(',')) if '--fix' in a else set()
    verbose = '--verbose' in a
    photos = [k for k in A if not k.startswith('_') and (only is None or k in only)]
    P0 = {k: np.array(v, float) for k, v in A['_points'].items()}
    frames = A.get('_frames', {})
    seen = set()
    for p in photos:
        for k in A[p].get('pts', {}):
            seen.add(k[:-2])
    missing = sorted(s for s in seen if s not in P0)
    if missing:
        sys.exit(f'no initial guess for {missing}')
    names = sorted(n for n in P0 if n in seen)
    ax0 = A.get('_axis', {})
    axv = [ax0.get(k, [d, 1.0])[0] for k, d in (('tz', 0.3), ('gy', 1.95), ('gz', 1.4))]

    off = 0; camidx = {}; pidx = {}
    for p in photos:
        camidx[p] = off; off += 9          # camera 7, psi, theta
    for n in names:
        if n in fix:
            continue
        pidx[n] = off; off += 3
    axidx = off; off += 3
    X = np.zeros(off)
    for n, i in pidx.items():
        X[i:i + 3] = P0[n]
    X[axidx:axidx + 3] = axv

    def base3(name, X):
        base, side = name[:-2], name[-1]
        v = (X[pidx[base]:pidx[base] + 3] if base in pidx else P0[base]).copy()
        if side == 'r':
            v[0] = -v[0]
        elif side == 'c':
            v[0] = 0.0
        return v

    def obs(p, X):
        a_ = A[p]; ks = list(a_.get('pts', {}))
        P3 = np.array([base3(k, X) for k in ks], float).reshape(-1, 3)
        O = np.array([a_['pts'][k] for k in ks], float).reshape(-1, 2)
        fr = np.array([frames.get(k[:-2], 'hull') for k in ks])
        psi, th = X[camidx[p] + 7], X[camidx[p] + 8]
        tz, gy, gz = X[axidx:axidx + 3]
        g = fr == 'gun'
        if g.any():
            P3[g] = gun_pose(P3[g], th, gy, gz)
        t = (fr == 'turret') | g
        if t.any():
            P3[t] = turret_pose(P3[t], psi, tz)
        return P3, O, ks, fr

    for p in photos:
        W, H = A[p]['size']
        if 'psi' in A[p]:
            X[camidx[p] + 7] = math.radians(A[p]['psi'][0])
        if 'theta' in A[p]:
            X[camidx[p] + 8] = math.radians(A[p]['theta'][0])
        P3, O, _, fr = obs(p, X)
        hull = fr == 'hull'
        use = hull if hull.sum() >= 6 else np.ones(len(fr), bool)
        best = (None, 1e9)
        fs = np.geomspace(0.5 * W, 8 * W, 50) if 'f_exif' not in A[p] else A[p]['f_exif'] * np.geomspace(0.8, 1.25, 9)
        for f in fs:
            cam, e = cam_from_pnp(P3[use], O[use], W, H, f)
            if cam is not None and e < best[1]:
                best = (cam, e)
        cam = best[0]
        X[camidx[p]:camidx[p] + 6] = cam[:6]; X[camidx[p] + 6] = math.log(cam[6])
        print(f'init {p}: pnp mean err {best[1]:.1f} px f {cam[6]:.0f} ({use.sum()} pts)')

    SIG = A.get('_sig_prior', 0.3)
    priors = A.get('_prior', {})

    def residuals(X, detail=False):
        r = []; det = {}
        for p in photos:
            W, H = A[p]['size']
            sig = A[p].get('sigma', 2.0)
            cam = list(X[camidx[p]:camidx[p] + 6]) + [math.exp(X[camidx[p] + 6])]
            P3, O, nm, _ = obs(p, X)
            uv = project(cam, P3, W, H)
            e = (uv - O) / sig
            n = np.hypot(e[:, 0], e[:, 1])
            k = 2.5
            w = np.where(n <= k, 1.0, np.sqrt(k * (2 * n - k)) / np.maximum(n, 1e-9))
            r.append((e * w[:, None]).ravel())
            if detail:
                det[p] = {m: round(float(np.hypot(*(uv[i] - O[i]))), 2) for i, m in enumerate(nm)}
            ps = A[p].get('psi', [0, 180]); th = A[p].get('theta', [0, 20])
            r.append(np.array([(X[camidx[p] + 7] - math.radians(ps[0])) / math.radians(ps[1]),
                               (X[camidx[p] + 8] - math.radians(th[0])) / math.radians(th[1])]))
            if 'f_exif' in A[p]:
                r.append(np.array([(X[camidx[p] + 6] - math.log(A[p]['f_exif'])) / A[p].get('f_sig', 0.1)]))
        for n, i in pidx.items():
            r.append((X[i:i + 3] - P0[n]) / SIG)
        for key, (val, sg) in priors.items():
            n, c = key.split('.')
            if n in pidx:
                r.append(np.array([(X[pidx[n] + 'xyz'.index(c)] - val) / sg]))
        for j, k in enumerate(('tz', 'gy', 'gz')):
            if k in ax0:
                r.append(np.array([(X[axidx + j] - ax0[k][0]) / ax0[k][1]]))
        rr = np.concatenate(r)
        return (rr, det) if detail else rr

    lam = 1e-2; r = residuals(X); cost = r @ r
    for it in range(80):
        J = np.zeros((len(r), len(X)))
        for j in range(len(X)):
            h = 1e-6 * max(1.0, abs(X[j])); xp = X.copy(); xp[j] += h; xm = X.copy(); xm[j] -= h
            J[:, j] = (residuals(xp) - residuals(xm)) / (2 * h)
        g = J.T @ r; Hm = J.T @ J
        ok = False; dc = 0
        for _ in range(12):
            dx = -np.linalg.solve(Hm + lam * np.diag(np.diag(Hm) + 1e-9), g)
            rn = residuals(X + dx); cn = rn @ rn
            if cn < cost:
                X, r, lam, ok = X + dx, rn, lam * 0.3, True
                dc = cost - cn; cost = cn
                break
            lam *= 10
        if not ok or dc < 1e-7 * cost:
            break
    rr, det = residuals(X, True)
    res = {'cams': {}, 'pose': {}, 'points': {}, 'rms': {}, 'res': det,
           'axis': {k: round(float(X[axidx + j]), 4) for j, k in enumerate(('tz', 'gy', 'gz'))}}
    for p in photos:
        W, H = A[p]['size']
        res['cams'][p] = [float(v) for v in X[camidx[p]:camidx[p] + 6]] + [float(math.exp(X[camidx[p] + 6])), [W, H]]
        res['pose'][p] = {'psi_deg': round(math.degrees(X[camidx[p] + 7]), 3), 'theta_deg': round(math.degrees(X[camidx[p] + 8]), 3)}
        e = np.array(list(det[p].values()))
        res['rms'][p] = round(float(np.sqrt((e ** 2).mean())), 2)
    for n in names:
        v = X[pidx[n]:pidx[n] + 3] if n in pidx else P0[n]
        res['points'][n] = [round(float(t), 4) for t in v]
    json.dump(res, open(out, 'w'), indent=1)
    for p in photos:
        c = res['cams'][p]
        worst = sorted(det[p].items(), key=lambda kv: -kv[1])[:4]
        print(f'{p:6s} rms {res["rms"][p]:5.2f}px  f {c[6]:6.0f}  cam ({c[0]:6.2f},{c[1]:5.2f},{c[2]:6.2f}) yaw {math.degrees(c[3]):6.1f} '
              f'pitch {math.degrees(c[4]):5.1f} roll {math.degrees(c[5]):5.2f}  {res["pose"][p]}  worst {worst}')
    print('axis', res['axis'])
    for n in names:
        v = res['points'][n]
        print(f'  {n:8s} {frames.get(n, "hull"):6s} {v[0]:7.3f} {v[1]:7.3f} {v[2]:7.3f}   (init {P0[n][0]:6.2f} {P0[n][1]:6.2f} {P0[n][2]:6.2f})')


if __name__ == '__main__':
    main()
