"""reverse lamps on r48: the clear lens (white ring + grey inside) on the red lens; written as rv_R / rv_L"""
import json, sys, cv2, numpy as np
from PIL import Image
S = 2
im = np.array(Image.open('../photos_hi/r48.jpg').convert('RGB')).astype(int)
db = json.load(open('lamps.json'))
chk = []
for lamp, (x0, y0, x1, y1) in {'rv_R': (875, 405, 975, 470), 'rv_L': (255, 395, 350, 460)}.items():
    c = im[y0 * S:y1 * S, x0 * S:x1 * S]
    R, G, B = c[..., 0], c[..., 1], c[..., 2]
    m = ((G > int(sys.argv[1])) & (B > int(sys.argv[1])) & (R - G < int(sys.argv[2]))).astype(np.uint8)
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7)))
    n, cl, st, _ = cv2.connectedComponentsWithStats(m)
    big = 1 + int(np.argmax(st[1:, cv2.CC_STAT_AREA]))
    comp = (cl == big).astype(np.uint8)
    cs, _ = cv2.findContours(comp, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    cc = cv2.convexHull(max(cs, key=cv2.contourArea))[:, 0, :].astype(float) + 0.5   # the lens is convex
    cc = np.vstack([cc, cc[:1]])
    seg = np.r_[0, np.cumsum(np.hypot(*np.diff(cc, axis=0).T))]
    t = np.linspace(0, seg[-1], 40, endpoint=False)
    poly = (np.stack([np.interp(t, seg, cc[:, 0]), np.interp(t, seg, cc[:, 1])], 1) + [x0 * S, y0 * S]) / S
    print(lamp, poly.min(0).round(1), poly.max(0).round(1))
    db['photos']['r48'][lamp] = {'poly': [[round(float(u), 2), round(float(v), 2)] for u, v in poly], 'how': 'revtrace ' + ' '.join(sys.argv[1:])}
    K = 6
    big_c = cv2.resize(c.astype(np.uint8), (c.shape[1] * K // S * 1, c.shape[0] * K // S), interpolation=cv2.INTER_CUBIC)
    q = np.round((poly - [x0, y0]) * K).astype(np.int32)
    cv2.polylines(big_c, [q], True, (0, 255, 0), 1, cv2.LINE_AA)
    chk.append(big_c)
if '--dry' not in sys.argv:
    json.dump(db, open('lamps.json', 'w'), indent=1)
h = max(x.shape[0] for x in chk)
Image.fromarray(np.concatenate([np.pad(x, ((0, h - x.shape[0]), (0, 8), (0, 0)), constant_values=255) for x in chk], 1)).save('trace/rv_check.png')
