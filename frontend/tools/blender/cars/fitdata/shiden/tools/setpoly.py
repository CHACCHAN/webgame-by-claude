"""setpoly.py <lamps.json> <photo> <lamp> 'x,y;x,y;...' [--smooth 3] [--check photo.jpg out.png]: a hand-traced outline
(closed; Catmull-Rom through the points with --smooth points per span) into lamps.json"""
import json, sys
import numpy as np
a = sys.argv[1:]
lj, ph, lamp, s = a[:4]
pts = [tuple(float(v) for v in p.split(',')) for p in s.split(';') if p]
k = int(a[a.index('--smooth') + 1]) if '--smooth' in a else 1
out = []
n = len(pts)
for i in range(n):
    p0, p1, p2, p3 = (np.array(pts[(i + j) % n]) for j in (-1, 0, 1, 2))
    for q in range(k):
        t = q / k
        out.append(0.5 * (2 * p1 + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3))
db = json.load(open(lj))
db.setdefault('photos', {}).setdefault(ph, {})[lamp] = {'poly': [[round(float(x), 2), round(float(y), 2)] for x, y in out], 'how': 'hand'}
json.dump(db, open(lj, 'w'), indent=1)
if '--check' in a:
    import cv2
    from PIL import Image
    i = a.index('--check')
    img = np.array(Image.open(a[i + 1]).convert('RGB'))
    P = np.array(out)
    x0, y0 = (P.min(0) - 25).astype(int)
    x1, y1 = (P.max(0) + 25).astype(int)
    x0, y0 = max(0, x0), max(0, y0)
    S = 4
    crop = cv2.resize(img[y0:y1, x0:x1], ((x1 - x0) * S, (y1 - y0) * S), interpolation=cv2.INTER_CUBIC)
    cv2.polylines(crop, [np.round((P - [x0, y0]) * S).astype(np.int32)], True, (0, 255, 0), 1, cv2.LINE_AA)
    for x, y in pts:
        cv2.circle(crop, (int((x - x0) * S), int((y - y0) * S)), 3, (255, 0, 255), -1)
    Image.fromarray(crop).save(a[i + 2])
print(ph, lamp, len(out), 'pts')
