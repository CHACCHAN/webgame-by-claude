"""
solve.py <annot.json> <out_cams.json> [--only a,b] : bundle adjustment of photo cameras on an AE86 (game frame: x left,
y up, z forward; ground y = 0; origin midway between the axles).
Known: wheel rims (circles at the real wheelbase / track), plates (rectangles of known or unknown size, facing +-z).
Unknown: per photo camera (pos, yaw, pitch, roll, focal), body pose relative to the wheels (dy, pitch; 0 on the
reference photo), plate positions; shared body feature points (symmetric pairs foo_l / foo_r, centre points c_*).
"""
import json, math, sys
import numpy as np
import cv2

WB = 2.400
TF, TR = 1.355, 1.345
RW = 0.285                      # loaded wheel centre height (185/60R14)
LIP = 0.06                      # rim lip / hub cap plane outboard of the wheel centre plane

# rough body feature positions (x >= 0 half; game frame) for the initial guess only
GUESS = {
    'lid_ri': (0.40, 0.79, 1.66), 'lid_ro': (0.74, 0.76, 1.64), 'lid_fi': (0.42, 0.74, 1.96), 'lid_fo': (0.72, 0.72, 1.94),
    'hood_ro': (0.70, 0.91, 0.72), 'ws_top': (0.58, 1.24, 0.12), 'ws_bot': (0.68, 0.93, 0.68),
    'handle': (0.80, 0.86, -0.38), 'blamp_ot': (0.72, 0.55, 1.98), 'blamp_it': (0.45, 0.55, 2.04),
    'hg_b': (0.58, 1.00, -1.97), 'hg_t': (0.54, 1.27, -0.85), 'qw_tip': (0.68, 1.00, -1.70),
    'mirror': (0.93, 0.99, 0.52), 'tl_ot': (0.80, 0.77, -2.05), 'tl_ob': (0.80, 0.52, -2.08), 'tl_it': (0.30, 0.77, -2.09),
    'tl_ib': (0.30, 0.55, -2.10), 'dw_rt': (0.62, 1.27, -0.50), 'dw_ft': (0.66, 1.22, 0.05),
    'c_emb_hatch': (0, 0.92, -2.03), 'c_toyota_r': (0, 0.74, -2.10), 'c_emb_f': (0, 0.62, 2.05),
    'fuel_s': (-0.79, 0.82, -1.55), 'hood_fc': (0.70, 0.74, 1.97), 'c_roof': (0, 1.33, -0.3),
    'arch_rf': (0.80, 0.55, 0.85), 'arch_rr': (0.80, 0.55, -1.55), 'dw_rb': (0.76, 0.97, -0.55),

}


# features on the body side: their lateral position is known within a few cm (catalogue width 1,625 mm)
PRIOR_SIGMA = {'handle': (0.02, 0.5, 0.5), 'fuel_s': (0.02, 0.5, 0.5), 'mirror': (0.05, 0.5, 0.5)}


def basis(yaw, pitch, roll):
    d = np.array([math.sin(yaw) * math.cos(pitch), math.sin(pitch), math.cos(yaw) * math.cos(pitch)])
    r = np.cross(d, [0, 1, 0]); r /= np.linalg.norm(r)
    u = np.cross(r, d)
    c, s = math.cos(roll), math.sin(roll)
    return d, c * r + s * u, -s * r + c * u


def project(cam, P, W, H):
    C = cam[:3]; d, r, u = basis(*cam[3:6]); f = math.exp(cam[6])
    Q = P - C
    z = Q @ d
    return np.stack([W / 2 + f * (Q @ r) / z, H / 2 - f * (Q @ u) / z], 1)


def body_to_ground(P, dy, th):
    c, s = math.cos(th), math.sin(th)
    y = P[:, 1] * c + P[:, 2] * s + dy
    z = P[:, 2] * c - P[:, 1] * s
    return np.stack([P[:, 0], y, z], 1)


def feat_base(name):
    if name.startswith('c_') or name.endswith('_s'):
        return name, 0
    if name.endswith('_l'):
        return name[:-2], 1
    if name.endswith('_r'):
        return name[:-2], -1
    raise ValueError(name)


def wheel_circle(name, rr, n=180, lip=LIP, steer=0.0):
    front = name[1] == 'f'
    side = 1 if name.endswith('_l') else -1
    xc = side * (TF if front else TR) / 2
    z = WB / 2 if front else -WB / 2
    a = np.linspace(0, 2 * math.pi, n, endpoint=False)
    # circle in the wheel's local frame (axle along x), offset outboard by lip, steered about the vertical axis
    loc = np.stack([np.full(n, side * lip), rr * np.cos(a), rr * np.sin(a)], 1)
    if front and steer:
        c, s = math.cos(steer), math.sin(steer)
        loc = np.stack([loc[:, 0] * c + loc[:, 2] * s, loc[:, 1], -loc[:, 0] * s + loc[:, 2] * c], 1)
    return loc + np.array([xc, RW, z])


def ellipse_pts(e, n=16):
    (cx, cy), (a, b), ang = e['centre'], e['axes'], math.radians(e['angle'])
    t = np.linspace(0, 2 * math.pi, n, endpoint=False)
    x, y = a * np.cos(t), b * np.sin(t)
    return np.stack([cx + x * math.cos(ang) - y * math.sin(ang), cy + x * math.sin(ang) + y * math.cos(ang)], 1)


class Problem:
    def __init__(self, A, names):
        self.A = A
        self.names = names
        feats = []
        for n in names:
            for k in A[n].get('pts', {}):
                b, _ = feat_base(k)
                if b not in feats:
                    feats.append(b)
        self.feats = feats
        # parameter layout
        self.idx = {}
        k = 0
        for n in names:
            self.idx[(n, 'cam')] = slice(k, k + 7); k += 7
            self.idx[(n, 'pose')] = slice(k, k + 2); k += 2
            self.idx[(n, 'rim')] = slice(k, k + 3); k += 3          # rim lip radius, lip offset, front steer
            for p, pd in A[n].get('plates', {}).items():
                m = 3 if pd.get('size') else 5
                self.idx[(n, p)] = slice(k, k + m); k += m
        for f in feats:
            m = 2 if f.startswith('c_') else 3
            self.idx[('feat', f)] = slice(k, k + m); k += m
        self.N = k

    def feat3(self, x, f):
        v = x[self.idx[('feat', f)]]
        return np.array([0.0, v[0], v[1]]) if f.startswith('c_') else v

    def residuals(self, x, detail=False):
        res, info = [], []
        for n in self.names:
            a = self.A[n]
            W, H = a['size']
            cam = x[self.idx[(n, 'cam')]]
            dy, th = x[self.idx[(n, 'pose')]]
            if a.get('ref'):
                dy, th = 0.0, 0.0
            rr, lip, steer = x[self.idx[(n, 'rim')]]
            # manual points
            pts = a.get('pts', {})
            if pts:
                P = []
                for k in pts:
                    b, s = feat_base(k)
                    p = self.feat3(x, b).copy()
                    if s:
                        p[0] = s * abs(p[0])
                    P.append(p)
                uv = project(cam, body_to_ground(np.array(P), dy, th), W, H)
                obs = np.array(list(pts.values()), float)
                e = (uv - obs) / a.get('sigma', 3.0)
                res.append(e.ravel())
                info += [(n, k, float(np.hypot(*(uv[i] - obs[i])))) for i, k in enumerate(pts)]
            # rims: the detected lip ellipse's centre (= the wheel centre) and its top / bottom points
            for w, e in a.get('rims', {}).items():
                front = w[1] == 'f'
                side = 1 if w.endswith('_l') else -1
                xc = side * ((TF if front else TR) / 2 + lip)
                zc = WB / 2 if front else -WB / 2
                P3 = np.array([[xc, RW, zc], [xc, RW + rr, zc], [xc, RW - rr, zc]])
                uv = project(cam, P3, W, H)
                ep = ellipse_pts(e, 360)
                obs = np.array([e['centre'], ep[ep[:, 1].argmin()], ep[ep[:, 1].argmax()]])
                d = uv - obs
                res.append((d / np.array([[2.0], [3.0], [3.0]])).ravel())
                info.append((n, w, float(np.sqrt((d ** 2).sum(1).mean()))))
            for p, pd in a.get('plates', {}).items():
                v = x[self.idx[(n, p)]]
                c = v[:3]
                w, h = pd['size'] if pd.get('size') else (v[3], v[4])
                fz = 1 if p.endswith('_f') else -1
                # corners TL TR BR BL as seen in the image from outside the plate; viewer right = +x (front) / -x (rear)
                sx = 1 if fz > 0 else -1
                cor = np.array([[c[0] - sx * w / 2, c[1] + h / 2, c[2]], [c[0] + sx * w / 2, c[1] + h / 2, c[2]],
                                [c[0] + sx * w / 2, c[1] - h / 2, c[2]], [c[0] - sx * w / 2, c[1] - h / 2, c[2]]])
                uv = project(cam, body_to_ground(cor, dy, th), W, H)
                obs = np.array(pd['corners'], float)
                res.append(((uv - obs) / 1.5).ravel())
                info += [(n, f'{p}{i}', float(np.hypot(*(uv[i] - obs[i])))) for i in range(4)]
            # priors
            res.append(np.array([dy / 0.08, th / 0.03, (rr - 0.19) / 0.02, (lip - LIP) / 0.02, steer / 0.15]))
        for f in self.feats:
            g = np.array(GUESS.get(f, (0.5, 0.8, 0.0)), float)
            v = self.feat3(x, f)
            sg = np.array(PRIOR_SIGMA.get(f, (0.5, 0.5, 0.5)))
            res.append((np.abs(v) - np.abs(g)) / sg if not f.startswith('c_') else (v - g) / sg)
        r = np.concatenate(res)
        return (r, info) if detail else r


def lm(prob, x, iters=60):
    r = prob.residuals(x)
    cost = r @ r
    lam = 1e-3
    for it in range(iters):
        J = np.zeros((len(r), prob.N))
        for j in range(prob.N):
            h = 1e-5 * max(1.0, abs(x[j]))
            xp = x.copy(); xp[j] += h
            xm = x.copy(); xm[j] -= h
            J[:, j] = (prob.residuals(xp) - prob.residuals(xm)) / (2 * h)
        g = J.T @ r
        A = J.T @ J
        improved = False
        for _ in range(12):
            dx = -np.linalg.solve(A + lam * np.diag(np.diag(A) + 1e-9), g)
            xn = x + dx
            rn = prob.residuals(xn)
            cn = rn @ rn
            if cn < cost:
                x, r, cost = xn, rn, cn
                lam = max(lam / 3, 1e-9)
                improved = True
                break
            lam *= 4
        if not improved or np.abs(dx).max() < 1e-7:
            break
    return x, cost


def init_camera(a, feats_guess):
    """solvePnP over a focal sweep from the rough 3D guess"""
    W, H = a['size']
    obj, img = [], []
    for k, uv in a.get('pts', {}).items():
        b, s = feat_base(k)
        g = np.array(GUESS[b], float)
        if s:
            g[0] = s * abs(g[0])
        obj.append(g); img.append(uv)
    for w, e in a.get('rims', {}).items():
        circ = wheel_circle(w, 0.0, 1)[0]
        obj.append(circ); img.append(e['centre'])
    for p, pd in a.get('plates', {}).items():
        fz = 1 if p.endswith('_f') else -1
        c = np.array([pd.get('guess_x', 0.0), 0.45 if fz > 0 else 0.62, 2.07 * fz])
        obj.append(c); img.append(np.mean(pd['corners'], 0))
    obj = np.array(obj, np.float64); img = np.array(img, np.float64)
    best = None
    for f in np.geomspace(W * 0.5, W * 8, 60):
        K = np.array([[f, 0, W / 2], [0, f, H / 2], [0, 0, 1]])
        # game frame -> opencv camera: image y down; use a flipped object frame so the solver sees a right-handed set
        ok, rv, tv = cv2.solvePnP(obj, img, K, None, flags=cv2.SOLVEPNP_SQPNP)
        if not ok:
            continue
        proj, _ = cv2.projectPoints(obj, rv, tv, K, None)
        err = np.sqrt(((proj.reshape(-1, 2) - img) ** 2).sum(1).mean())
        if best is None or err < best[0]:
            best = (err, f, rv, tv)
    err, f, rv, tv = best
    R, _ = cv2.Rodrigues(rv)
    C = -R.T @ tv.ravel()
    d = R.T @ np.array([0, 0, 1.0])
    rr = R.T @ np.array([1.0, 0, 0])
    yaw = math.atan2(d[0], d[2]); pitch = math.asin(max(-1, min(1, d[1])))
    _, r0, u0 = basis(yaw, pitch, 0.0)
    roll = math.atan2(rr @ u0, rr @ r0)
    return np.array([*C, yaw, pitch, roll, math.log(f)]), err


def main():
    A = json.load(open(sys.argv[1]))
    names = [n for n in A if not n.startswith('_')]
    if '--only' in sys.argv:
        names = sys.argv[sys.argv.index('--only') + 1].split(',')
    prob = Problem(A, names)
    x = np.zeros(prob.N)
    for n in names:
        cam, err = init_camera(A[n], GUESS)
        print(f'init {n}: pnp rms {err:.1f}px f {math.exp(cam[6]):.0f} C {np.round(cam[:3], 2)}')
        x[prob.idx[(n, 'cam')]] = cam
        x[prob.idx[(n, 'rim')]] = [0.19, LIP, 0.0]
        for p, pd in A[n].get('plates', {}).items():
            fz = 1 if p.endswith('_f') else -1
            v = [pd.get('guess_x', 0.0), 0.45 if fz > 0 else 0.62, 2.07 * fz]
            if not pd.get('size'):
                v += [0.33, 0.165]
            x[prob.idx[(n, p)]] = v
    for f in prob.feats:
        g = GUESS[f]
        x[prob.idx[('feat', f)]] = [g[1], g[2]] if f.startswith('c_') else g
    # stage 1: each camera alone with the features fixed; stage 2: everything
    x, cost = lm(prob, x, 80)
    r, info = prob.residuals(x, True)
    out = {'cams': {}, 'rms_px': {}, 'pose': {}, 'feats': {}, 'plates': {}}
    for n in names:
        W, H = A[n]['size']
        cam = x[prob.idx[(n, 'cam')]]
        out['cams'][n] = [*map(float, cam[:6]), float(math.exp(cam[6])), [W, H]]
        e_pts = [d for (m, k, d) in info if m == n and not k.startswith('w') and not k.startswith('plate')]
        e_rim = [d for (m, k, d) in info if m == n and k.startswith('w')]
        e_pl = [d for (m, k, d) in info if m == n and k.startswith('plate')]
        allp = e_pts + e_rim + e_pl
        rms = float(np.sqrt(np.mean(np.square(allp))))
        out['rms_px'][n] = round(rms, 2)
        pose = x[prob.idx[(n, 'pose')]]
        out['pose'][n] = {'dy': round(float(pose[0]), 4), 'pitch_deg': round(math.degrees(pose[1]), 3), 'rim': [round(float(v), 3) for v in x[prob.idx[(n, 'rim')]]]}
        for p in A[n].get('plates', {}):
            out['plates'][f'{n}.{p}'] = [round(float(v), 4) for v in x[prob.idx[(n, p)]]]
        print(f'{n}: rms {rms:.2f}px (pts {np.sqrt(np.mean(np.square(e_pts))) if e_pts else 0:.2f}, rims {np.sqrt(np.mean(np.square(e_rim))) if e_rim else 0:.2f}, plates {np.sqrt(np.mean(np.square(e_pl))) if e_pl else 0:.2f}) '
              f'f {math.exp(cam[6]):.0f} C {np.round(cam[:3], 2)} dy {pose[0]:+.3f} pitch {math.degrees(pose[1]):+.2f}deg rim {np.round(x[prob.idx[(n, "rim")]], 3)}')
        worst = sorted([(d, k) for (m, k, d) in info if m == n], reverse=True)[:4]
        print('   worst', ', '.join(f'{k} {d:.1f}' for d, k in worst))
    for f in prob.feats:
        v = prob.feat3(x, f)
        out['feats'][f] = [round(float(abs(v[0]) if not f.endswith('_s') else v[0]), 4), round(float(v[1]), 4), round(float(v[2]), 4)]
        print(f'  feat {f:12s} {np.round(out["feats"][f], 3)}')
    json.dump(out, open(sys.argv[2], 'w'), indent=1)


if __name__ == '__main__':
    main()
