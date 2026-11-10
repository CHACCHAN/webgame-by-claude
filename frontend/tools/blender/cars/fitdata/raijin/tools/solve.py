"""solve.py <annot.json> <cams.json> [names] [--anchors anchors.json] : per-photo camera solve for the GDB STI
(game frame: metres, x left, y up, z forward, ground y = 0, origin midway between the axles).
annot entry: {"size": [W, H], "init": [x, y, z, yaw, pitch, roll, f], "rims": "<rimfit json>" (points on each visible
rim lip, refined by rimfit.py), "rim": lip radius prior, "rim_sigma", "wb", "track": [front, rear],
"pts": {"<feat>_l|_r": [u, v]} (body features from FEATS, mirrored), "prior": {"x|y|z|yaw|pitch|roll|f|steer|py|pz":
[mean, sigma]}, "plate": {"end": "f"|"r", "size": [w, h] | [w, null] | null, "corners": {"tl","tr","br","bl"}}}
Unknowns: camera (7), front steer, rim lip radius and plane offset, plate centre (y, z) and free plate size.
Rim residual = distance of each annotated lip point to the projected 3D lip circle.
Writes cams.json {"cams": {n: [x,y,z,yaw,pitch,roll,f,[W,H]]}, "rms", "pose"} and optionally anchors for ffdfit.py
([x, y, z, u, v, wu, wv, body, group] rows)."""
import json, math, os, sys
import numpy as np
FEATS = {'mirror': [1.062, 0.978, 0.56]}
LIP = 0.100
RW = 0.312


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


def feat_pt(name):
    base, s = name[:-2], (1 if name.endswith('_l') else -1)
    p = np.array(FEATS[base], float); p[0] = s * abs(p[0])
    return p


def solve(a, base_dir, verbose=True):
    W, H = a['size']; rim0 = a.get('rim', 0.228)
    WB = a.get('wb', 2.525); TF, TR = a.get('track', (1.485, 1.480))
    names = list(a.get('pts', {}))
    P = np.array([feat_pt(k) for k in names], float).reshape(-1, 3)
    O = np.array([a['pts'][k] for k in names], float).reshape(-1, 2)
    pl = a.get('plate'); pri = a.get('prior', {})
    rims = a.get('rims', {})
    if isinstance(rims, str):
        rims = {k: v['pts'] for k, v in json.load(open(os.path.join(base_dir, rims))).items()}
    psz = pl.get('size') if pl else None
    free_w = pl is not None and not psz
    free_h = pl is not None and (not psz or psz[1] is None)
    i0 = a['init']
    x = np.array(list(i0[:6]) + [math.log(i0[6]), 0.0, rim0, LIP,
                                  pl.get('y', 0.45) if pl else 0, pl.get('z', 2.2) if pl else 0, 0.3, 0.13], float)
    th = np.linspace(0, 2 * math.pi, 720, endpoint=False)

    def circle(w, steer, rim, lip):
        side = 1 if w[1] == 'l' else -1; front = w[0] == 'f'
        t = (TF if front else TR) / 2; z = WB / 2 if front else -WB / 2
        loc = np.stack([np.full_like(th, side * lip), rim * np.cos(th), rim * np.sin(th)], 1)
        if front and steer:
            c, s_ = math.cos(steer), math.sin(steer)
            loc = np.stack([loc[:, 0] * c + loc[:, 2] * s_, loc[:, 1], -loc[:, 0] * s_ + loc[:, 2] * c], 1)
        return loc + np.array([side * t, RW, z])

    def plate_corners(x):
        pw = x[12] if free_w else psz[0]
        ph = x[13] if free_h else psz[1]
        sx = -1 if pl['end'] == 'f' else 1
        yc, zc = x[10], x[11]
        return np.array([[sx * pw / 2, yc + ph / 2, zc], [-sx * pw / 2, yc + ph / 2, zc],
                         [-sx * pw / 2, yc - ph / 2, zc], [sx * pw / 2, yc - ph / 2, zc]])

    def res(x, detail=False):
        cam = list(x[:6]) + [math.exp(x[6])]
        r, uv_all, ob_all, nm = [], [], [], []
        if len(P):
            uv = project(cam, P, W, H); r.append((uv - O).ravel()); uv_all.append(uv); ob_all.append(O); nm += names
        if pl:
            puv = project(cam, plate_corners(x), W, H)
            po = np.array([pl['corners'][k] for k in ('tl', 'tr', 'br', 'bl')], float)
            r.append((puv - po).ravel()); uv_all.append(puv); ob_all.append(po); nm += ['pl_tl', 'pl_tr', 'pl_br', 'pl_bl']
        rimd = {}
        for w, pts in rims.items():
            cuv = project(cam, circle(w, x[7], x[8], x[9]), W, H)
            pts = np.array(pts, float)
            dd = np.sqrt(((pts[:, None, :] - cuv[None]) ** 2).sum(2)).min(1)
            rimd[w] = dd
            r.append(dd * math.sqrt(4.0 / len(pts)))
        for k, i in (('x', 0), ('y', 1), ('z', 2), ('yaw', 3), ('pitch', 4), ('roll', 5), ('steer', 7)):
            if k in pri: r.append(np.array([(x[i] - pri[k][0]) / pri[k][1]]))
        if 'f' in pri: r.append(np.array([(math.exp(x[6]) - pri['f'][0]) / pri['f'][1]]))
        if pl and 'pz' in pri: r.append(np.array([(x[11] - pri['pz'][0]) / pri['pz'][1]]))
        if pl and 'py' in pri: r.append(np.array([(x[10] - pri['py'][0]) / pri['py'][1]]))
        r.append(np.array([x[7] / 0.3, (x[8] - rim0) / a.get('rim_sigma', 0.01), (x[9] - LIP) / 0.02]))
        if not pl: r.append(np.array([x[10] - 0.45, x[11] - 2.2, x[12] - 0.3, x[13] - 0.13]) * 100)
        else:
            if not free_w: r.append(np.array([(x[12] - 0.3) * 100]))
            if not free_h: r.append(np.array([(x[13] - 0.13) * 100]))
        rr = np.concatenate(r)
        if detail:
            return rr, (np.vstack(uv_all) if uv_all else np.zeros((0, 2))), (np.vstack(ob_all) if ob_all else np.zeros((0, 2))), nm, rimd
        return rr

    lam = 1e-3; r = res(x); cost = r @ r
    for it in range(300):
        J = np.zeros((len(r), len(x)))
        for j in range(len(x)):
            h = 1e-6 * max(1, abs(x[j])); xp = x.copy(); xp[j] += h; xm = x.copy(); xm[j] -= h
            J[:, j] = (res(xp) - res(xm)) / (2 * h)
        g = J.T @ r; A = J.T @ J
        ok = False
        for _ in range(20):
            dx = -np.linalg.solve(A + lam * np.diag(np.diag(A) + 1e-9), g)
            rn = res(x + dx); cn = rn @ rn
            if cn < cost:
                x, r, cost, lam, ok = x + dx, rn, cn, lam * 0.3, True; break
            lam *= 10
        if not ok or np.abs(dx).max() < 1e-10: break
    rr, uv, ob, nm, rimd = res(x, True)
    e = np.hypot(*(uv - ob).T) if len(uv) else np.zeros(0)
    allerr = np.concatenate([e] + list(rimd.values()))
    rms = float(np.sqrt((allerr ** 2).mean()))
    cam = [float(v) for v in x[:6]] + [float(math.exp(x[6]))]
    if verbose:
        for n, ee, p, o in zip(nm, e, uv, ob):
            print(f'   {n:10s} err {ee:5.1f}  model ({p[0]:7.1f},{p[1]:7.1f})  photo ({o[0]:6.1f},{o[1]:6.1f})')
        for w, dd in rimd.items():
            print(f'   rim {w}: mean {dd.mean():.2f} max {dd.max():.2f} px')
        print(f'   steer {math.degrees(x[7]):+.1f} deg rim {x[8]:.3f} lip {x[9]:.3f}' + (f'  plate y {x[10]:.3f} z {x[11]:.3f} size {x[12] if free_w else psz[0]:.3f}x{x[13] if free_h else psz[1]:.3f}' if pl else ''))
    # anchors: rim points pinned to their nearest 3D lip point (rigid wheels), plate corners and features on the body
    anch = []
    for w, pts in rims.items():
        C3 = circle(w, x[7], x[8], x[9]); cuv = project(cam, C3, W, H)
        wt = round(math.sqrt(4.0 / len(pts)), 3)
        for p in pts:
            k = int(np.argmin(((cuv - np.array(p)) ** 2).sum(1)))
            anch.append([*np.round(C3[k], 4).tolist(), round(p[0], 1), round(p[1], 1), wt, wt, 0, 0])
    if pl:
        pc = plate_corners(x)
        for P3, k in zip(pc, ('tl', 'tr', 'br', 'bl')):
            anch.append([*np.round(P3, 4).tolist(), *pl['corners'][k], 0.8, 0.8, 1, 2])
    for k, p3, o in zip(names, P, O):
        anch.append([*np.round(p3, 4).tolist(), float(o[0]), float(o[1]), 0.5, 0.5, 1, 0])
    return cam + [[W, H]], rms, anch


if __name__ == '__main__':
    a = sys.argv[1:]
    anc_out = a[a.index('--anchors') + 1] if '--anchors' in a else None
    a = [v for i, v in enumerate(a) if v != '--anchors' and (i == 0 or a[i - 1] != '--anchors')]
    A = json.load(open(a[0])); out = a[1]; base = os.path.dirname(os.path.abspath(a[0]))
    names = a[2].split(',') if len(a) > 2 else [k for k in A if not k.startswith('_')]
    C = json.load(open(out)) if os.path.exists(out) else {'cams': {}, 'rms': {}, 'pose': {}}
    AN = json.load(open(anc_out)) if anc_out and os.path.exists(anc_out) else {}
    for n in names:
        print(n)
        cam, rms, anch = solve(A[n], base)
        print(f' {n}: rms {rms:.2f} px  cam ({cam[0]:.2f},{cam[1]:.2f},{cam[2]:.2f}) yaw {math.degrees(cam[3]):.1f} pitch {math.degrees(cam[4]):.1f} roll {math.degrees(cam[5]):.2f} f {cam[6]:.0f}')
        C['cams'][n] = cam; C['rms'][n] = round(rms, 2); C.setdefault('pose', {}).setdefault(n, {'dy': 0.0, 'pitch_deg': 0.0})
        AN[n] = anch
    json.dump(C, open(out, 'w'), indent=1)
    if anc_out: json.dump(AN, open(anc_out, 'w'))
