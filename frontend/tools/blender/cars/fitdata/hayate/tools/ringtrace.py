"""ringtrace.py: a lamp's outline on a photo as the area inside its dark seal ring. Inside the box, pixels lighter than
--thr (L, 0-255) reachable from the box's border (flood fill, 4-connected) are outside; the rest (holes filled) is the
lamp, its outline written as a polygon into lamps.json [photo][lamp] (photo px at the calibrated size) and drawn on
a 4x check crop. Works where the paint round the lamp is light (silver / white cars) and the seal is a dark line.

  py ringtrace.py <photo> <lamps.json> <photo name> <lamp> <x0,y0,x1,y1> [--thr 90] [--scale s (photo px per
      calibrated px)] [--close 1] [--grow 0] [--n 48] [--cut x0,y0,x1,y1 ...] [--check out.png] [--dry]
--cut boxes (calibrated px) are forced to 'outside' seeds (walls off a dark grille next to the lamp).
"""
import json, sys

import cv2
import numpy as np
from PIL import Image

a = sys.argv[1:]


def opt(k, d=None):
    return a[a.index(k) + 1] if k in a else d


photo, lj, ph, lamp = a[:4]
sc = float(opt('--scale', '1'))
bx = [float(v) for v in a[4].split(',')]
x0, y0, x1, y1 = (int(round(v * sc)) for v in bx)
img = np.array(Image.open(photo).convert('RGB'))
roi = img[y0:y1, x0:x1]
L = cv2.cvtColor(roi, cv2.COLOR_RGB2LAB)[..., 0].astype(np.uint8)
thr = float(opt('--thr', '90'))
light = (L > thr).astype(np.uint8)
k = int(opt('--close', '1'))
dark = 1 - light
if k:
    dark = cv2.morphologyEx(dark, cv2.MORPH_CLOSE, np.ones((2 * k + 1, 2 * k + 1), np.uint8))
light = 1 - dark
H, W = light.shape
outside = np.zeros((H + 2, W + 2), np.uint8)
ff = light.copy()
seeds = [(x, 0) for x in range(W)] + [(x, H - 1) for x in range(W)] + [(0, y) for y in range(H)] + [(W - 1, y) for y in range(H)]
for i, t in enumerate(a):
    if t == '--cut':
        c = [int(round(float(v) * sc)) for v in a[i + 1].split(',')]
        ff[max(0, c[1] - y0):max(0, c[3] - y0), max(0, c[0] - x0):max(0, c[2] - x0)] = 1
        seeds += [(max(0, c[0] - x0), max(0, c[1] - y0))]
reach = np.zeros_like(ff)
mask = np.zeros((H + 2, W + 2), np.uint8)
for sx, sy in seeds:
    if ff[sy, sx] and not reach[sy, sx]:
        tmp = ff.copy()
        cv2.floodFill(tmp, mask, (sx, sy), 2, flags=4)
        reach |= (tmp == 2).astype(np.uint8)
lampm = (1 - reach).astype(np.uint8)
lampm = cv2.morphologyEx(lampm, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
cs, _ = cv2.findContours(lampm, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
c = max(cs, key=cv2.contourArea)
fill = np.zeros_like(lampm)
cv2.drawContours(fill, [c], -1, 1, -1)
g = int(opt('--grow', '0'))
if g > 0:
    fill = cv2.dilate(fill, np.ones((2 * g + 1, 2 * g + 1), np.uint8))
elif g < 0:
    fill = cv2.erode(fill, np.ones((-2 * g + 1, -2 * g + 1), np.uint8))
cs, _ = cv2.findContours(fill, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
c = max(cs, key=cv2.contourArea)[:, 0, :].astype(float) + 0.5
N = int(opt('--n', '48'))
cc = np.vstack([c, c[:1]])
seg = np.r_[0, np.cumsum(np.hypot(*np.diff(cc, axis=0).T))]
t = np.linspace(0, seg[-1], N, endpoint=False)
poly = (np.stack([np.interp(t, seg, cc[:, 0]), np.interp(t, seg, cc[:, 1])], 1) + [x0, y0]) / sc
print(f'{ph} {lamp}: {len(poly)} pts, bbox {poly[:, 0].min():.0f}..{poly[:, 0].max():.0f} x {poly[:, 1].min():.0f}..{poly[:, 1].max():.0f}')
if '--dry' not in a:
    db = json.load(open(lj))
    db.setdefault('photos', {}).setdefault(ph, {})[lamp] = {'poly': [[round(float(u), 2), round(float(v), 2)] for u, v in poly],
                                                           'how': 'ringtrace ' + ' '.join(a[4:])}
    json.dump(db, open(lj, 'w'), indent=1)
chk = opt('--check')
if chk:
    S = max(1, int(round(4 / sc)))
    crop = cv2.resize(roi, (W * S, H * S), interpolation=cv2.INTER_CUBIC)
    q = np.round((poly * sc - [x0, y0]) * S).astype(np.int32)
    tint = crop.copy()
    rm = cv2.resize(reach, (W * S, H * S), interpolation=cv2.INTER_NEAREST)
    tint[rm > 0] = (0.6 * tint[rm > 0] + 0.4 * np.array([0, 160, 255])).astype(np.uint8)
    cv2.polylines(crop, [q], True, (0, 255, 0), 1, cv2.LINE_AA)
    cv2.polylines(tint, [q], True, (0, 255, 0), 1, cv2.LINE_AA)
    Image.fromarray(np.concatenate([crop, np.full((crop.shape[0], 6, 3), 255, np.uint8), tint], 1)).save(chk)
