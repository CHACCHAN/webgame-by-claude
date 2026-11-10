"""
fit.py: the photos' cameras and the nose's shape table together, by silhouettes (the photo masks of mkmask.py) and
the livery points of the bundle adjustment (their 3D positions held as ba.py solved them).

  py fit.py <cams.json> <workdir> <annot.json> <ba.json> <shape_in.json|-> <out_prefix>
            [--photos c07,c04] [--cams-only] [--shape-only] [--steps 20] [--sigma 3] [--scale 0.5] [--verbose]
            [--lamps lamps.json] [--tipsmooth 0.3] [--tipfree] [--bot B] [--df 0.4 --yc 0.7 --m 3]
  -> <out_prefix>_cams.json, <out_prefix>_shape.json (and the scores per photo)
The final round (gC, l0_shape's table): cams.json from ba.json's round, then
  fit.py cams.json . annot.json ba.json - gC --photos c07,c04,c12 --steps 30 --lamps lamps.json --tipsmooth 0.08 --tipfree
The face is a cap (l0_shape.CAP: the section at df shrunk towards (0, yc), bluntness m); --tipfree also fits the tip's
set-back from the published length (REF_TIP), else it is held there.

Silhouette residuals: the decided pixels (mask != 128) of a band round the mask's outline, of
blur(model - train) (the difference blurred: smooth in the parameters, no pull from the ignored pixels).
Each photo's silhouette is weighted so that the whole outline off by 1 px costs about as much as 25 points off by
1.5 px. Shape: the cap's yc and m, the tip's set-back, rows 1 … n-2 of the nose table (top, yw, hw; bot, nt, nb near the
tip), with a smoothness prior along the nose (second differences) and a weak prior to the start.
"""
import json, math, os, sys, time

import cv2
import numpy as np

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, '..', '..', '..', 'parts'))
import cam as C
import l0_shape as S

KEYS = ('top', 'yw', 'hw', 'bot')
KI = {k: S._KEYS.index(k) + 1 for k in S._KEYS}    # column in a table row (d first)
BAD_PTS = ('bt', 'bl', 'vent_tf', 'vent_br', 'door_tf', 'door_tr')


# ------------------------------------------------------------------ the model's silhouette
def train_rings(nose_steps):
    """per car: array (stations, 2 HALF_N, 3) of the full sections in the train frame"""
    cars = []
    for name, kind in (('car0', 'end'), ('car1', 'mid'), ('car2', 'end')):
        rs = S.rings(kind, step=4.0, nose_steps=nose_steps)
        A = []
        for z, half in rs:
            full = np.vstack([half, (half * [-1, 1])[::-1]])
            A.append(np.column_stack([full[:, 0], full[:, 1], np.full(len(full), z)]))
        A = np.array(A)
        if name == 'car2':
            A = A * [-1, 1, -1]
        A[..., 2] += S.CAR_Z[name]
        cars.append(A)
    return cars


def coarse_nose_ds():
    ds = list(np.arange(S.NOSE_LEN - 0.5, 2.4, -0.5)) + list(np.geomspace(2.4, 0.006, 16))
    return ds


def raster(cam, W, H, cars, s):
    m = np.zeros((int(round(H * s)), int(round(W * s))), np.uint8)
    for A in cars:
        n, k, _ = A.shape
        P = C.project(cam, A.reshape(-1, 3), W, H).reshape(n, k, 3)
        for i in range(n - 1):
            q = P[i:i + 2].reshape(-1, 3)
            if (q[:, 2] < 0.5).any():
                continue
            pts = np.round(q[:, :2] * s * 16).astype(np.int32)
            hull = cv2.convexHull(pts)
            cv2.fillConvexPoly(m, hull, 1, lineType=cv2.LINE_8, shift=4)
    return m


# ------------------------------------------------------------------ shape parameters
def free_list(table):
    """the free (row, key) pairs: top, hw, yw along the nose; the bottom only near the tip (hidden by the guideway
    walls further back)"""
    fl = []
    for i, row in enumerate(table[1:-1], 1):
        for k in KEYS + ('nt', 'nb'):
            if k in ('bot', 'nt', 'nb') and row[0] > 1.8:
                continue
            fl.append((i, k))
    return fl


NHEAD = 3          # the shape vector starts with the face's centre height, its bluntness and the tip's set-back


def capped(table):
    """the table for the capped face: rows nearer the tip than the cap's df dropped, row 0 a copy of the df row"""
    df = S.CAP['df']
    rows = [list(r) for r in table if r[0] >= df - 1e-9]
    if abs(rows[0][0] - df) > 1e-9:
        p = S.NOSE.params(df)
        rows.insert(0, [df] + [p[k] for k in S._KEYS])
    return [[0.0] + rows[0][1:]] + rows


def shape_vec(table, fl, head):
    return np.array(list(head) + [table[i][KI[k]] for i, k in fl], float)


def table_from(v, base, fl):
    t = [list(r) for r in base]
    for j, (i, k) in enumerate(fl, NHEAD):
        t[i][KI[k]] = float(v[j])
    for row in t[1:-1]:
        row[KI['hw']] = min(max(row[KI['hw']], 0.02), S.HW)
        row[KI['nt']] = min(max(row[KI['nt']], 1.6), 5.0)
        row[KI['nb']] = min(max(row[KI['nb']], 1.6), 5.0)
        row[KI['bot']] = max(row[KI['bot']], 0.05)
        # a rounded shoulder: the upper quadrant keeps at least a fifth of the section's height (12 cm)
        up = max(0.12, 0.2 * (row[KI['top']] - row[KI['bot']]))
        row[KI['yw']] = min(max(row[KI['yw']], row[KI['bot']] + 0.05), row[KI['top']] - up)
    t[0] = [0.0] + t[1][1:]
    return t


def head_from(v):
    """cap (yc, m) and the tip's z"""
    return dict(yc=float(v[0]), m=min(max(float(v[1]), 1.6), 8.0)), TIP0 - float(v[2])


def main():
    a = sys.argv[1:]

    def opt(k, d=None):
        return a[a.index(k) + 1] if k in a else d
    cams_in, wd, annot_p, ba_p, shape_in, prefix = a[:6]
    cams = json.load(open(cams_in))['cams']
    A = json.load(open(annot_p))
    BA = json.load(open(ba_p))['points']
    photos = opt('--photos', 'c07,c04').split(',')
    steps = int(opt('--steps', '20'))
    sigma = float(opt('--sigma', '3'))
    s = float(opt('--scale', '0.5'))
    verbose = '--verbose' in a
    do_cams = '--shape-only' not in a
    do_shape = '--cams-only' not in a
    lamps = json.load(open(opt('--lamps'))) if opt('--lamps') else None
    TIPMESH = {}
    if lamps:
        import measure as MS

    def tip_mesh():
        if 'V' not in TIPMESH:
            Vs, Fs = S.shell_mesh('end', step=4.0)
            TIPMESH['V'], TIPMESH['F'] = Vs, Fs[(Vs[:, 2] > S.NOSE_TIP - 1.0)[Fs].any(1)]
        return TIPMESH['V'], TIPMESH['F']

    def lay(x, y):
        Vs, Fs = tip_mesh()
        h = MS.hit_mesh(np.array([x, y, 40.0]), np.array([0.0, 0.0, -1.0]), Vs, Fs)
        return h if h is not None else np.array([x, y, S.NOSE_TIP])

    def lamp_corners(name, p):
        """the 3D corners in the trace's order (top-left, top-right, bottom-right, bottom-left as the photo shows
        them: the photos look at the nose from ahead, the train's right (x < 0) on the image's left)"""
        x0, x1, y0, y1, _ = S.LAMP_WIN
        if name in ('cam', 'cam_low'):
            cx, cy, w, h = S.CAM_WIN if name == 'cam' else S.CAM_LOW
            xs, ys = (cx - w / 2, cx + w / 2), (cy - h / 2, cy + h / 2)
        elif name == 'lamp_r':
            xs, ys = (-x1, -x0), (y0, y1)
        else:
            xs, ys = (x0, x1), (y0, y1)
        return [lay(xs[0], ys[1]), lay(xs[1], ys[1]), lay(xs[1], ys[0]), lay(xs[0], ys[0])]

    global TIP0
    TIP0 = S.REF_TIP
    if shape_in != '-' and os.path.exists(shape_in):
        sh = json.load(open(shape_in))
        if 'cap' not in sh:
            # an older fit with a pointed tip: start the cap from its section at df
            S.set_nose(sh.get('nose'), sh.get('body'), dict(df=0.0))
            S.CAP['df'] = float(opt('--df', '0.4'))
            sh = dict(sh, nose=capped(S.NOSE.table), cap=dict(S.CAP, yc=float(opt('--yc', '0.70')),
                                                               m=float(opt('--m', '3.0'))))
        S.load_shape(sh)
        TIP0 = 20.75
    base = capped(S.NOSE.table)
    for r in base[1:]:
        if r[0] <= 1.81 and opt('--bot'):
            r[KI['bot']] = min(r[KI['bot']], float(opt('--bot')))
    S.set_nose(base, S.BODY)
    FL = free_list(base)
    tipfree = '--tipfree' in a
    v_shape0 = shape_vec(base, FL, (S.CAP['yc'], S.CAP['m'], TIP0 - S.NOSE_TIP))
    smooth = float(opt('--smooth', '3'))
    nds = coarse_nose_ds()

    # per photo: the target and its sample pixels
    data = {}
    for p in photos:
        W, H = cams[p][7]
        M = cv2.imread(os.path.join(wd, 'masks', p + '.png'), cv2.IMREAD_GRAYSCALE)
        Ms = cv2.resize(M, (int(round(W * s)), int(round(H * s))), interpolation=cv2.INTER_NEAREST)
        car = (Ms == 255).astype(np.float32)
        dec = (Ms != 128).astype(np.float32)
        e = (car - cv2.erode(car, np.ones((3, 3), np.uint8))) > 0
        dt = cv2.distanceTransform((~e).astype(np.uint8), cv2.DIST_L2, 5)
        band = 6 * sigma + 30 * s
        samp = (dt <= band) & (dec > 0)
        samp[::2, :] = False
        samp[:, ::2] = False
        idx = np.nonzero(samp)
        d = dict(W=W, H=H, car=car, dec=dec, idx=idx)
        # weight: a 1 px shift of the mask's own outline
        c1 = 0.0
        for dx, dy in ((1, 0), (0, 1)):
            sh = np.roll(np.roll(car, dy, 0), dx, 1)
            r = cv2.GaussianBlur((sh - car) * dec, (0, 0), sigma)[idx]
            c1 += 0.5 * float(r @ r)
        d['w'] = math.sqrt(25 * 0.44 * 2 / max(c1, 1e-9))
        # points and lines
        pts = []
        for o, uv in A.get(p, {}).get('pts', {}).items():
            b, side = o.rsplit('_', 1)
            if b in BAD_PTS or b not in BA:
                continue
            q = np.array(BA[b], float)
            if side == 'r':
                q[0] = -q[0]
            elif side == 'c':
                q[0] = 0.0
            pts.append((q, np.array(uv, float)))
        d['pts'] = pts
        lines = []
        for o, uvs in A.get(p, {}).get('lines', {}).items():
            b, side = o.rsplit('_', 1)
            q = np.array(A['_points'][b], float)
            if side == 'r':
                q[0] = -q[0]
            ax = np.zeros(3)
            ax['xyz'.index(A['_lines'][b])] = 1.0
            lines.append((q, ax, np.array(uvs, float)))
        d['lines'] = lines
        # the lamp panel's traced corners (lamps.json) against our lamp windows' corners laid on the shell
        d['lamps'] = [(name, np.array(tr, float)) for name, tr in lamps[p].items()] if lamps and p in lamps else []
        data[p] = d

    def photo_res(p, cam, cars):
        d = data[p]
        m = raster(cam, d['W'], d['H'], cars, s).astype(np.float32)
        r = cv2.GaussianBlur((m - d['car']) * d['dec'], (0, 0), sigma)[d['idx']] * d['w']
        out = [r]
        sp = A.get(p, {}).get('sigma', 1.5)
        if d['pts']:
            Q = np.array([q for q, _ in d['pts']])
            U = np.array([uv for _, uv in d['pts']])
            pr = C.project(cam, Q, d['W'], d['H'])[:, :2]
            out.append(((pr - U) / sp).ravel())
        for name, tr in d['lamps']:
            Q = np.array(lamp_corners(name, p))
            pr = C.project(cam, Q, d['W'], d['H'])[:, :2]
            out.append(((pr - tr) / 1.0).ravel())
        for q, ax, uvs in d['lines']:
            pr = C.project(cam, np.array([q - 3 * ax, q + 3 * ax]), d['W'], d['H'])[:, :2]
            t = pr[1] - pr[0]
            t /= np.linalg.norm(t)
            nrm = np.array([-t[1], t[0]])
            out.append(((uvs - pr[0]) @ nrm) / sp)
        out.append(np.array([cam[5] / 0.15]))
        if 'f_exif' in A.get(p, {}):
            out.append(np.array([math.log(cam[6] / A[p]['f_exif']) / A[p].get('f_sig', 0.05)]))
        return np.concatenate(out)

    # smoothness of the nose table: second differences of each key along d
    ds = np.array([r[0] for r in base])

    def shape_prior(vs):
        t = table_from(vs, base, FL)
        r = []
        for k in KEYS:
            y = np.array([row[KI[k]] for row in t])
            wk = smooth * (4.0 if k == 'yw' else 1.0)
            for i in range(2, len(t) - 1):
                h0, h1 = ds[i] - ds[i - 1], ds[i + 1] - ds[i]
                curv = ((y[i + 1] - y[i]) / h1 - (y[i] - y[i - 1]) / h0) / (0.5 * (h0 + h1))
                # curvature allowed to be large at the tip, small along the long nose
                r.append(curv * min(max(ds[i], float(opt("--tipsmooth", "0.3"))), 4.0) * wk)
            if k in ('top', 'hw'):
                # the nose only grows towards the body
                r += [max(0.0, y[i] - y[i + 1]) / 0.01 for i in range(1, len(t) - 1)]
        r += list((vs - v_shape0) / 0.6)
        if not tipfree:
            r.append(vs[2] / 0.002)
        return np.array(r)

    ncam = 7
    cam_keys = photos if do_cams else []

    def pack(cs, vs):
        v = []
        for p in cam_keys:
            c = cs[p]
            v += list(c[:6]) + [math.log(c[6])]
        if do_shape:
            v += list(vs)
        return np.array(v, float)

    def unpack(v):
        cs = {}
        k = 0
        for p in photos:
            if p in cam_keys:
                cs[p] = list(v[k:k + 6]) + [math.exp(v[k + 6])]
                k += 7
            else:
                cs[p] = cams[p][:7]
        vs = v[k:] if do_shape else v_shape0
        return cs, vs

    def set_shape(vs):
        cap, tip = head_from(vs)
        S.set_nose(table_from(vs, base, FL), S.BODY, cap, tip)
        TIPMESH.clear()
        return train_rings(nds)

    def all_res(v, cars=None):
        cs, vs = unpack(v)
        if cars is None:
            cars = set_shape(vs)
        parts = {p: photo_res(p, cs[p], cars) for p in photos}
        return parts, (shape_prior(vs) if do_shape else np.zeros(0))

    def flat(parts, pr):
        return np.concatenate([parts[p] for p in photos] + [pr])

    # numeric-Jacobian steps per parameter
    eps = []
    for p in cam_keys:
        c = cams[p]
        dist = float(np.linalg.norm(np.array(c[:3]) - [0, 1.5, 8.0]))
        pe = 0.6 * dist / c[6]
        eps += [pe, pe, pe, 0.6 / c[6], 0.6 / c[6], 0.6 / c[6], 1.5e-3]
    if do_shape:
        eps += [0.008, 0.05, 0.008] + [0.008] * (len(v_shape0) - NHEAD)
    eps = np.array(eps)

    x = pack(cams, v_shape0)
    parts, pr = all_res(x)
    r = flat(parts, pr)
    cost = r @ r
    lam = 1e-2
    t0 = time.time()
    print(f'start cost {cost:.1f}  ' + '  '.join(f'{p} {parts[p] @ parts[p]:.1f}' for p in photos), flush=True)
    for it in range(steps):
        J = np.zeros((len(r), len(x)))
        # camera columns: only their photo's rows change
        cs, vs = unpack(x)
        cars = set_shape(vs)
        offs, o = {}, 0
        for p in photos:
            offs[p] = (o, o + len(parts[p]))
            o += len(parts[p])
        k = 0
        for p in cam_keys:
            for j in range(ncam):
                xk = x.copy()
                xk[k] += eps[k]
                c2, _ = unpack(xk)
                a0, a1 = offs[p]
                J[a0:a1, k] = (photo_res(p, c2[p], cars) - parts[p]) / eps[k]
                k += 1
        if do_shape:
            for j in range(len(v_shape0)):
                xk = x.copy()
                xk[k] += eps[k]
                pk, prk = all_res(xk)
                J[:, k] = (flat(pk, prk) - r) / eps[k]
                k += 1
        Ah = J.T @ J
        g = J.T @ r
        improved = False
        for _ in range(10):
            dx = -np.linalg.solve(Ah + lam * np.diag(np.diag(Ah) + 1e-9), g)
            x2 = x + dx
            p2, pr2 = all_res(x2)
            r2 = flat(p2, pr2)
            c2 = r2 @ r2
            if c2 < cost:
                x, r, cost, parts, pr = x2, r2, c2, p2, pr2
                lam = max(lam / 3, 1e-6)
                improved = True
                break
            lam *= 4
        print(f'it {it} cost {cost:.1f} lam {lam:.0e} ({time.time() - t0:.0f} s)  ' +
              '  '.join(f'{p} {parts[p] @ parts[p]:.1f}' for p in photos), flush=True)
        if not improved:
            break
    cs, vs = unpack(x)
    outc = json.load(open(cams_in))
    for p in photos:
        outc['cams'][p] = [round(float(q), 6) for q in cs[p]] + [cams[p][7]]
    json.dump(outc, open(prefix + '_cams.json', 'w'), indent=1)
    t = table_from(vs, base, FL)
    cap, tip = head_from(vs)
    cap = dict(S.CAP, **cap)
    json.dump({'nose': [[round(float(q), 4) for q in row] for row in t], 'body': S.BODY,
               'cap': {k: round(float(q), 4) for k, q in cap.items()}, 'tip': round(float(tip), 4)},
              open(prefix + '_shape.json', 'w'), indent=1)
    print('cap', cap, 'tip', round(tip, 4), 'set-back', round(TIP0 - tip, 4))
    for row in t:
        print('  (' + ', '.join(f'{q:.3f}' for q in row) + '),')


if __name__ == '__main__':
    main()
