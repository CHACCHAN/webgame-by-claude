"""livmask.py <photo> <sil.png> <outdir> : colour masks (red, blue, navy) of livery areas inside the model silhouette,
their contours simplified → <outdir>/pts.json {"red_0": [[u,v]...], ...} and a preview"""
import sys, json, os
import cv2, numpy as np
ph = cv2.imread(sys.argv[1]); H, W = ph.shape[:2]
sil = cv2.imread(sys.argv[2], cv2.IMREAD_UNCHANGED)
sil = cv2.resize(sil[:, :, 3], (W, H), interpolation=cv2.INTER_NEAREST) > 127
sil = cv2.dilate(sil.astype(np.uint8), np.ones((25, 25), np.uint8)).astype(bool)
out = sys.argv[3]
hsv = cv2.cvtColor(ph, cv2.COLOR_BGR2HSV).astype(int)
h, s, v = hsv[..., 0], hsv[..., 1], hsv[..., 2]
masks = {
    'red': (((h < 8) | (h > 170)) & (s > 120) & (v > 70)),
    'blue': ((h > 100) & (h < 130) & (s > 120) & (v > 60)),
    'navy': ((h > 100) & (h < 135) & (s > 60) & (v < 90) & (v > 15)),
}
pts = {}
prev = ph.copy() // 3
cols = {'red': (40, 40, 255), 'blue': (255, 80, 30), 'navy': (140, 40, 40)}
for k, m in masks.items():
    m = (m & sil).astype(np.uint8)
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    prev[m > 0] = cols[k]
    cs, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    cs = [c for c in cs if cv2.contourArea(c) > 400]
    for i, c in enumerate(sorted(cs, key=cv2.contourArea, reverse=True)):
        a = cv2.approxPolyDP(c, 2.0, True)[:, 0]
        # resample to ~6 px spacing
        p = np.concatenate([a, a[:1]]).astype(float)
        seg = np.linalg.norm(np.diff(p, axis=0), axis=1); L = seg.sum()
        t = np.linspace(0, L, max(8, int(L / 6)), endpoint=False)
        cum = np.concatenate([[0], np.cumsum(seg)])
        q = [p[np.searchsorted(cum, x, 'right') - 1] + (p[np.searchsorted(cum, x, 'right')] - p[np.searchsorted(cum, x, 'right') - 1]) * ((x - cum[np.searchsorted(cum, x, 'right') - 1]) / max(1e-9, seg[np.searchsorted(cum, x, 'right') - 1])) for x in t]
        pts[f'{k}_{i}'] = [[round(float(x), 1), round(float(y), 1)] for x, y in q]
        cv2.polylines(prev, [c], True, (255, 255, 255), 1)
        x, y, w_, h_ = cv2.boundingRect(c)
        cv2.putText(prev, f'{k}_{i}', (x, y + 12), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
json.dump(pts, open(os.path.join(out, 'pts.json'), 'w'))
cv2.imwrite(os.path.join(out, 'mask_preview.jpg'), cv2.resize(prev, (W // 2, H // 2)))
print({k: len(v) for k, v in pts.items()})
