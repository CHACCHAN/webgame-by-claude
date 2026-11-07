"""
detect.py <work.jpg> <seeds.json key> <out_dbg.png>: refine wheel rims (ellipse fit to the rim's outer edge along rays)
and plates (bright quad) from rough seeds; prints JSON of refined points.
seeds: {"rims": {"wf_l": [cx, cy, rx, ry], ...}, "plates": {"plate_r": [x0, y0, x1, y1]}}
"""
import json, sys, math
import numpy as np, cv2

img = cv2.imread(sys.argv[1])
seeds = json.load(open(sys.argv[2]))[sys.argv[3]]
gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32)
g = cv2.GaussianBlur(gray, (0, 0), 1.2)
gx = cv2.Sobel(g, cv2.CV_32F, 1, 0, ksize=3)
gy = cv2.Sobel(g, cv2.CV_32F, 0, 1, ksize=3)
dbg = img.copy()
out = {}


def bil(a, x, y):
    return cv2.getRectSubPix(a, (1, 1), (float(x), float(y)))[0, 0]


for name, (cx, cy, rx, ry) in seeds.get('rims', {}).items():
    pts = []
    for k in range(120):
        a = 2 * math.pi * k / 120
        dx, dy = math.cos(a), math.sin(a)
        best, bt = 0, None
        for t in np.linspace(0.65, 1.35, 90):
            x, y = cx + rx * t * dx, cy + ry * t * dy
            if not (1 < x < img.shape[1] - 2 and 1 < y < img.shape[0] - 2):
                continue
            # derivative along the ray (outward), bright rim -> dark tyre: negative
            nx, ny = rx * dx, ry * dy
            l = math.hypot(nx, ny)
            d = (bil(gx, x, y) * nx + bil(gy, x, y) * ny) / l
            if -d > best:
                best, bt = -d, (x, y)
        if bt is not None and best > 8:
            pts.append(bt)
    P = np.array(pts, np.float32)
    keep = np.ones(len(P), bool)
    for it in range(4):
        if keep.sum() < 8:
            break
        e = cv2.fitEllipse(P[keep])
        (ex, ey), (w, h), ang = e
        # residual: normalised radial distance
        ca, sa = math.cos(math.radians(ang)), math.sin(math.radians(ang))
        X, Y = P[:, 0] - ex, P[:, 1] - ey
        u = (X * ca + Y * sa) / (w / 2)
        v = (-X * sa + Y * ca) / (h / 2)
        r = np.abs(np.sqrt(u * u + v * v) - 1)
        thr = max(0.04, np.percentile(r[keep], 75) * 2)
        keep = r < thr
    e = cv2.fitEllipse(P[keep])
    out[name] = {'centre': [round(e[0][0], 2), round(e[0][1], 2)], 'axes': [round(e[1][0] / 2, 2), round(e[1][1] / 2, 2)], 'angle': round(e[2], 2), 'n': int(keep.sum()), 'of': len(P)}
    cv2.ellipse(dbg, e, (0, 0, 255), 1)
    for p, kk in zip(P, keep):
        cv2.circle(dbg, (int(p[0]), int(p[1])), 1, (0, 255, 0) if kk else (255, 0, 255), -1)
    cv2.drawMarker(dbg, (int(e[0][0]), int(e[0][1])), (0, 0, 255), cv2.MARKER_CROSS, 12, 1)

for name, (x0, y0, x1, y1) in seeds.get('plates', {}).items():
    roi = img[y0:y1, x0:x1]
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    v = hsv[:, :, 2].astype(np.float32)
    thr = np.percentile(v, 50) * 0.5 + np.percentile(v, 97) * 0.5
    m = ((v > thr) & (hsv[:, :, 1] < 80)).astype(np.uint8) * 255
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    cs, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    c = max(cs, key=cv2.contourArea)
    hull = cv2.convexHull(c)
    q = None
    for eps in np.linspace(0.01, 0.1, 30):
        ap = cv2.approxPolyDP(hull, eps * cv2.arcLength(hull, True), True)
        if len(ap) == 4:
            q = ap.reshape(4, 2).astype(np.float32)
            break
    if q is None:
        print('plate fail', name)
        continue
    # refine each side by fitting lines to contour points near it
    C = c.reshape(-1, 2).astype(np.float32)
    lines = []
    for i in range(4):
        a, b = q[i], q[(i + 1) % 4]
        ab = b - a
        L = np.linalg.norm(ab)
        n = np.array([-ab[1], ab[0]]) / L
        t = ((C - a) @ ab) / L ** 2
        dd = np.abs((C - a) @ n)
        sel = (t > 0.15) & (t < 0.85) & (dd < 4)
        if sel.sum() < 5:
            lines.append((a, ab / L))
            continue
        vx, vy, x_, y_ = cv2.fitLine(C[sel], cv2.DIST_HUBER, 0, 0.01, 0.01).ravel()
        lines.append((np.array([x_, y_]), np.array([vx, vy])))
    cor = []
    for i in range(4):
        (p1, d1), (p2, d2) = lines[i - 1], lines[i]
        A = np.array([d1, -d2]).T
        s = np.linalg.solve(A, p2 - p1)
        cor.append(p1 + s[0] * d1 + np.array([x0, y0]))
    cor = np.array(cor)
    # order: top-left, top-right, bottom-right, bottom-left (image)
    cc = cor.mean(0)
    ang = np.arctan2(cor[:, 1] - cc[1], cor[:, 0] - cc[0])
    cor = cor[np.argsort(ang)]          # from -pi: TL(-3pi/4) TR(-pi/4) BR BL
    out[name] = {'corners': [[round(float(a), 2), round(float(b), 2)] for a, b in cor]}
    cv2.polylines(dbg, [cor.astype(np.int32).reshape(-1, 1, 2)], True, (0, 0, 255), 1)
cv2.imwrite(sys.argv[4], dbg)
print(json.dumps(out))
