"""gate.py <tris.npz> <out dir>: the model against the photos' solved cameras (s1 side, fr front), the rectified planform, the published figures"""
import json
import sys
import cv2
import numpy as np
import os
# FIT: the folder with fit/cams.json and fit/plan_mask.png (plan.py); PHOTOS: the photographs of ref/list.json (not in the repository)
D = os.environ['FIT'].rstrip('/') + '/'
PH = os.environ['PHOTOS'].rstrip('/') + '/'
Z = np.load(sys.argv[1], allow_pickle=True)
out = sys.argv[2]
P = Z['P'].astype(np.float64)                      # (n, 3, 3) game frame
names = list(Z['names'])
O = Z['O']
ZN = 9.33
cams = json.load(open(D + 'fit/cams.json'))['cams']


def outline(mask, k=2):
    e = cv2.morphologyEx(mask, cv2.MORPH_GRADIENT, np.ones((3, 3), np.uint8))
    return cv2.dilate(e, np.ones((k, k), np.uint8)) > 0


def silhouette(uv, size):
    m = np.zeros((size[1], size[0]), np.uint8)
    pts = np.round(uv * 8).astype(np.int32)
    for t in pts:
        cv2.fillConvexPoly(m, t, 255, shift=3)
    return m


rep = []
for name in ('s1', 'fr'):
    c = cams[name]
    C, R, f = np.array(c['C']), np.array(c['R']), c['f']
    W, H = c['size']
    q = (P.reshape(-1, 3) - C) @ R.T
    uv = np.stack([W / 2 + f * q[:, 0] / q[:, 2], H / 2 + f * q[:, 1] / q[:, 2]], 1).reshape(-1, 3, 2)
    m = silhouette(uv, (W, H))
    im = cv2.imread(PH + name + '.jpg')
    if im.shape[1] != W:
        im = cv2.resize(im, (W, H))
    ov = im.copy()
    zl = list(Z["zones"])
    for zn, col in (("cowl", (255, 0, 255)), ("wing", (0, 255, 0)), ("glass", (255, 128, 0)), ("fin", (0, 128, 255)), ("stab", (0, 0, 255)), ("radome", (255, 255, 255)), ("lip", (255, 0, 0)), ("metal", (128, 255, 128))):
        if zn in zl:
            ov[outline(silhouette(uv[Z["Z"] == zl.index(zn)], (W, H)), 1)] = col
    ov[outline(m)] = (0, 255, 255)
    cv2.imwrite(f'{out}/g_{name}.jpg', ov, [cv2.IMWRITE_JPEG_QUALITY, 90])
    cv2.imwrite(f'{out}/m_{name}.png', m)

# planform: 100 px/m, the axis at column 750, the nose at row 50
plan = cv2.imread(D + 'fit/plan.png')
mask = cv2.imread(D + 'fit/plan_mask.png', 0) > 127
uv = np.stack([750 + P[:, :, 0] * 100, 50 + (ZN - P[:, :, 2]) * 100], 2)
m = silhouette(uv, (plan.shape[1], plan.shape[0]))
mm = m > 127
iou = (mm & mask).sum() / max(1, (mm | mask).sum())
ov = plan.copy()
ov[outline(m, 3)] = (0, 255, 255)
cv2.imwrite(f'{out}/g_plan.jpg', ov, [cv2.IMWRITE_JPEG_QUALITY, 90])
rep.append(f'planform IoU {iou:.3f} (the photo is seen from below at ~22 deg: parts off the wing plane shift)')

A = P.reshape(-1, 3)
lo, hi = A.min(0), A.max(0)
rep.append(f'length {hi[2] - lo[2]:.3f} (19.43)   span {hi[0] - lo[0]:.3f} (13.05)   height {hi[1]:.3f} (5.63)   lowest {lo[1]:.3f}')
for n in ('stab_m',):
    if n in names:
        S = P[O == names.index(n)].reshape(-1, 3)
        rep.append(f'tailplane span {S[:, 0].max() - S[:, 0].min():.3f} (8.61)')
for n, want in (('spin_l_m', 'main wheel'), ('steer_nose_m', 'nose wheel')):
    if n in names:
        S = P[O == names.index(n)].reshape(-1, 3)
        k = S[:, 1] < 0.02
        rep.append(f'{want}: contact x {S[k, 0].mean():+.3f} z {S[k, 2].mean():+.3f}  lowest {S[:, 1].min():.4f}')
rep.append(f'nose tip d = {ZN - hi[2]:.3f}  tail d = {ZN - lo[2]:.3f}')
print('\n'.join(rep))
open(f'{out}/gate.txt', 'w').write('\n'.join(rep) + '\n')
