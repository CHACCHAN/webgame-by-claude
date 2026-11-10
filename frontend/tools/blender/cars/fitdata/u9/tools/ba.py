"""
ba.py <annot.json> <out.json> [--photos a,b] [--fix name,...] [--verbose]: bundle adjustment for the Yangwang U9: the
cameras of every photo and the 3D positions of the body's named vertices together, from points read off the photos.

Game frame: metres, x = the truck's left, y up (ground 0), z forward, origin midway between the axles. The car is
symmetric: a vertex <name> is solved once for the left side (x > 0); annotations <name>_l / <name>_r are its left and
mirrored right copies, <name>_c a centre-line point (x = 0). Scale and the frame come from the wheel hubs (centre caps,
z = +-WB/2, x = +-hub_x, y = hub_y - dy of the photo's body pose) and the licence plates (unused: the show cars' plates have no standard size).

annot.json: {"_points": {name: [x, y, z] initial guess, ...}, "_centre": {name: [y, z]},
             "<photo>": {"size": [W, H], "f": focal guess px, "pts": {"nose_l": [u, v], ...},
                         "plate": {"end": "f"|"r", "corners": {"tl": [u, v], "tr", "br", "bl"}}, "sigma": px, "ref": true,
                         (U9: "_hub_prior": {"xf"|"xr"|"y": [mean, sigma]} priors on the hub caps' x and the hubs' height)
                         "f_exif": px, "f_sig": 0.08}}  (f_exif: the focal length from the photo's EXIF, lens / sensor
                         width x pixels, for the crop as uploaded; a prior in log f)
Unknowns: per photo the camera (x, y, z, yaw, pitch, roll, log f) and the body's lift over the wheels (dy; 0 on the
reference photo), every vertex, hub_x front / rear, hub_y. Robust (Huber, 2.5 sigma) reprojection residuals, weak priors
(0.25 m) on the vertices' initial guesses. Writes {"cams": {photo: [x, y, z, yaw, pitch, roll, f, [W, H]]}, "pose":
{photo: {"dy", "pitch_deg"}}, "points": {name: [x, y, z]}, "hub": {...}, "rms": {photo: px}, "res": {photo: {pt: px}}}.
"""
import json, math, sys
import numpy as np
import cv2

WB = 2.900
PLATE = (0.44, 0.14)


def basis(yaw, pitch, roll):
    d = np.array([math.sin(yaw) * math.cos(pitch), math.sin(pitch), math.cos(yaw) * math.cos(pitch)])
    r = np.cross(d, [0, 1, 0]); r /= np.linalg.norm(r)
    u = np.cross(r, d)
    c, s = math.cos(roll), math.sin(roll)
    return d, c * r + s * u, -s * r + c * u


def project(cam, P, W, H):
    C = np.array(cam[:3]); d, r, u = basis(*cam[3:6]); f = cam[6]
    Q = P - C; z = Q @ d
    return np.stack([W / 2 + f * (Q @ r) / z, H / 2 - f * (Q @ u) / z], 1)


def cam_from_pnp(P3, P2, W, H, f):
    K = np.array([[f, 0, W / 2], [0, f, H / 2], [0, 0, 1]], float)
    ok, rv, tv = cv2.solvePnP(P3.astype(np.float64), P2.astype(np.float64), K, None, flags=cv2.SOLVEPNP_SQPNP)
    if not ok:
        return None, 1e9
    R, _ = cv2.Rodrigues(rv)
    C = (-R.T @ tv).ravel()
    d = R.T @ np.array([0, 0, 1.0]); right = R.T @ np.array([1.0, 0, 0]); up = -(R.T @ np.array([0, 1.0, 0]))
    yaw = math.atan2(d[0], d[2]); pitch = math.asin(max(-1, min(1, d[1])))
    d0, r0, u0 = basis(yaw, pitch, 0.0)
    roll = math.atan2(right @ u0, right @ r0)
    cam = [*C, yaw, pitch, roll, f]
    e = np.sqrt(((project(cam, P3, W, H) - P2) ** 2).sum(1)).mean()
    return cam, e


def main():
    a = sys.argv[1:]
    A = json.load(open(a[0])); out = a[1]
    only = a[a.index('--photos') + 1].split(',') if '--photos' in a else None
    fix = set(a[a.index('--fix') + 1].split(',')) if '--fix' in a else set()
    verbose = '--verbose' in a
    photos = [k for k in A if not k.startswith('_') and (only is None or k in only)]
    P0 = {k: np.array(v, float) for k, v in A['_points'].items()}
    C0 = {k: np.array(v, float) for k, v in A.get('_centre', {}).items()}
    hub0 = A.get('_hub', {'xf': 0.88, 'xr': 0.88, 'y': 0.42})
    names = sorted(P0); cnames = sorted(C0)
    # which vertices are seen at all
    seen = set()
    for p in photos:
        for k in A[p].get('pts', {}):
            seen.add(k[:-2])
        if 'plate' in A[p]:
            seen.add('plf' if A[p]['plate']['end'] == 'f' else 'plr')
    names = [n for n in names if n in seen]; cnames = [n for n in cnames if n in seen]
    ref = [p for p in photos if A[p].get('ref')] or photos[:1]

    def point3(name, X):
        """3D of an annotation key under parameter vector X (body frame)"""
        base, side = name[:-2], name[-1]
        if base.startswith('hub_'):
            return None
        if base in pidx:
            v = X[pidx[base]:pidx[base] + 3].copy()
        else:
            v = P0[base].copy()
        if side == 'r':
            v[0] = -v[0]
        elif side == 'c':
            v[0] = 0.0
        return v

    # parameter layout
    off = 0; camidx = {}; dyidx = {}
    for p in photos:
        camidx[p] = off; off += 7
        if p not in ref:
            dyidx[p] = off; off += 2      # body lift dy and pitch over the wheels
    pidx = {}
    for n in names:
        if n in fix:
            continue
        pidx[n] = off; off += 3
    cidx = {}
    for n in cnames:
        cidx[n] = off; off += 2
    hidx = off; off += 3
    X = np.zeros(off)
    for n, i in pidx.items():
        X[i:i + 3] = P0[n]
    for n, i in cidx.items():
        X[i:i + 2] = C0[n]
    X[hidx:hidx + 3] = [hub0['xf'], hub0['xr'], hub0['y']]

    def body_to_world(v, X, p):
        """body pose of photo p: rotate by pitch about the x axis through the origin, then lift dy"""
        if p not in dyidx:
            return v
        dy, th = X[dyidx[p]], X[dyidx[p] + 1]
        c, s = math.cos(th), math.sin(th)
        y, z = v[..., 1], v[..., 2]
        out = v.copy()
        out[..., 1] = c * y + s * z + dy
        out[..., 2] = -s * y + c * z
        return out

    def obs(p, X):
        """3D points (world) and their observed image points for photo p"""
        a = A[p]; P3, O, nm = [], [], []
        for k, uv in a.get('pts', {}).items():
            if k.startswith('hub_'):
                fr, side = k[4], k[-1]
                x = X[hidx] if fr == 'f' else X[hidx + 1]
                v = np.array([x if side == 'l' else -x, X[hidx + 2], WB / 2 if fr == 'f' else -WB / 2])
                P3.append(v)
            else:
                P3.append(body_to_world(point3(k, X), X, p))
            O.append(uv); nm.append(k)
        if 'plate' in a:
            pl = a['plate']; c = 'plf' if pl['end'] == 'f' else 'plr'
            yc, zc = X[cidx[c]], X[cidx[c] + 1]
            sx = -1 if pl['end'] == 'f' else 1
            pw, ph = PLATE
            for k, (cx, cy) in zip(('tl', 'tr', 'br', 'bl'), ((sx, 1), (-sx, 1), (-sx, -1), (sx, -1))):
                P3.append(body_to_world(np.array([cx * pw / 2, yc + cy * ph / 2, zc]), X, p))
                O.append(pl['corners'][k]); nm.append('plate_' + k)
        return np.array(P3, float), np.array(O, float), nm

    # initial cameras by PnP over a range of focal lengths
    for p in photos:
        W, H = A[p]['size']
        P3, O, _ = obs(p, X)
        best = (None, 1e9)
        fs = np.geomspace(0.5 * W, 8 * W, 40) if 'f_exif' not in A[p] else A[p]['f_exif'] * np.geomspace(0.8, 1.25, 9)
        for f in fs:
            cam, e = cam_from_pnp(P3, O, W, H, f)
            if cam is not None and e < best[1]:
                best = (cam, e)
        cam = best[0]
        X[camidx[p]:camidx[p] + 6] = cam[:6]; X[camidx[p] + 6] = math.log(cam[6])
        if verbose:
            print(f'init {p}: pnp mean err {best[1]:.1f} px f {cam[6]:.0f}')

    SIG_PRIOR = 0.25

    def residuals(X, detail=False):
        r = []; det = {}
        for p in photos:
            W, H = A[p]['size']
            sig = A[p].get('sigma', 2.0)
            cam = list(X[camidx[p]:camidx[p] + 6]) + [math.exp(X[camidx[p] + 6])]
            P3, O, nm = obs(p, X)
            uv = project(cam, P3, W, H)
            e = (uv - O) / sig
            n = np.hypot(e[:, 0], e[:, 1])
            k = 2.5
            w = np.where(n <= k, 1.0, np.sqrt(k * (2 * n - k)) / np.maximum(n, 1e-9))   # Huber as reweighting
            r.append((e * w[:, None]).ravel())
            if detail:
                det[p] = {m: round(float(np.hypot(*(uv[i] - O[i]))), 2) for i, m in enumerate(nm)}
            if p in dyidx:
                r.append(np.array([X[dyidx[p]] / 0.08, X[dyidx[p] + 1] / 0.02]))
            if 'f_exif' in A[p]:      # focal length from the photo's EXIF (lens, sensor, crop): a prior in log f
                r.append(np.array([(X[camidx[p] + 6] - math.log(A[p]['f_exif'])) / A[p].get('f_sig', 0.1)]))
        for n, i in pidx.items():
            r.append((X[i:i + 3] - P0[n]) / SIG_PRIOR)
        for n, i in cidx.items():
            r.append((X[i:i + 2] - C0[n]) / SIG_PRIOR)
        r.append(np.array([(X[hidx] - X[hidx + 1]) / 0.03]))     # front and rear hub faces about the same
        for k, i in (('xf', 0), ('xr', 1), ('y', 2)):                # priors on the hubs (track, loaded tyre radius)
            if k in A.get('_hub_prior', {}):
                m, sg = A['_hub_prior'][k]
                r.append(np.array([(X[hidx + i] - m) / sg]))
        for n, (xv, sg) in A.get('_xprior', {}).items():           # published width: the widest body lines
            if n in pidx:
                r.append(np.array([(X[pidx[n]] - xv) / sg]))
        rr = np.concatenate(r)
        return (rr, det) if detail else rr

    lam = 1e-2; r = residuals(X); cost = r @ r
    for it in range(60):
        J = np.zeros((len(r), len(X)))
        for j in range(len(X)):
            h = 1e-6 * max(1.0, abs(X[j])); xp = X.copy(); xp[j] += h; xm = X.copy(); xm[j] -= h
            J[:, j] = (residuals(xp) - residuals(xm)) / (2 * h)
        g = J.T @ r; Hm = J.T @ J
        ok = False
        for _ in range(12):
            dx = -np.linalg.solve(Hm + lam * np.diag(np.diag(Hm) + 1e-9), g)
            rn = residuals(X + dx); cn = rn @ rn
            if cn < cost:
                X, r, lam, ok = X + dx, rn, lam * 0.3, True
                dc = cost - cn; cost = cn
                break
            lam *= 10
        if not ok or dc < 1e-6 * cost:
            break
    rr, det = residuals(X, True)
    res = {'cams': {}, 'pose': {}, 'points': {}, 'centre': {}, 'rms': {}, 'res': det}
    for p in photos:
        W, H = A[p]['size']
        c = [float(v) for v in X[camidx[p]:camidx[p] + 6]] + [float(math.exp(X[camidx[p] + 6])), [W, H]]
        res['cams'][p] = c
        dy, th = (float(X[dyidx[p]]), float(X[dyidx[p] + 1])) if p in dyidx else (0.0, 0.0)
        res['pose'][p] = {'dy': round(dy, 4), 'pitch_deg': round(math.degrees(th), 3)}
        e = np.array(list(det[p].values()))
        res['rms'][p] = round(float(np.sqrt((e ** 2).mean())), 2)
    for n in names:
        v = X[pidx[n]:pidx[n] + 3] if n in pidx else P0[n]
        res['points'][n] = [round(float(t), 4) for t in v]
    for n, i in cidx.items():
        res['centre'][n] = [round(float(X[i]), 4), round(float(X[i + 1]), 4)]
    res['hub'] = {'xf': round(float(X[hidx]), 4), 'xr': round(float(X[hidx + 1]), 4), 'y': round(float(X[hidx + 2]), 4)}
    json.dump(res, open(out, 'w'), indent=1)
    for p in photos:
        c = res['cams'][p]
        worst = sorted(det[p].items(), key=lambda kv: -kv[1])[:4]
        print(f'{p:6s} rms {res["rms"][p]:5.2f}px  f {c[6]:6.0f}  cam ({c[0]:6.2f},{c[1]:5.2f},{c[2]:6.2f}) yaw {math.degrees(c[3]):6.1f} '
              f'pitch {math.degrees(c[4]):5.1f} roll {math.degrees(c[5]):5.2f}  pose {res["pose"][p]}  worst {worst}')
    print('hub', res['hub'])
    for n in names:
        v = res['points'][n]
        print(f'  {n:8s} {v[0]:7.3f} {v[1]:7.3f} {v[2]:7.3f}   (init {P0[n][0]:6.2f} {P0[n][1]:6.2f} {P0[n][2]:6.2f})')
    for n, v in res['centre'].items():
        print(f'  {n:8s}   y {v[0]:7.3f} z {v[1]:7.3f}')


if __name__ == '__main__':
    main()
