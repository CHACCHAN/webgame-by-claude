"""colortrace.py: a lamp's outline on a photo as the region of lamp colour (red / amber lens: by chroma; clear parts
are added by closing). Writes the polygon (calibrated photo px) into lamps.json [photo][lamp] and a check image.

  py colortrace.py <photo> <lamps.json> <ph> <lamp> <x0,y0,x1,y1> [--scale s] [--hue a0,a1] [--minc 18] [--close 3]
      [--open 1] [--add x0,y0,x1,y1 ...] [--cut x0,y0,x1,y1 ...] [--n 48] [--check out.png] [--dry]
box / add / cut in calibrated px; --scale: photo px per calibrated px (hi-res photo); --hue in degrees of the Lab
(a*, b*) angle (red ~ 20-45, amber ~ 50-75)
"""
import json, sys
import cv2
import numpy as np
from PIL import Image
a = sys.argv[1:]


def opt(k, d=None):
    return a[a.index(k) + 1] if k in a else d


photo, lj, ph, lamp = a[:4]
S = float(opt('--scale', '1'))
bx = [float(v) for v in a[4].split(',')]
x0, y0, x1, y1 = (int(round(v * S)) for v in bx)
img = np.array(Image.open(photo).convert('RGB'))[y0:y1, x0:x1]
lab = cv2.cvtColor(img, cv2.COLOR_RGB2LAB).astype(float)
A, Bc = lab[..., 1] - 128, lab[..., 2] - 128
mag = np.hypot(A, Bc)
ang = np.degrees(np.arctan2(Bc, A))
h0, h1 = (float(v) for v in opt('--hue', '-10,80').split(','))
m = ((mag > float(opt('--minc', '18'))) & (ang > h0) & (ang < h1)).astype(np.uint8)
for i, t in enumerate(a):
    if t in ('--add', '--cut'):
        c = [int(round(float(v) * S)) for v in a[i + 1].split(',')]
        m[max(0, c[1] - y0):max(0, c[3] - y0), max(0, c[0] - x0):max(0, c[2] - x0)] = 1 if t == '--add' else 0
k = int(round(int(opt('--open', '1')) * S))
if k:
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((2 * k + 1, 2 * k + 1), np.uint8))
k = int(round(int(opt('--close', '3')) * S))
if k:
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * k + 1, 2 * k + 1)))
n, cl, st, _ = cv2.connectedComponentsWithStats(m)
big = 1 + int(np.argmax(st[1:, cv2.CC_STAT_AREA]))
comp = (cl == big).astype(np.uint8)
cs, _ = cv2.findContours(comp, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
c = max(cs, key=cv2.contourArea)[:, 0, :].astype(float) + 0.5
N = int(opt('--n', '48'))
cc = np.vstack([c, c[:1]])
seg = np.r_[0, np.cumsum(np.hypot(*np.diff(cc, axis=0).T))]
t = np.linspace(0, seg[-1], N, endpoint=False)
poly = (np.stack([np.interp(t, seg, cc[:, 0]), np.interp(t, seg, cc[:, 1])], 1) + [x0, y0]) / S
print(f'{ph} {lamp}: bbox {poly[:, 0].min():.0f}..{poly[:, 0].max():.0f} x {poly[:, 1].min():.0f}..{poly[:, 1].max():.0f}')
if '--dry' not in a:
    db = json.load(open(lj)) if __import__('os').path.exists(lj) else {'photos': {}}
    db.setdefault('photos', {}).setdefault(ph, {})[lamp] = {'poly': [[round(float(u), 2), round(float(v), 2)] for u, v in poly],
                                                           'how': 'colortrace ' + ' '.join(a[4:])}
    json.dump(db, open(lj, 'w'), indent=1)
chk = opt('--check')
if chk:
    K = max(1, int(round(900 / img.shape[1])))
    crop = cv2.resize(img, (img.shape[1] * K, img.shape[0] * K), interpolation=cv2.INTER_CUBIC)
    tint = crop.copy()
    mm = cv2.resize(m, (crop.shape[1], crop.shape[0]), interpolation=cv2.INTER_NEAREST)
    tint[mm > 0] = (0.5 * tint[mm > 0] + 0.5 * np.array([0, 255, 255])).astype(np.uint8)
    q = np.round((poly * S - [x0, y0]) * K).astype(np.int32)
    cv2.polylines(crop, [q], True, (0, 255, 0), 1, cv2.LINE_AA)
    cv2.polylines(tint, [q], True, (0, 255, 0), 1, cv2.LINE_AA)
    Image.fromarray(np.concatenate([crop, tint], 0)).save(chk)
