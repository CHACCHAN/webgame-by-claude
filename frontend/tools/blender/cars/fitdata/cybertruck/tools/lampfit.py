"""
lampfit.py <lamps.json> <fit.json (params + cams + pose)> [--fit name,name,...] [--out res.json] [--crops dir,photodir]
Compares the lamps of the model with their outlines traced on the photos (lamps.json): each lamp outline of
cybertruck_parts.lamp_outlines is projected through the photo's solved camera (with the body pose) and set against the
tracing: IoU of the two areas and the distance between the outlines (both ways, sampled every 0.25 px): max and p95 in
px. --fit: least squares on the listed lamp parameters (vertex to traced vertex) before measuring; the result is
written into the params block of the fit json. --crops: photo crops with the tracing (green) and the model (red).
"""
import json, math, os, sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, '..', '..', '..')))
sys.dont_write_bytecode = True
import cybertruck_shape as CS  # noqa: E402
import cybertruck_parts as PT  # noqa: E402

a = sys.argv[1:]
L = json.load(open(a[0]))
FJ = a[1]
FIT = json.load(open(FJ))
P0 = CS.load(None)
P0.update(FIT.get('params', {}))


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
    Q = np.asarray(X, float) - np.array([x, y, z])
    zc = Q @ d
    return np.stack([W / 2 + f * (Q @ r) / zc, H / 2 - f * (Q @ u) / zc], axis=-1)


def posed(v, pose):
    dy, th = pose.get('dy', 0.0), math.radians(pose.get('pitch_deg', 0.0))
    c, s = math.cos(th), math.sin(th)
    v = np.asarray(v, float).copy()
    y, z = v[:, 1].copy(), v[:, 2].copy()
    v[:, 1] = c * y + s * z + dy
    v[:, 2] = -s * y + c * z
    return v


def model_uv(P, photo):
    S = CS.Shape(P)
    o = PT.lamp_outlines(P, S)
    cam, pose = FIT['cams'][photo], FIT['pose'].get(photo, {})
    return {k: project(cam, posed(v, pose)) for k, v in o.items()}


def pairs():
    for ph, d in L.items():
        if ph.startswith('_') or ph not in FIT['cams']:
            continue
        for k, v in d.items():
            if k != 'lit':
                yield ph, k, np.array(v, float)


def seg_dist(pts, poly):
    """distance from each point to the closed polyline"""
    best = np.full(len(pts), np.inf)
    for i in range(len(poly)):
        a, b = poly[i], poly[(i + 1) % len(poly)]
        ab = b - a
        t = np.clip(((pts - a) @ ab) / max(ab @ ab, 1e-12), 0, 1)
        d = np.linalg.norm(pts - (a + t[:, None] * ab), axis=1)
        best = np.minimum(best, d)
    return best


def sample(poly, step=0.25):
    out = []
    for i in range(len(poly)):
        a, b = poly[i], poly[(i + 1) % len(poly)]
        n = max(1, int(np.linalg.norm(b - a) / step))
        out.append(a + (b - a) * (np.arange(n)[:, None] / n))
    return np.concatenate(out)


def iou(p1, p2, ss=8):
    import cv2
    lo = np.floor(np.minimum(p1.min(0), p2.min(0))) - 2
    hi = np.ceil(np.maximum(p1.max(0), p2.max(0))) + 2
    W, H = (hi - lo) * ss
    m1 = np.zeros((int(H), int(W)), np.uint8); m2 = m1.copy()
    cv2.fillPoly(m1, [np.round((p1 - lo) * ss).astype(np.int32)], 1)
    cv2.fillPoly(m2, [np.round((p2 - lo) * ss).astype(np.int32)], 1)
    return float((m1 & m2).sum() / max((m1 | m2).sum(), 1))


def measure(P):
    res = {}
    cache = {}
    for ph, k, tr in pairs():
        if ph not in cache:
            cache[ph] = model_uv(P, ph)
        md = cache[ph][k]
        d = np.concatenate([seg_dist(sample(md), tr), seg_dist(sample(tr), md)])
        res[(ph, k)] = {'iou': round(iou(md, tr), 3), 'max': round(float(d.max()), 2), 'p95': round(float(np.percentile(d, 95)), 2),
                        'vtx': round(float(np.sqrt(((md - tr) ** 2).sum(1).mean())), 2)}
    return res


if '--fit' in a:
    names = a[a.index('--fit') + 1].split(',')
    x0 = np.array([P0[n] for n in names])

    def resid(x):
        P = dict(P0)
        P.update(dict(zip(names, x)))
        r = []
        cache = {}
        for ph, k, tr in pairs():
            if ph not in cache:
                cache[ph] = model_uv(P, ph)
            r.append((cache[ph][k] - tr).ravel())
        r.append((x - x0) / 0.5)
        return np.concatenate(r)
    x = x0.copy(); r = resid(x); lam = 1e-3
    for it in range(50):
        J = np.zeros((len(r), len(x)))
        for j in range(len(x)):
            h = 1e-5; xp = x.copy(); xp[j] += h; xm = x.copy(); xm[j] -= h
            J[:, j] = (resid(xp) - resid(xm)) / (2 * h)
        g = J.T @ r; Hm = J.T @ J
        dx = -np.linalg.solve(Hm + lam * np.diag(np.diag(Hm) + 1e-9), g)
        rn = resid(x + dx)
        if rn @ rn < r @ r:
            x, r, lam = x + dx, rn, lam * 0.3
        else:
            lam *= 10
        if np.abs(dx).max() < 1e-6:
            break
    for n, v in zip(names, x):
        print(f'  {n:8s} {P0[n]:7.4f} -> {v:7.4f}')
        P0[n] = float(v)
        FIT.setdefault('params', {})[n] = round(float(v), 4)
    json.dump(FIT, open(FJ, 'w'), indent=1)

R = measure(P0)
print(f'{"photo":6s} {"lamp":8s} {"IoU":>6s} {"max":>6s} {"p95":>6s} {"vtx":>6s}  (px at 1280)')
for (ph, k), v in R.items():
    print(f'{ph:6s} {k:8s} {v["iou"]:6.3f} {v["max"]:6.2f} {v["p95"]:6.2f} {v["vtx"]:6.2f}')
if '--out' in a:
    json.dump({f'{ph}/{k}': v for (ph, k), v in R.items()}, open(a[a.index('--out') + 1], 'w'), indent=1)
if '--crops' in a:
    from PIL import Image, ImageDraw
    cdir, phdir = a[a.index('--crops') + 1].split(',')
    os.makedirs(cdir, exist_ok=True)
    for ph in {p for p, _, _ in pairs()}:
        md = model_uv(P0, ph)
        im = Image.open(os.path.join(phdir, ph + '.jpg')).convert('RGB')
        S = 3
        tr = {k: np.array(v, float) for k, v in L[ph].items() if k != 'lit'}
        allp = np.concatenate(list(tr.values()) + [md[k] for k in tr])
        lo = np.maximum(allp.min(0) - 25, 0); hi = np.minimum(allp.max(0) + 25, im.size)
        c = im.crop((int(lo[0]), int(lo[1]), int(hi[0]), int(hi[1]))).resize((int(hi[0] - lo[0]) * S, int(hi[1] - lo[1]) * S), Image.LANCZOS)
        d = ImageDraw.Draw(c)
        for k, t in tr.items():
            d.polygon([tuple((p - lo) * S) for p in t], outline=(0, 255, 0))
            d.polygon([tuple((p - lo) * S) for p in md[k]], outline=(255, 40, 40))
        c.save(os.path.join(cdir, f'{ph}_lamps.png'))
