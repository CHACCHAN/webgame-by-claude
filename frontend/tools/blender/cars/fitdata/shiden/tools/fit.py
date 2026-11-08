"""
fit.py <fit.json> <state_in.json|-> <state_out.json> [--iters N] [--nocam] [--noffd] [--photos a,b] [--wtot 500]
       [--ls 2000] [--l0 50] [--rev 0.5] [--huber 1.0]
Joint fit of the body FFD lattice (last lattice in fit.json; earlier ones are fixed), the photo cameras, the body pose
per car group and the rims, to the photo silhouettes (masks: 255 car / 0 not / 128 ignore) and detected rim edges.
Residuals in % of the car's bbox width in each photo. Damped Gauss-Newton (LM) with Huber weights.
"""
import json
import math
import os
import sys
import time

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cv2
import numpy as np

import fitlib as F

argv = sys.argv[1:]
cfg = json.load(open(argv[0]))
state_in, state_out = argv[1], argv[2]


def opt(k, d):
    return type(d)(argv[argv.index(k) + 1]) if k in argv else d


ITERS = opt('--iters', 8)
NOCAM = '--nocam' in argv
NOFFD = '--noffd' in argv
NOPOSE = '--nopose' in argv
WTOT = opt('--wtot', 500.0)
LS = opt('--ls', 2000.0)
L0 = opt('--l0', 50.0)
REV = opt('--rev', 0.5)
HUB = opt('--huber', 1.0)
WRIM = opt('--wrim', 400.0)
only = opt('--photos', '')
names = [n for n in cfg['photos'] if not only or n in only.split(',')]
base = os.path.dirname(os.path.abspath(argv[0]))

# ---------------------------------------------------------------- data
mesh = np.load(cfg['mesh'])
Vb0 = mesh['body_v']; Tb = mesh['body_t']
lats = [F.Lattice.from_json(l) if 'D' in l else F.Lattice(l['lo'], l['hi'], l['seg']) for l in cfg['lattices']]
for L in lats[:-1]:
    Vb0 = L.apply(Vb0)
LAT = lats[-1]
widx, ww = LAT.weights(Vb0)
wheels = {w: (mesh[f'{w}_v'], mesh[f'{w}_t']) for w in F.WHEELS}
Eb, EFb = F.edges_of(Tb)
Ew = {w: F.edges_of(wheels[w][1]) for w in wheels}
rims = json.load(open(cfg['rims'])) if cfg.get('rims') else {}

photos = {}
for n in names:
    pc = cfg['photos'][n]
    m = cv2.imread(os.path.join(base, pc['mask']), cv2.IMREAD_GRAYSCALE)
    P = m > 192
    ign = (m > 64) & (m <= 192)
    S, gx, gy = F.sdf(P)
    ys, xs = np.nonzero(P)
    photos[n] = {'P': P, 'ign': ign.astype(np.float32), 'S': S, 'gx': gx, 'gy': gy, 'W': m.shape[1], 'H': m.shape[0],
                 'scale': 100.0 / (xs.max() - xs.min() + 1), 'group': pc['group'], 'fprior': pc.get('f'), 'fsig': pc.get('fsig', cfg.get('fsig', 0.03)),
                 'Pout': F.outline(P) & ~ign}

# ---------------------------------------------------------------- state / parameter vector
st = json.load(open(state_in)) if state_in != '-' else {}
cams = {n: np.array(st.get('cams', {}).get(n, json.load(open(cfg['cams']))['cams'][n])[:7], float) for n in names}
for n in names:
    cams[n][6] = math.log(cams[n][6])
groups = sorted({photos[n]['group'] for n in names})
ref = cfg.get('ref_group')
pose = {g: np.array(st.get('pose', {}).get(g, [0.0, 0.0]), float) for g in groups}
rimp = {g: np.array(st.get('rim', {}).get(g, cfg.get('rim0', [0.228, 0.09])), float) for g in groups}
steer = {n: float(st.get('steer', {}).get(n, 0.0)) for n in names}
if 'D' in st and not NOFFD:
    LAT.D = np.array(st['D'], float)
elif 'D' in st:
    LAT.D = np.array(st['D'], float)
rim_groups = [g for g in groups if any(n in rims and rims[n] and photos[n]['group'] == g for n in names)]
pose_groups = [g for g in groups if g != ref and not NOPOSE and g in rim_groups]
steer_photos = [n for n in names if n in rims and any(w in ('fl', 'fr') for w in rims[n])]

layout = []
if not NOFFD:
    layout.append(('ffd', None, LAT.nfree))
if not NOCAM:
    for n in names:
        layout.append(('cam', n, 7))
for g in pose_groups:
    layout.append(('pose', g, 2))
for g in rim_groups:
    layout.append(('rim', g, 2))
for n in steer_photos:
    layout.append(('steer', n, 1))
offs = {}
o = 0
for kind, key, k in layout:
    offs[(kind, key)] = (o, k)
    o += k
NP = o
print('params', NP, {k: v for k, v in offs.items() if k[0] != 'cam'} if NP < 2000 else '', flush=True)


def get_vec():
    v = np.zeros(NP)
    for (kind, key), (a, k) in offs.items():
        if kind == 'ffd':
            v[a:a + k] = LAT.get_free()
        elif kind == 'cam':
            v[a:a + k] = cams[key]
        elif kind == 'pose':
            v[a:a + k] = pose[key]
        elif kind == 'rim':
            v[a:a + k] = rimp[key]
        elif kind == 'steer':
            v[a] = steer[key]
    return v


def set_vec(v):
    for (kind, key), (a, k) in offs.items():
        if kind == 'ffd':
            LAT.set_free(v[a:a + k])
        elif kind == 'cam':
            cams[key] = v[a:a + k].copy()
        elif kind == 'pose':
            pose[key] = v[a:a + k].copy()
        elif kind == 'rim':
            rimp[key] = v[a:a + k].copy()
        elif kind == 'steer':
            steer[key] = float(v[a])


def camf(n, c=None):
    c = cams[n] if c is None else c
    return [*c[:6], math.exp(c[6])]


def steered(w, V, s):
    if w not in ('fl', 'fr') or s == 0.0:
        return V
    side, zc = F.WHEELS[w]
    c0 = np.array([side * F.TRACK / 2, F.WHEEL_Y, zc])
    ca, sa = math.cos(s), math.sin(s)
    d = V - c0
    return c0 + np.stack([d[:, 0] * ca + d[:, 2] * sa, d[:, 1], -d[:, 0] * sa + d[:, 2] * ca], 1)


# ---------------------------------------------------------------- residuals for one photo

def photo_terms(n, Vdef, jac):
    ph = photos[n]; W, H = ph['W'], ph['H']
    cam = camf(n)
    g = ph['group']
    dy, pt = pose.get(g, (0.0, 0.0))
    Vp = F.pose_apply(Vdef, dy, pt)
    meshes = [('body', Vp, Tb, (Eb, EFb))]
    for w, (V, T) in wheels.items():
        meshes.append((w, steered(w, V, steer.get(n, 0.0)), T, Ew[w]))
    M = np.zeros((H, W), np.uint8)
    uvs = {}
    for name, V, T, E in meshes:
        uv, z = F.project(cam, V, W, H)
        uvs[name] = uv
        F.raster(uv, T, W, H, M)
    O = F.outline(M)
    dO = cv2.distanceTransform((~O).astype(np.uint8), cv2.DIST_L2, 3)
    samples = []                         # (mesh, vi, vj, t, uv)
    for name, V, T, (E, EF) in meshes:
        uv = uvs[name]
        a = uv[T[:, 1]] - uv[T[:, 0]]; b = uv[T[:, 2]] - uv[T[:, 0]]
        face = (a[:, 0] * b[:, 1] - a[:, 1] * b[:, 0]) > 0
        f0 = face[EF[:, 0]]
        f1 = np.where(EF[:, 1] >= 0, face[np.maximum(EF[:, 1], 0)], ~f0)
        cand = E[f0 != f1]
        for t in (0.0, 0.33, 0.67):
            p = uv[cand[:, 0]] * (1 - t) + uv[cand[:, 1]] * t
            ok = (p[:, 0] > 1) & (p[:, 0] < W - 2) & (p[:, 1] > 1) & (p[:, 1] < H - 2)
            idx = np.nonzero(ok)[0]
            d = F.bilinear(dO, p[idx])
            keep = idx[d < 1.0]
            samples.append((name, cand[keep, 0], cand[keep, 1], np.full(len(keep), t), p[keep]))
    # bin: one sample per pixel
    allp = np.concatenate([s[4] for s in samples])
    key = np.floor(allp).astype(int)
    k1 = key[:, 1] * W + key[:, 0]
    _, first = np.unique(k1, return_index=True)
    sel = np.zeros(len(allp), bool); sel[first] = True
    rows = []
    r_all = []
    jrows = []
    off = 0
    for name, vi, vj, tt, p in samples:
        s = sel[off:off + len(p)]; off += len(p)
        if not s.any():
            continue
        vi, vj, tt, p = vi[s], vj[s], tt[s], p[s]
        ig = F.bilinear(ph['ign'], p)
        k = ig < 0.25
        if name == 'body':
            yv = Vdef[vi, 1] * (1 - tt) + Vdef[vj, 1] * tt
            k &= yv > YMIN
        vi, vj, tt, p = vi[k], vj[k], tt[k], p[k]
        if len(p) == 0:
            continue
        r = F.bilinear(ph['S'], p) * ph['scale']
        gg = np.stack([F.bilinear(ph['gx'], p), F.bilinear(ph['gy'], p)], 1)
        gg /= np.linalg.norm(gg, axis=1, keepdims=True) + 1e-9
        rows.append((name, vi, vj, tt, p, r, gg))
    # reverse term: photo outline → nearest model sample
    allr = []
    if rows:
        P_all = np.concatenate([x[4] for x in rows])
        lab = np.zeros((H, W), np.int32)
        ki = np.clip(np.floor(P_all).astype(int), [0, 0], [W - 1, H - 1])
        lab[ki[:, 1], ki[:, 0]] = np.arange(1, len(P_all) + 1)
        src = (lab == 0).astype(np.uint8)
        dist, lbl = cv2.distanceTransformWithLabels(src, cv2.DIST_L2, 5, labelType=cv2.DIST_LABEL_PIXEL)
        # map label → sample index
        lab_of = np.zeros(lbl.max() + 1, np.int64)
        lab_of[lbl[ki[:, 1], ki[:, 0]]] = np.arange(len(P_all))
        qy, qx = np.nonzero(ph['Pout'])
        if len(qx) > 4000:
            st_ = len(qx) // 4000 + 1
            qx, qy = qx[::st_], qy[::st_]
        si = lab_of[lbl[qy, qx]]
        q = np.stack([qx, qy], 1).astype(float) + 0.5
        nq = np.stack([ph['gx'][qy, qx], ph['gy'][qy, qx]], 1)
        nq /= np.linalg.norm(nq, axis=1, keepdims=True) + 1e-9
        rr = ((P_all[si] - q) * nq).sum(1) * ph['scale']
        far = np.linalg.norm(P_all[si] - q, axis=1) * ph['scale'] < 6.0
        allr = (si[far], rr[far], nq[far])
    out = {'rows': rows, 'rev': allr, 'M': M}
    if not jac:
        return out
    return out


def sample_points(n, rows, Vdef):
    """3D points (posed) of the samples, and their undeformed positions for the FFD weights"""
    g = photos[n]['group']
    dy, pt = pose.get(g, (0.0, 0.0))
    X = []; U = []; kind = []
    for name, vi, vj, tt, p, r, gg in rows:
        if name == 'body':
            a = Vdef[vi] * (1 - tt)[:, None] + Vdef[vj] * tt[:, None]
            X.append(F.pose_apply(a, dy, pt))
            U.append(np.stack([vi, vj], 1)); kind += ['body'] * len(vi)
        else:
            V = steered(name, wheels[name][0], steer.get(n, 0.0))
            X.append(V[vi] * (1 - tt)[:, None] + V[vj] * tt[:, None])
            U.append(np.stack([vi, vj], 1)); kind += [name] * len(vi)
    return np.concatenate(X), np.concatenate(U), np.array(kind), np.concatenate([np.repeat(r[5], 1) for r in rows])


def huber_w(r, d):
    a = np.abs(r)
    return np.where(a <= d, 1.0, np.sqrt(d / np.maximum(a, 1e-12)))


def rim_res(n, c=None, rp=None, s=None):
    """signed px distances of detected rim points to the projected rim circles (+ = outside)"""
    ph = photos[n]; W, H = ph['W'], ph['H']
    cam = camf(n, c)
    rp = rimp[ph['group']] if rp is None else rp
    s = steer.get(n, 0.0) if s is None else s
    out = []
    for w, d in rims.get(n, {}).items():
        side, zc = F.WHEELS[w]
        circ = F.rim_circle(side, zc, rp[0], rp[1], s if w in ('fl', 'fr') else 0.0)
        uv, z = F.project(cam, circ, W, H)
        poly = uv.astype(np.float32).reshape(-1, 1, 2)
        Q = np.array(d['pts'], float)
        sd = np.array([-cv2.pointPolygonTest(poly, (float(x), float(y)), True) for x, y in Q])
        out.append(sd)
    return np.concatenate(out) if out else np.zeros(0)


# ---------------------------------------------------------------- cost / normal equations

Lreg = LAT.reg()
Rmat = None
if not NOFFD:
    LS_ = Lreg @ LAT.S
    Rmat = LS * (LS_.T @ LS_) + L0 * (LAT.S.T @ LAT.S)


def deformed():
    return Vb0 + np.einsum('nk,nkc->nc', ww, LAT.D[widx])


def priors(v, jac=False):
    """prior residuals (dimensionless) and their Jacobian rows"""
    res = []; J = []
    def add(i, val, sig):
        res.append(val / sig)
        if jac:
            row = np.zeros(NP); row[i] = 1.0 / sig; J.append(row)
    for (kind, key), (a, k) in offs.items():
        if kind == 'cam' and photos[key]['fprior']:
            add(a + 6, v[a + 6] - math.log(photos[key]['fprior']), photos[key]['fsig'])
        if kind == 'pose':
            add(a, v[a], cfg.get('pose_sig', [0.01, 0.005])[0]); add(a + 1, v[a + 1], cfg.get('pose_sig', [0.01, 0.005])[1])
        if kind == 'rim':
            rp0 = cfg.get('rim_prior', {}).get(key, [0.23, 0.003, 0.09, 0.015]); add(a, v[a] - rp0[0], rp0[1]); add(a + 1, v[a + 1] - rp0[2], rp0[3])
        if kind == 'steer':
            add(a, v[a], 0.3)
    return np.array(res), (np.array(J) if jac else None)


ACC = opt('--acc', 'xor')
YMIN = opt('--ymin', 0.15)
iou_ = {}


def evaluate(jac):
    """total cost; with jac also JtJ, Jtr; per-photo stats"""
    v = get_vec()
    Vdef = deformed()
    cost = 0.0
    iou_.clear()
    stats = {}
    if jac:
        A = np.zeros((NP, NP)); bvec = np.zeros(NP)
    for n in names:
        ph = photos[n]
        T = photo_terms(n, Vdef, jac)
        rows = T['rows']
        if not rows:
            continue
        X, U, kind, _ = sample_points(n, rows, Vdef)
        r = np.concatenate([x[5] for x in rows])
        gg = np.concatenate([x[6] for x in rows])
        nf = len(r)
        wph = math.sqrt(WTOT / max(nf, 1))
        hw = huber_w(r, HUB)
        rev_si, rev_r, rev_n = T['rev'] if T['rev'] else (np.zeros(0, int), np.zeros(0), np.zeros((0, 2)))
        wrev = math.sqrt(WTOT * REV / max(len(rev_r), 1))
        hwr = huber_w(rev_r, HUB)
        rr = rim_res(n) * ph['scale']
        wr = math.sqrt(WRIM * len(rims.get(n, {})) / max(len(rr), 1))
        hwm = huber_w(rr, HUB)
        c_sil = float(((wph * hw * r) ** 2).sum()); c_rev = float(((wrev * hwr * rev_r) ** 2).sum())
        c_rim = float(((wr * hwm * rr) ** 2).sum())
        if ACC == 'xor':
            valid = ph['ign'] < 0.5
            xor = ((T['M'] > 0) ^ ph['P']) & valid
            xf = xor.sum() * (ph['scale'] / 100.0) ** 2
            inter = ((T['M'] > 0) & ph['P'] & valid).sum(); uni = (((T['M'] > 0) | ph['P']) & valid).sum()
            cost += WTOT * (xf / 0.03) ** 2 + c_rim
            iou_[n] = inter / max(uni, 1)
        else:
            cost += c_sil + c_rev + c_rim
        stats[n] = (np.sqrt((r ** 2).mean()), np.sqrt((rev_r ** 2).mean()) if len(rev_r) else 0, np.sqrt((rr ** 2).mean()) if len(rr) else 0, nf)
        if not jac:
            continue
        # Jacobian of the forward residuals: dr/dX (posed) = scale * g . dp/dX
        cam = camf(n)
        Jp = F.proj_jac(cam, X, ph['W'], ph['H'])
        drdX = ph['scale'] * np.einsum('ni,nij->nj', gg, Jp)          # (N,3)
        Jrows = np.zeros((nf, NP))
        g = ph['group']
        dy, pt = pose.get(g, (0.0, 0.0))
        isb = kind == 'body'
        if not NOFFD and isb.any():
            # dXposed/dV = R(pitch); V = Vb0 + sum w D
            c_, s_ = math.cos(pt), math.sin(pt)
            R = np.array([[1, 0, 0], [0, c_, -s_], [0, s_, c_]])
            dV = drdX[isb] @ R                                          # (Nb,3)
            ub = U[isb]
            tt = np.concatenate([x[3] for x in rows])[isb]
            a0, k0 = offs[('ffd', None)]
            Jfull = np.zeros((isb.sum(), LAT.ncp * 3), np.float64)
            rowi = np.arange(isb.sum())
            for end, wt in ((0, 1 - tt), (1, tt)):
                vid = ub[:, end]
                for kk in range(64):
                    cp = widx[vid, kk]; wk = ww[vid, kk] * wt
                    for cc in range(3):
                        np.add.at(Jfull, (rowi, cp * 3 + cc), wk * dV[:, cc])
            Jrows[np.nonzero(isb)[0], a0:a0 + k0] = Jfull @ LAT.S
        # numeric: camera, pose, steer
        def reproj(c=None, ps=None, s=None):
            cc = camf(n, c)
            Xs = X.copy()
            if ps is not None and isb.any():
                Vd = np.concatenate([Vdef_samples])
                Xs[isb] = F.pose_apply(Vd, ps[0], ps[1])
            if s is not None:
                for w in ('fl', 'fr'):
                    m = kind == w
                    if m.any():
                        side, zc = F.WHEELS[w]
                        Xs[m] = steered(w, steered(w, X[m], -steer.get(n, 0.0)), s)
            uv, _ = F.project(cc, Xs, ph['W'], ph['H'])
            return uv
        Vdef_samples = None
        if isb.any():
            # unposed deformed sample points
            dy_, pt_ = dy, pt
            c_, s_ = math.cos(-pt_), math.sin(-pt_)
            Xb = X[isb].copy(); Xb[:, 1] -= dy_
            y = Xb[:, 1] * c_ - Xb[:, 2] * s_; z = Xb[:, 1] * s_ + Xb[:, 2] * c_
            Vdef_samples = np.stack([Xb[:, 0], y, z], 1)
        uv0 = reproj()
        if not NOCAM:
            a0, _ = offs[('cam', n)]
            for k, h in enumerate((1e-3, 1e-3, 1e-3, 1e-4, 1e-4, 1e-4, 1e-4)):
                c2 = cams[n].copy(); c2[k] += h
                d = (reproj(c=c2) - uv0) / h
                Jrows[:, a0 + k] = ph['scale'] * (gg * d).sum(1)
        if ('pose', g) in offs:
            a0, _ = offs[('pose', g)]
            for k, h in enumerate((1e-3, 1e-4)):
                ps = np.array([dy, pt]); ps[k] += h
                d = (reproj(ps=ps) - uv0) / h
                Jrows[:, a0 + k] = ph['scale'] * (gg * d).sum(1)
        if ('steer', n) in offs:
            a0, _ = offs[('steer', n)]
            h = 1e-4
            d = (reproj(s=steer[n] + h) - uv0) / h
            Jrows[:, a0] = ph['scale'] * (gg * d).sum(1)
        W1 = (wph * hw)[:, None]
        Jw = Jrows * W1
        A += Jw.T @ Jw; bvec += Jw.T @ (wph * hw * r)
        # reverse rows: r = n_q . (p_s - q): dr/dθ = n_q . dp_s/dθ  → reuse forward rows with g replaced by n_q
        if len(rev_r):
            # forward row for sample s is scale*g_s.dp_s/dθ; we need scale*n_q.dp_s/dθ: rebuild via the 2-vector
            # derivatives d(uv)/dθ = Jrows_uv; approximate n_q ≈ g_s (both are outline normals of nearby outlines)
            sgn = np.sign((rev_n * gg[rev_si]).sum(1))
            Jr = Jrows[rev_si] * sgn[:, None] * (wrev * hwr)[:, None]
            A += Jr.T @ Jr; bvec += Jr.T @ (wrev * hwr * rev_r)
        # rims
        if len(rr):
            Jm = np.zeros((len(rr), NP))
            base_r = rr
            if not NOCAM:
                a0, _ = offs[('cam', n)]
                for k, h in enumerate((1e-3, 1e-3, 1e-3, 1e-4, 1e-4, 1e-4, 1e-4)):
                    c2 = cams[n].copy(); c2[k] += h
                    Jm[:, a0 + k] = (rim_res(n, c=c2) * ph['scale'] - base_r) / h
            if ('rim', g) in offs:
                a0, _ = offs[('rim', g)]
                for k, h in enumerate((1e-4, 1e-4)):
                    rp = rimp[g].copy(); rp[k] += h
                    Jm[:, a0 + k] = (rim_res(n, rp=rp) * ph['scale'] - base_r) / h
            if ('steer', n) in offs:
                a0, _ = offs[('steer', n)]
                Jm[:, a0] = (rim_res(n, s=steer[n] + 1e-4) * ph['scale'] - base_r) / 1e-4
            Jmw = Jm * (wr * hwm)[:, None]
            A += Jmw.T @ Jmw; bvec += Jmw.T @ (wr * hwm * rr)
    pr, Jpr = priors(v, jac)
    cost += float((pr ** 2).sum())
    if Rmat is not None:
        a0, k0 = offs[('ffd', None)]
        p = v[a0:a0 + k0]
        cost += float(p @ Rmat @ p)
    if not jac:
        return cost, stats
    if len(pr):
        A += Jpr.T @ Jpr; bvec += Jpr.T @ pr
    if Rmat is not None:
        a0, k0 = offs[('ffd', None)]
        A[a0:a0 + k0, a0:a0 + k0] += Rmat
        bvec[a0:a0 + k0] += Rmat @ v[a0:a0 + k0]
    return cost, stats, A, bvec


def save(path):
    out = {'cams': {n: [*camf(n), photos[n]['W'] and [photos[n]['W'], photos[n]['H']]] for n in names},
           'pose': {g: pose[g].tolist() for g in groups}, 'rim': {g: rimp[g].tolist() for g in groups},
           'steer': steer, 'D': np.round(LAT.D, 6).tolist()}
    old = json.load(open(state_out)) if os.path.exists(state_out) else {}
    for k in ('cams', 'pose', 'rim', 'steer'):
        merged = old.get(k, {}); merged.update(out[k]); out[k] = merged
    json.dump(out, open(path, 'w'), indent=0)


def show(stats, cost, tag):
    print(f'{tag} cost {cost:.2f}  ' + '  '.join(f'{n}:{s[0]:.2f}/{s[1]:.2f}/{s[2]:.2f}/{iou_.get(n, 0):.3f}' for n, s in stats.items()),
          flush=True)


mu = 1e-3
t0 = time.time()
cost, stats, A, b = evaluate(True)
if '--check2' in argv:
    n = names[0]; ph = photos[n]
    Vdef = deformed(); T = photo_terms(n, Vdef, True); rows = T['rows']
    X, U, kind, _ = sample_points(n, rows, Vdef)
    r0 = np.concatenate([x[5] for x in rows]); gg = np.concatenate([x[6] for x in rows])
    for k, h in enumerate((1e-3, 1e-3, 1e-3, 1e-4, 1e-4, 1e-4, 1e-4)):
        c2 = cams[n].copy(); c2[k] += 10 * h
        uv1, _ = F.project(camf(n, c2), X, ph['W'], ph['H']); uv0, _ = F.project(camf(n), X, ph['W'], ph['H'])
        r1 = F.bilinear(ph['S'], uv1) * ph['scale']; r00 = F.bilinear(ph['S'], uv0) * ph['scale']
        lin = ph['scale'] * (gg * (uv1 - uv0)).sum(1)
        ok = np.abs(r00) < 3
        print('cam', k, 'mean act', round(float((r1 - r00)[ok].mean()), 4), 'mean lin', round(float(lin[ok].mean()), 4), 'corr', round(float(np.corrcoef((r1 - r00)[ok], lin[ok])[0, 1]), 3), 'r0 vs r00', round(float(np.abs(r0 - r00).max()), 4))
    sys.exit()
if '--check' in argv:
    v0 = get_vec()
    rng = np.random.default_rng(1)
    a0, k0 = offs.get(('ffd', None), (0, 0))
    idx = list(rng.choice(np.arange(a0, a0 + k0), 6, replace=False)) if k0 else []
    idx += [offs[('cam', names[0])][0] + k for k in (0, 3, 6)] if ('cam', names[0]) in offs else []
    for i in idx:
        h = 4e-3 if i < a0 + k0 else 3e-3
        v = v0.copy(); v[i] += h; set_vec(v); cp, _ = evaluate(False)
        v = v0.copy(); v[i] -= h; set_vec(v); cm, _ = evaluate(False)
        set_vec(v0)
        print('check', i, 'num', round((cp - cm) / (2 * h), 2), 'lin', round(2 * b[i], 2), 'A_ii', round(A[i, i], 1))
    sys.exit()
show(stats, cost, 'it0')
for it in range(ITERS):
    v = get_vec()
    dA = np.diag(A).copy()
    dA[dA < 1e-9] = 1e-9
    accepted = False
    for tries in range(6):
        try:
            step = np.linalg.solve(A + mu * np.diag(dA) + 1e-9 * np.eye(NP), -b)
        except np.linalg.LinAlgError:
            mu *= 10; continue
        set_vec(v + step)
        c2, s2 = evaluate(False)
        if c2 < cost:
            mu = max(mu / 3, 1e-6)
            accepted = True
            break
        mu *= 5
        set_vec(v)
    if not accepted:
        print('no improvement; stop'); break
    cost, stats, A, b = evaluate(True)
    show(stats, cost, f'it{it + 1} mu={mu:.0e} t={time.time() - t0:.0f}s')
    save(state_out)
save(state_out)
print('pose', {g: np.round(pose[g], 4).tolist() for g in groups}, 'rim', {g: np.round(rimp[g], 4).tolist() for g in groups},
      'steer', {n: round(s, 3) for n, s in steer.items() if s})
Dn = np.linalg.norm(LAT.D, axis=1)
print('lattice max |D|', round(float(Dn.max()), 4), 'mean', round(float(Dn.mean()), 4))
