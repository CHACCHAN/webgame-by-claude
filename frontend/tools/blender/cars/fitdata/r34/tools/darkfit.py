"""
darkfit.py: the material lines of a two-tone car, measured. Inside the car (photo mask ∩ model silhouette, wheels left
out) the photo's dark parts (glass, black trim, black lower body, rubber) and, on a light car, its red / amber lamp
lenses are segmented by brightness and colour; the model's are the same materials in its id render. The borders of
the two masks are compared both ways (distance from each border pixel to the other's border), in % of the car's
width in the image.

  py darkfit.py <photo> <ids.png> <palette.json> <photo_mask.png> <outdir> <name> [white|red]
  -> <name>_dark.json, <name>_dark.png (photo dimmed; cyan / green = photo's dark / lamp borders, magenta / red = model's)
"""
import json, os, sys

import cv2
import numpy as np
from PIL import Image

photo, ids_p, pal_p, mask_p, out, name = sys.argv[1:7]
livery = sys.argv[7] if len(sys.argv) > 7 else 'white'

DARK = {'glass', 'trim', 'accent', 'interior', 'tire'}
LAMP = {'taillight', 'amber'} if livery == 'white' else {'amber'}
WHEEL = {'tire', 'rim', 'disc', 'brake'}
SKIP = {'reverse', 'headlight', 'popup_lens', 'chrome', 'brake', 'disc'}

ids = np.array(Image.open(ids_p).convert('RGBA'))
H, W = ids.shape[:2]
img = np.array(Image.open(photo).convert('RGB').resize((W, H), Image.LANCZOS))
pm = np.array(Image.open(mask_p).convert('L').resize((W, H), Image.NEAREST)) > 127
pal = json.load(open(pal_p))
names = sorted(pal)
cols = np.array([pal[k] for k in names], float)
sil = ids[:, :, 3] > 127
rgb = ids[:, :, :3].reshape(-1, 3).astype(float)
lab = np.argmin(((rgb[:, None, :] - cols[None]) ** 2).sum(-1), 1).reshape(H, W)
lab[~sil] = -1


def mat_mask(group):
    idx = [names.index(k) for k in group if k in names]
    return np.isin(lab, idx)


ys, xs = np.nonzero(pm)
width = float(xs.max() - xs.min() + 1)
k3 = np.ones((3, 3), np.uint8)

region = pm & sil
wheel = cv2.dilate(mat_mask(WHEEL).astype(np.uint8), np.ones((25, 25), np.uint8)) > 0
skip = cv2.dilate(mat_mask(SKIP).astype(np.uint8), np.ones((7, 7), np.uint8)) > 0
region &= ~wheel & ~skip
region = cv2.erode(region.astype(np.uint8), np.ones((9, 9), np.uint8)) > 0

hsv = cv2.cvtColor(img, cv2.COLOR_RGB2HSV)
V = hsv[:, :, 2].astype(float)
S = hsv[:, :, 1].astype(float)
Hh = hsv[:, :, 0].astype(float)
paint = cv2.erode(mat_mask({'paint'}).astype(np.uint8), np.ones((9, 9), np.uint8)) > 0
paint &= region
vref = float(np.median(V[paint])) if paint.sum() > 100 else float(np.percentile(V[region], 75))
p_dark = V < 0.42 * vref
red = ((Hh <= 12) | (Hh >= 165)) & (S > 110) & (V > 50)
amber = (Hh > 8) & (Hh <= 28) & (S > 110) & (V > 90)
p_lamp = (red | amber) if livery == 'white' else amber
if livery != 'white':
    p_dark &= ~((S > 120) & ((Hh <= 12) | (Hh >= 165)) & (V > 0.25 * vref))


def clean(m, r=2, min_frac=0.0004):
    m = m.astype(np.uint8)
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1))
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, k)
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, k)
    n, cc, st, _ = cv2.connectedComponentsWithStats(m, 8)
    keep = np.zeros(n, bool)
    keep[1:] = st[1:, cv2.CC_STAT_AREA] >= min_frac * width * width
    return keep[cc]


p_dark = clean(p_dark, 3)
p_lamp = clean(p_lamp, 2, 0.0002)
p_dark &= ~p_lamp
m_dark = mat_mask(DARK)
m_lamp = mat_mask(LAMP)


def border(m):
    m8 = m.astype(np.uint8)
    b = (m8 - cv2.erode(m8, k3)) | (cv2.dilate(m8, k3) - m8)
    return (b > 0) & region


res = {}
vis = (img * 0.55).astype(np.uint8)
vis[~region] = (vis[~region] * 0.5).astype(np.uint8)
for cname, pmk, mmk, cp, cm in (('dark', p_dark, m_dark, (0, 255, 255), (255, 0, 255)),
                                ('lamp', p_lamp, m_lamp, (0, 255, 0), (255, 60, 0))):
    pmk = pmk & region
    mmk = mmk & region
    if mmk.sum() < 50 and pmk.sum() < 50:
        continue
    bp, bm = border(pmk), border(mmk)
    if bp.sum() == 0 or bm.sum() == 0:
        res[cname] = {'iou': 0.0, 'mean_pct': 99.0, 'p90_pct': 99.0}
        continue
    dp = cv2.distanceTransform((~bp).astype(np.uint8), cv2.DIST_L2, 5)
    dm = cv2.distanceTransform((~bm).astype(np.uint8), cv2.DIST_L2, 5)
    a, b = dp[bm], dm[bp]
    both = np.concatenate([a, b]) / width * 100
    inter, uni = (pmk & mmk).sum(), (pmk | mmk).sum()
    res[cname] = {'iou': round(float(inter / max(1, uni)), 3), 'mean_pct': round(float(both.mean()), 2),
                  'p90_pct': round(float(np.percentile(both, 90)), 2),
                  'model_to_photo_mean_pct': round(float(a.mean() / width * 100), 2),
                  'photo_to_model_mean_pct': round(float(b.mean() / width * 100), 2)}
    vis[cv2.dilate(bp.astype(np.uint8), k3) > 0] = cp
    vis[cv2.dilate(bm.astype(np.uint8), k3) > 0] = cm
json.dump({'photo': photo, 'livery': livery, 'vref': vref, 'width_px': width, 'classes': res},
          open(os.path.join(out, f'{name}_dark.json'), 'w'), indent=1)
Image.fromarray(vis).save(os.path.join(out, f'{name}_dark.png'))
print(name, json.dumps(res))
