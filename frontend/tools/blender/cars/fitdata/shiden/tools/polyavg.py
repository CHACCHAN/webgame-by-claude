"""polyavg.py: a consensus outline from several back-projected outlines in a 2D design frame (w, v): radius about a
centre per angle, averaged over the sources valid at that angle (weights), smoothed; prints and writes the outline.

  py polyavg.py <frame.json: {name: [[w, v] | null]}> <out.json> --centre w,v --src name:weight[:w0,w1,v0,v1 valid box]...
      [--step 6] [--smooth 2] [--plot out.png --box w0,w1,v0,v1 --cur cur.json]
"""
import json, math, sys
import numpy as np
a = sys.argv[1:]
src = json.load(open(a[0]))
def opt(k, d=None):
    return a[a.index(k) + 1] if k in a else d
cx, cy = (float(v) for v in opt('--centre').split(','))
step = float(opt('--step', '6'))
angs = np.radians(np.arange(0, 360, step))
specs = [a[i + 1] for i, t in enumerate(a) if t == '--src']


def radius(poly, th):
    """distance from the centre to the polygon along the ray at angle th (max of intersections)"""
    d = np.array([math.cos(th), math.sin(th)])
    best = None
    n = len(poly)
    for i in range(n):
        p, q = poly[i], poly[(i + 1) % n]
        e = q - p
        M = np.array([[d[0], -e[0]], [d[1], -e[1]]])
        if abs(np.linalg.det(M)) < 1e-12:
            continue
        t, s = np.linalg.solve(M, p - np.array([cx, cy]))
        if t > 0 and 0 <= s <= 1:
            best = t if best is None else max(best, t)
    return best


acc = np.zeros(len(angs)); wsum = np.zeros(len(angs))
per = {}
for s in specs:
    parts = s.split(':')
    name, w = parts[0], float(parts[1])
    boxes = [tuple(float(v) for v in b.split(',')) for b in parts[2:]]
    poly = np.array([p for p in src[name] if p is not None], float)
    rs = []
    for k, th in enumerate(angs):
        r = radius(poly, th)
        if r is None:
            rs.append(None); continue
        pt = (cx + r * math.cos(th), cy + r * math.sin(th))
        ok = (not boxes) or any(b[0] <= pt[0] <= b[1] and b[2] <= pt[1] <= b[3] for b in boxes)
        rs.append(r if ok else None)
        if ok:
            acc[k] += w * r; wsum[k] += w
    per[name] = rs
r = np.where(wsum > 0, acc / np.maximum(wsum, 1e-9), np.nan)
# fill gaps by circular interpolation, then smooth
idx = np.arange(len(r)); good = ~np.isnan(r)
r = np.interp(idx, np.r_[idx[good] - len(r), idx[good], idx[good] + len(r)], np.r_[r[good], r[good], r[good]])
k = int(opt('--smooth', '1'))
for _ in range(k):
    r = (np.roll(r, 1) + 2 * r + np.roll(r, -1)) / 4
out = [[round(cx + rr * math.cos(t), 4), round(cy + rr * math.sin(t), 4)] for rr, t in zip(r, angs)]
json.dump({'outline': out, 'missing_deg': [round(math.degrees(t)) for t, g in zip(angs, good) if not g]}, open(a[1], 'w'))
print('outline', len(out), 'pts; no source at', [round(math.degrees(t)) for t, g in zip(angs, good) if not g])
if '--plot' in a:
    from PIL import Image, ImageDraw
    w0, w1, v0, v1 = (float(v) for v in opt('--box').split(','))
    S = 2000
    img = Image.new('RGB', (int((w1 - w0) * S), int((v1 - v0) * S)), 'white'); dr = ImageDraw.Draw(img)
    X = lambda w, v: ((w - w0) * S, (v1 - v) * S)
    for g in np.arange(-0.4, 0.45, 0.05):
        dr.line([X(g, v0), X(g, v1)], fill=(225, 225, 225)); dr.line([X(w0, g), X(w1, g)], fill=(225, 225, 225))
        dr.text(X(g, v0 + 0.01), f'{g:+.2f}', fill=(120, 120, 120)); dr.text(X(w0 + 0.005, g), f'{g:+.2f}', fill=(120, 120, 120))
    if opt('--cur'):
        cur = json.load(open(opt('--cur')))
        dr.line([X(*p) for p in cur] + [X(*cur[0])], fill=(255, 0, 255), width=2)
    cols = [(0, 160, 0), (0, 0, 255), (230, 120, 0), (0, 160, 160), (160, 0, 160), (120, 80, 0)]
    for j, (name, rs) in enumerate(per.items()):
        for k, rr in enumerate(rs):
            if rr is not None:
                x, y = X(cx + rr * math.cos(angs[k]), cy + rr * math.sin(angs[k]))
                dr.ellipse([x - 3, y - 3, x + 3, y + 3], fill=cols[j % 6])
        dr.text(X(w0 + 0.01, v1 - 0.01 - 0.012 * j), name, fill=cols[j % 6])
    dr.line([X(*p) for p in out] + [X(*out[0])], fill=(0, 0, 0), width=3)
    img.save(opt('--plot'))
