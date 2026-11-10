"""rimfit.py <photo> <rough.json> <out.json> [overlay.png] : refine rough rim-lip points (>= 5 per wheel, read on a grid
crop) to the ellipse on the image's strongest edge; writes 24 points per wheel for solve.py"""
import json, sys, math
import cv2, numpy as np
from PIL import Image
img = np.array(Image.open(sys.argv[1]).convert('RGB')).astype(np.float32)
R = json.load(open(sys.argv[2]))
g = cv2.GaussianBlur(cv2.cvtColor(img.astype(np.uint8), cv2.COLOR_RGB2GRAY).astype(np.float32), (0, 0), 1.0)
gx, gy = cv2.Sobel(g, cv2.CV_32F, 1, 0), cv2.Sobel(g, cv2.CV_32F, 0, 1)
samp = lambda a, x, y: cv2.getRectSubPix(a, (1, 1), (float(x), float(y)))[0, 0]
out = {}; ov = img.copy()
for w, pts in R.items():
    (cx, cy), (A, B), ang = cv2.fitEllipse(np.array(pts, np.float32))
    for it in range(4):
        th = np.linspace(0, 2 * math.pi, 72, endpoint=False); a, b, t = A / 2, B / 2, math.radians(ang)
        ex = cx + a * np.cos(th) * math.cos(t) - b * np.sin(th) * math.sin(t)
        ey = cy + a * np.cos(th) * math.sin(t) + b * np.sin(th) * math.cos(t)
        nx, ny = ex - cx, ey - cy; nn = np.hypot(nx, ny); nx, ny = nx / nn, ny / nn
        found = []
        rng = 6 if it < 2 else 3
        for x, y, ux, uy in zip(ex, ey, nx, ny):
            best, bs = (x, y), 0
            for s in np.arange(-rng, rng + 0.01, 0.5):
                px, py = x + s * ux, y + s * uy
                gr = abs(samp(gx, px, py) * ux + samp(gy, px, py) * uy)
                if gr > bs: bs, best = gr, (px, py)
            found.append((best, bs))
        thr = np.percentile([f[1] for f in found], 30)
        (cx, cy), (A, B), ang = cv2.fitEllipse(np.array([f[0] for f in found if f[1] >= thr], np.float32))
    th = np.linspace(0, 2 * math.pi, 24, endpoint=False); a, b, t = A / 2, B / 2, math.radians(ang)
    out[w] = {'ellipse': [cx, cy, a, b, ang], 'pts': [[round(cx + a * math.cos(q) * math.cos(t) - b * math.sin(q) * math.sin(t), 2),
              round(cy + a * math.cos(q) * math.sin(t) + b * math.sin(q) * math.cos(t), 2)] for q in th]}
    print(w, 'centre (%.1f, %.1f) axes %.1f %.1f ang %.1f' % (cx, cy, a, b, ang))
    cv2.ellipse(ov, ((cx, cy), (A, B), ang), (255, 0, 255), 1)
json.dump(out, open(sys.argv[3], 'w'), indent=0)
if len(sys.argv) > 4:
    Image.fromarray(np.clip(ov, 0, 255).astype(np.uint8)).save(sys.argv[4])
