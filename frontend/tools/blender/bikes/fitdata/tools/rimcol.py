"""rimcol.py <photo> <rough.json> <out.json> <overlay.png> [colour r,g,b] [tol] [band px] [run px]: rim lip ellipse from the rim's colour.
For each wheel, rays from the rough ellipse's centre: the outermost rim-coloured pixel within ±band of the rough ellipse;
an ellipse fitted with trimming. rough.json: {wheel: [[u,v] >= 5 points on the lip]} (or {"pts": ..., "colour": [r,g,b]})."""
import json, sys, math
import cv2, numpy as np
from PIL import Image
img = np.array(Image.open(sys.argv[1]).convert('RGB')).astype(np.int32)
R = json.load(open(sys.argv[2]))
col = [int(v) for v in sys.argv[5].split(',')] if len(sys.argv) > 5 else [220, 30, 30]
tol = float(sys.argv[6]) if len(sys.argv) > 6 else 70
band = float(sys.argv[7]) if len(sys.argv) > 7 else 25
run = int(sys.argv[8]) if len(sys.argv) > 8 else 4      # rim colour needed this many px inward (thin stripes: 2)
H, W = img.shape[:2]
out = {}; ov = img.astype(np.uint8).copy()
for w, v in R.items():
    pts = v['pts'] if isinstance(v, dict) else v
    c = np.array(v.get('colour', col) if isinstance(v, dict) else col)
    d = np.sqrt(((img - c[None, None]) ** 2).sum(2))
    M = d < tol
    (cx, cy), (A, B), ang = cv2.fitEllipse(np.array(pts, np.float32))
    for it in range(3):
        a, b, t = A / 2, B / 2, math.radians(ang)
        found = []
        for th in np.linspace(0, 2 * math.pi, 180, endpoint=False):
            ex = cx + a * math.cos(th) * math.cos(t) - b * math.sin(th) * math.sin(t)
            ey = cy + a * math.cos(th) * math.sin(t) + b * math.sin(th) * math.cos(t)
            ux, uy = ex - cx, ey - cy; n = math.hypot(ux, uy); ux, uy = ux / n, uy / n
            best = None
            for s in np.arange(band, -band, -0.5):
                px, py = int(round(ex + s * ux)), int(round(ey + s * uy))
                if 0 <= px < W and 0 <= py < H and M[py, px]:
                    # need a run of rim colour inward (not a speck)
                    ok = all(M[min(H - 1, max(0, int(round(py - k * uy)))), min(W - 1, max(0, int(round(px - k * ux))))] for k in range(1, run + 1))
                    if ok:
                        best = (ex + s * ux, ey + s * uy); break
            if best is not None and abs(s) < band - 0.6:
                found.append(best)
        F = np.array(found, np.float32)
        if len(F) < 6: print(w, 'too few', len(F)); break
        (cx, cy), (A, B), ang = cv2.fitEllipse(F)
        # trim: drop points far from the ellipse
        a, b, t = A / 2, B / 2, math.radians(ang)
        q = F - [cx, cy]; xr = q[:, 0] * math.cos(t) + q[:, 1] * math.sin(t); yr = -q[:, 0] * math.sin(t) + q[:, 1] * math.cos(t)
        e = np.abs(np.sqrt((xr / a) ** 2 + (yr / b) ** 2) - 1) * (a + b) / 2
        keep = e < max(1.5, np.percentile(e, 75))
        (cx, cy), (A, B), ang = cv2.fitEllipse(F[keep])
        band = max(6, band * 0.5)
    a, b, t = A / 2, B / 2, math.radians(ang)
    out[w] = {'ellipse': [cx, cy, a, b, ang], 'found': F[keep].round(1).tolist(),
              'pts': [[round(cx + a * math.cos(q) * math.cos(t) - b * math.sin(q) * math.sin(t), 2),
                       round(cy + a * math.cos(q) * math.sin(t) + b * math.sin(q) * math.cos(t), 2)] for q in np.linspace(0, 2 * math.pi, 24, endpoint=False)]}
    print(w, 'centre (%.1f, %.1f) axes %.1f %.1f ang %.1f  n %d  resid p75 %.2f' % (cx, cy, a, b, ang, keep.sum(), np.percentile(e, 75)))
    cv2.ellipse(ov, ((cx, cy), (A, B), ang), (255, 0, 255), 1)
    for x, y in F[keep]: cv2.circle(ov, (int(x), int(y)), 2, (0, 255, 0), -1)
json.dump(out, open(sys.argv[3], 'w'))
Image.fromarray(ov).save(sys.argv[4])
