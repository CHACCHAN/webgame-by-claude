import json, numpy as np
d = json.load(open('trace/rv_back.json'))['r48']
outs = []
for k in ('rv_R', 'rv_L'):
    p = np.array([q for q in d[k] if q is not None])
    outs.append(np.stack([np.abs(p[:, 0]), p[:, 1]], 1))
c = np.mean([o.mean(0) for o in outs], 0)
th = np.radians(np.arange(0, 360, 12))
R = []
for o in outs:
    a = np.arctan2(o[:, 1] - c[1], o[:, 0] - c[0]); r = np.hypot(*(o - c).T)
    i = np.argsort(a); a, r = a[i], r[i]
    a = np.r_[a - 2 * np.pi, a, a + 2 * np.pi]; r = np.r_[r, r, r]
    R.append(np.interp(np.arctan2(np.sin(th), np.cos(th)), a, r))
R = np.array(R)
print('centre', c.round(4), 'R/L radius diff mm: mean', (1000 * np.abs(R[0] - R[1])).mean().round(1), 'max', (1000 * np.abs(R[0] - R[1])).max().round(1))
r = R.mean(0)
pts = np.stack([c[0] + r * np.cos(th), c[1] + r * np.sin(th)], 1)
print('[' + ', '.join(f'({x:.3f}, {y:.3f})' for x, y in pts) + ']')
print('bbox', pts.min(0).round(3), pts.max(0).round(3))
