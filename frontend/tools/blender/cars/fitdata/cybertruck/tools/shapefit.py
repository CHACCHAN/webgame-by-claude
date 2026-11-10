"""
shapefit.py <annot.json> <ba.json> <out shape.json> [--free a,b,...] [--fixcams] [--photos a,b] [--verbose] [--sil weight] [--lensig m]
    [--lamps lamps.json]
    [--plot outdir,photodir]
Fits the shape parameters of cybertruck_shape (the flat panels: beltline, hood, windscreen, roof, faces, arches,
creases) together with the cameras and body poses to the points read off the photos (annot.json): the model's named
features (cybertruck_shape.features) are projected through each camera and compared with the annotations. Cameras and
poses start from the bundle adjustment (ba.json); the EXIF focal priors of annot.json apply; the published length
(5683 mm) and width (2027 mm, fixed: sw) hold. Robust (Huber) Levenberg-Marquardt with a numerical Jacobian.

Writes {"params": {...}, "cams": {...}, "pose": {...}, "rms": {photo: px}, "res": {photo: {pt: px}}} to <out>; the
params block is what cybertruck_shape.load() merges over its defaults; cams/pose feed loop.py (--cams/--pose).
"""
import json, math, os, sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, '..', '..', '..')))
sys.dont_write_bytecode = True
import cybertruck_shape as CS  # noqa: E402
import cybertruck_parts as PT  # noqa: E402

a = sys.argv[1:]
A = json.load(open(a[0]))
BA = json.load(open(a[1]))
OUT = a[2]
VERB = '--verbose' in a
only = a[a.index('--photos') + 1].split(',') if '--photos' in a else None
P0 = CS.load(OUT if os.path.exists(OUT) else None)

# free parameters and their prior sigma (m or deg) about the start values
FREE = {
    'belt_f': 0.05, 'belt_r': 0.05, 'tumble': 4, 'zf': 0.05, 'yk': 0.05, 'face_lean': 0.02, 'xk': 0.05, 'y_ff': 0.05,
    'zws': 0.08, 'yws': 0.05, 'zpk': 0.10, 'ypk': 0.05, 'roof': 2, 'tg_lean': 0.03, 'y_lb': 0.05, 'y_tgb': 0.05,
    'lc_f': 0.05, 'lc_r': 0.05, 'lower': 5, 'y_db': 0.05, 'w_bot': 0.03, 'w_top': 0.03, 'w_a': 0.03, 'w_cb': 0.05,
    'w_ct': 0.05, 'cl_out': 0.02,
    'af_bf_z': 0.08, 'af_bf_y': 0.08, 'af_tf_z': 0.08, 'af_tf_y': 0.08, 'af_tr_z': 0.08, 'af_tr_y': 0.08,
    'af_br_z': 0.08, 'af_br_y': 0.08, 'ar_bf_z': 0.08, 'ar_bf_y': 0.08, 'ar_tf_z': 0.08, 'ar_tf_y': 0.08,
    'ar_tr_z': 0.08, 'ar_tr_y': 0.08, 'ar_br_z': 0.08, 'ar_br_y': 0.08,
    'fb_top': 0.05, 'fb_side': 0.05, 'rb_top': 0.05, 'rb_side': 0.05, 'rb_z': 0.05,
    'hub_x': 0.05, 'hub_y': 0.03, 'plf_y': 0.05, 'plf_z': 0.05, 'plr_y': 0.05, 'plr_z': 0.05, 'z_rg': 0.10,
    'fb_z': 0.05, 'fb_low': 0.05, 'fb_bot': 0.05, 'fb_botz': 0.05, 'rb_bot': 0.05, 'y_rk': 0.05, 'rb_mid': 0.05, 'rb_lw': 0.08, 'rb_lz': 0.04,
}
LAMPS = json.load(open(a[a.index('--lamps') + 1])) if '--lamps' in a else {}
if LAMPS:
    # the lamp outlines traced on the photos join the points (vertex to vertex), with the lamp parameters free
    FREE.update({'bar': 0.01, 'bar_h': 0.01, 'hl_x0': 0.05, 'hl_x1': 0.05, 'hl_h': 0.01, 'hl_gap': 0.01, 'tl_kx': 0.01,
                 'tl_kw': 0.02, 'tl_kt': 0.01, 'tl_kh': 0.02, 'tl_cy': 0.02, 'tl_ch': 0.005, 'tl_cw': 0.05})
LAMP_SIG = 1.5
if '--free' in a:
    keep = a[a.index('--free') + 1].split(',')
    FREE = {k: v for k, v in FREE.items() if k in keep}
FIXCAMS = '--fixcams' in a
LEN_SIG = float(a[a.index('--lensig') + 1]) if '--lensig' in a else 0.01
photos = [p for p in A if not p.startswith('_') and p in BA['cams'] and (only is None or p in only)]
ref = [p for p in photos if A[p].get('ref')] or photos[:1]
PLATE = (0.3048, 0.1524)
WB = CS.WB


def basis(yaw, pitch, roll):
    d = np.array([math.sin(yaw) * math.cos(pitch), math.sin(pitch), math.cos(yaw) * math.cos(pitch)])
    r = np.cross(d, [0, 1, 0]); r /= np.linalg.norm(r)
    u = np.cross(r, d)
    c, s = math.cos(roll), math.sin(roll)
    return d, c * r + s * u, -s * r + c * u


def project(cam, X):
    x, y, z, yaw, pitch, roll, f = cam[:7]
    W, H = cam[7]
    d, r, u = basis(yaw, pitch, roll)
    Q = X - np.array([x, y, z])
    zc = Q @ d
    return np.stack([W / 2 + f * (Q @ r) / zc, H / 2 - f * (Q @ u) / zc], axis=-1)


def posed(v, dy, th):
    c, s = math.cos(th), math.sin(th)
    out = v.copy()
    out[..., 1] = c * v[..., 1] + s * v[..., 2] + dy
    out[..., 2] = -s * v[..., 1] + c * v[..., 2]
    return out


# parameter vector: shape params, then per photo camera (6 + log f) and pose (dy, pitch) except the reference
names = list(FREE)
off = len(names)
camidx, poseidx = {}, {}
for p in photos:
    if not FIXCAMS:
        camidx[p] = off; off += 7
    if p not in ref:
        poseidx[p] = off; off += 2
X0 = np.zeros(off)
for i, n in enumerate(names):
    X0[i] = P0[n]
for p in photos:
    c = BA['cams'][p]
    if p in camidx:
        X0[camidx[p]:camidx[p] + 6] = c[:6]; X0[camidx[p] + 6] = math.log(c[6])
    if p in poseidx:
        q = BA['pose'].get(p, {})
        X0[poseidx[p]] = q.get('dy', 0.0); X0[poseidx[p] + 1] = math.radians(q.get('pitch_deg', 0.0))
SCALE = np.array([FREE[n] for n in names] + [1.0] * (off - len(names)))
# finite-difference steps: big enough to move the rasterised outlines by a fraction of a pixel
STEP = np.array([0.1 * FREE[n] for n in names] + [0.0] * (off - len(names)))
for p in photos:
    if p in camidx:
        STEP[camidx[p]:camidx[p] + 7] = [0.005, 0.005, 0.005, 2e-4, 2e-4, 2e-4, 2e-3]
    if p in poseidx:
        STEP[poseidx[p]:poseidx[p] + 2] = [0.002, 2e-4]


def params(X):
    P = dict(P0)
    for i, n in enumerate(names):
        P[n] = float(X[i])
    return P


def length_of(P, S):
    zt = S.T[2] + (S.T[1] - P['y_tgb']) * S.tg_tl
    front = max(P['fb_z'], P['zf'] + P['face_lean'])
    rear = min(P['rb_z'], S.T[2], zt)
    return front - rear


PLOT = {}
# --- silhouettes: the photo masks against a fast rasterisation of the model's panels (every face is convex, the union
# of their projections is the silhouette), both blurred a little so the misfit is smooth in the parameters
SIL_W = float(a[a.index('--sil') + 1]) if '--sil' in a else 0.0
SIL_RES = 320
SIL_BAND = 9          # px (at SIL_RES) either side of the photo's outline: only there can the misfit change
MASKS = {}
if SIL_W > 0:
    import cv2
    from PIL import Image
    mdir = os.path.join(HERE, '..', 'masks')
    for p in photos:
        W, H = BA['cams'][p][7]
        m = np.array(Image.open(os.path.join(mdir, p + '.png')).convert('L'))
        sc = SIL_RES / W
        w, h = SIL_RES, int(round(H * sc))
        car = cv2.resize((m == 255).astype(np.float32), (w, h), interpolation=cv2.INTER_AREA)
        ign = cv2.resize((m == 128).astype(np.float32), (w, h), interpolation=cv2.INTER_AREA)
        k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * SIL_BAND + 1, 2 * SIL_BAND + 1))
        cb = (car > 0.5).astype(np.uint8)
        band = (cv2.dilate(cb, k) > 0) & ~(cv2.erode(cb, k) > 0) & (ign < 0.05)
        MASKS[p] = (cv2.GaussianBlur(car, (0, 0), 1.0), (ign < 0.05).astype(np.float32), sc, np.flatnonzero(band))


def scene_polys(P, S):
    """(body polygons, wheel polygons) as lists of (n, 3) arrays"""
    _, faces = CS.all_faces(P)
    mir = PT.mirror_unit(P, S)
    faces = faces + mir + PT.mirrored(mir)
    body = [np.array(f.pts, float) for f in faces if len(f.pts) >= 3]
    wheels = []
    R, tf = P['tyre_r'], P['track'] / 2
    a = np.linspace(0, 2 * np.pi, 40, endpoint=False)
    for sx in (1, -1):
        for sz in (1, -1):
            cx, cz = sx * tf, sz * WB / 2
            pts = []
            for dx, r in ((-0.148, 0.40), (-0.112, R), (0.112, R), (0.148, 0.40)):
                pts.append(np.stack([np.full_like(a, cx + dx), np.maximum(P['hub_y'] + r * np.cos(a), 0.0), cz + r * np.sin(a)], 1))
            wheels.append(np.concatenate(pts))
    return body, wheels


def raster(cam, dy, th, body, wheels, sc, shape):
    import cv2
    img = np.zeros(shape, np.uint8)
    allb = np.concatenate(body)
    uvb = project(cam, posed(allb, dy, th)) * sc
    k = 0
    for f in body:
        n = len(f)
        q = np.round(uvb[k:k + n] * 16).astype(np.int32)
        k += n
        cv2.fillConvexPoly(img, q, 255, cv2.LINE_AA, 4)
    for w in wheels:
        uv = project(cam, w) * sc
        hull = cv2.convexHull(np.round(uv * 16).astype(np.int32))
        cv2.fillConvexPoly(img, hull, 255, cv2.LINE_AA, 4)
    return img.astype(np.float32) / 255.0


def sil_residuals(P, S, X, detail=False):
    import cv2
    body, wheels = scene_polys(P, S)
    out, det = [], {}
    for p in photos:
        if p not in MASKS:
            continue
        car, wt, sc, idx = MASKS[p]
        cam = cam_of(p, X)
        dy, th = pose_of(p, X)
        R = cv2.GaussianBlur(raster(cam, dy, th, body, wheels, sc, car.shape), (0, 0), 1.0)
        d = (R - car) * wt
        out.append(SIL_W * d.ravel()[idx])
        if detail:
            inter = ((R > 0.5) & (car > 0.5) & (wt > 0)).sum(); uni = (((R > 0.5) | (car > 0.5)) & (wt > 0)).sum()
            det[p] = round(float(inter / max(uni, 1)), 4)
            SILS[p] = (R, car, wt)
    return out, det


SILS = {}


def cam_of(p, X):
    if p in camidx:
        return list(X[camidx[p]:camidx[p] + 6]) + [math.exp(X[camidx[p] + 6]), BA['cams'][p][7]]
    return BA['cams'][p]


def pose_of(p, X):
    return (X[poseidx[p]], X[poseidx[p] + 1]) if p in poseidx else (0.0, 0.0)


def residuals(X, detail=False):
    P = params(X)
    S = CS.Shape(P)
    F = CS.features(P, S)
    r, det = [], {}
    for p in photos:
        if p in camidx:
            cam = list(X[camidx[p]:camidx[p] + 6]) + [math.exp(X[camidx[p] + 6]), BA['cams'][p][7]]
        else:
            cam = BA['cams'][p]
        dy, th = (X[poseidx[p]], X[poseidx[p] + 1]) if p in poseidx else (0.0, 0.0)
        P3, O, nm, posedmask = [], [], [], []
        for k, uv in A[p].get('pts', {}).items():
            base, side = k[:-2], k[-1]
            if base.startswith('hub_'):
                x = P['hub_x']
                P3.append([x if side == 'l' else -x, P['hub_y'], WB / 2 if base == 'hub_f' else -WB / 2]); posedmask.append(False)
            elif base in F:
                v = list(F[base])
                if side == 'r':
                    v[0] = -v[0]
                elif side == 'c':
                    v[0] = 0.0
                P3.append(v); posedmask.append(True)
            else:
                continue
            O.append(uv); nm.append(k)
        if 'plate' in A[p]:
            pl = A[p]['plate']
            yc, zc = (P['plf_y'], P['plf_z']) if pl['end'] == 'f' else (P['plr_y'], P['plr_z'])
            sx = -1 if pl['end'] == 'f' else 1
            for k, (cx, cy) in zip(('tl', 'tr', 'br', 'bl'), ((sx, 1), (-sx, 1), (-sx, -1), (sx, -1))):
                P3.append([cx * PLATE[0] / 2, yc + cy * PLATE[1] / 2, zc]); posedmask.append(True)
                O.append(pl['corners'][k]); nm.append('plate_' + k)
        P3 = np.array(P3, float); O = np.array(O, float); pm = np.array(posedmask)
        P3[pm] = posed(P3[pm], dy, th)
        uv = project(cam, P3)
        e = (uv - O) / A[p].get('sigma', 2.0)
        n = np.hypot(e[:, 0], e[:, 1])
        k = 2.5
        w = np.where(n <= k, 1.0, np.sqrt(np.maximum(k * (2 * n - k), 0)) / np.maximum(n, 1e-9))
        r.append((e * w[:, None]).ravel())
        if detail:
            det[p] = {m: round(float(np.hypot(*(uv[i] - O[i]))), 2) for i, m in enumerate(nm)}
            PLOT[p] = (uv, O, nm)
            if VERB:
                print(p, ' '.join(f'{m}:{uv[i][0] - O[i][0]:+.0f},{uv[i][1] - O[i][1]:+.0f}' for i, m in enumerate(nm)))
        if p in LAMPS:
            LO = PT.lamp_outlines(P, S)
            for k, tr in LAMPS[p].items():
                if k == 'lit' or k not in LO:
                    continue
                uvl = project(cam, posed(np.array(LO[k], float), dy, th))
                el = (uvl - np.array(tr, float)) / LAMP_SIG
                r.append(el.ravel())
                if detail:
                    det[p]['lamp_' + k] = round(float(np.sqrt((el ** 2).sum(1).mean()) * LAMP_SIG), 2)
        if p in poseidx:
            r.append(np.array([dy / 0.08, th / 0.02]))
        if p in camidx and 'f_exif' in A[p]:
            r.append(np.array([(X[camidx[p] + 6] - math.log(A[p]['f_exif'])) / A[p].get('f_sig', 0.1)]))
    # priors on the shape parameters, the published length
    r.append((X[:len(names)] - X0[:len(names)]) / np.array([FREE[n] for n in names]))
    r.append(np.array([(length_of(P, S) - CS.LENGTH) / LEN_SIG]))
    if SIL_W > 0:
        sr, sdet = sil_residuals(P, S, X, detail)
        r += sr
        if detail:
            det['_iou'] = sdet
    rr = np.concatenate(r)
    return (rr, det) if detail else rr


def solve(X):
    r = residuals(X); cost = r @ r; lam = 1e-2
    for it in range(80):
        J = np.zeros((len(r), len(X)))
        for j in range(len(X)):
            h = STEP[j]
            xp = X.copy(); xp[j] += h; xm = X.copy(); xm[j] -= h
            J[:, j] = (residuals(xp) - residuals(xm)) / (2 * h)
        g = J.T @ r; Hm = J.T @ J
        ok = False
        for _ in range(12):
            dx = -np.linalg.solve(Hm + lam * np.diag(np.diag(Hm) + 1e-9), g)
            rn = residuals(X + dx); cn = rn @ rn
            if np.isfinite(cn) and cn < cost:
                X, r, lam, ok = X + dx, rn, lam * 0.3, True
                dc = cost - cn; cost = cn
                break
            lam *= 10
        if VERB:
            print(f'it {it} cost {cost:.1f} lam {lam:.1e}')
        if not ok or dc < 1e-6 * cost:
            break
    return X


X = solve(X0.copy())
rr, det = residuals(X, True)
P = params(X)
S = CS.Shape(P)
iou = det.pop('_iou', {})
res = {'params': {n: round(P[n], 4) for n in names}, 'cams': {}, 'pose': {}, 'rms': {}, 'res': det, 'iou': iou}
old = json.load(open(OUT)) if os.path.exists(OUT) else {}
keep = dict(old.get('params', {}))
keep.update(res['params'])
res['params'] = keep
for p in photos:
    if p in camidx:
        c = [float(v) for v in X[camidx[p]:camidx[p] + 6]] + [float(math.exp(X[camidx[p] + 6])), BA['cams'][p][7]]
    else:
        c = BA['cams'][p]
    res['cams'][p] = c
    dy, th = (float(X[poseidx[p]]), float(X[poseidx[p] + 1])) if p in poseidx else (0.0, 0.0)
    res['pose'][p] = {'dy': round(dy, 4), 'pitch_deg': round(math.degrees(th), 3)}
    e = np.array([v for k, v in det[p].items() if not k.startswith('lamp_')])
    res['rms'][p] = round(float(np.sqrt((e ** 2).mean())), 2)
json.dump(res, open(OUT, 'w'), indent=1)
for p in photos:
    c = res['cams'][p]
    worst = sorted(det[p].items(), key=lambda kv: -kv[1])[:5]
    print(f'{p:6s} rms {res["rms"][p]:5.2f}px f {c[6]:6.0f} iou {iou.get(p, 0):.4f} pose {res["pose"][p]} worst {worst}')
print(f'length {length_of(P, S):.4f}  tail {tuple(round(v, 3) for v in S.T)}  nose {tuple(round(v, 3) for v in S.N)}')
if '--plot' in a:
    # annotations (green rings) and the model's features (red dots) with the error line, on each photo
    from PIL import Image, ImageDraw
    pdir, phdir = a[a.index('--plot') + 1].split(',')
    os.makedirs(pdir, exist_ok=True)
    for p, (uv, O, nm) in PLOT.items():
        im = Image.open(os.path.join(phdir, p + '.jpg')).convert('RGB')
        d = ImageDraw.Draw(im)
        for (u, v), (ou, ov), m in zip(uv, O, nm):
            d.ellipse([ou - 4, ov - 4, ou + 4, ov + 4], outline=(0, 255, 0))
            d.line([ou, ov, u, v], fill=(255, 255, 0))
            d.ellipse([u - 2, v - 2, u + 2, v + 2], fill=(255, 0, 0))
            d.text((ou + 5, ov - 12), m, fill=(255, 255, 0))
        im.save(os.path.join(pdir, p + '_pts.jpg'))
    for p, (R, car, wt) in SILS.items():
        # red: model only, blue: photo only, grey: both; ignored areas dark
        o = np.zeros(R.shape + (3,), np.float32)
        o[..., 0] = R; o[..., 2] = car; o[..., 1] = np.minimum(R, car)
        o *= (0.3 + 0.7 * wt)[..., None]
        Image.fromarray((o * 255).astype(np.uint8)).save(os.path.join(pdir, p + '_sil.png'))
for n in names:
    if abs(P[n] - P0[n]) > 1e-4:
        print(f'  {n:10s} {P0[n]:8.3f} -> {P[n]:8.3f}')
