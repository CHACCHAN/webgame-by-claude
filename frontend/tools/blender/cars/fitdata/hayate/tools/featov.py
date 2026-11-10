"""featov.py <photo_hi> <rdir> <ph> <x0,y0,x1,y1> <scale> <out>: outlines of single materials of the model (same solved
camera) over the photo: trim (cyan), amber (orange), headlight (green), plate (yellow), paint (magenta), silhouette (white)"""
import json, sys, cv2, numpy as np
from PIL import Image
ph_hi, rdir, ph, box, S, out = sys.argv[1:7]
S = float(S)
x0, y0, x1, y1 = (int(v) for v in box.split(','))
ids = np.array(Image.open(f'{rdir}/{ph}_ids.png').convert('RGBA'))
H, W = ids.shape[:2]
pal = json.load(open(f'{rdir}/palette.json')); names = sorted(pal); cols = np.array([pal[k] for k in names], float)
lab = np.argmin(((ids[:, :, :3].reshape(-1, 3).astype(float)[:, None, :] - cols[None]) ** 2).sum(-1), 1).reshape(H, W)
sil = ids[:, :, 3] > 127
lab[~sil] = -1
src = np.array(Image.open(ph_hi).convert('RGB'))
k = src.shape[1] / W
ow, oh = int((x1 - x0) * S), int((y1 - y0) * S)
ov = cv2.resize(src[int(y0 * k):int(y1 * k), int(x0 * k):int(x1 * k)], (ow, oh), interpolation=cv2.INTER_AREA)
for name, col in (('paint', (255, 0, 255)), ('trim', (0, 230, 255)), ('plate', (255, 255, 0)), ('amber', (255, 140, 0)), ('headlight', (0, 255, 0))):
    if name not in names:
        continue
    m = (lab[y0:y1, x0:x1] == names.index(name)).astype(np.uint8)
    m = cv2.resize(m, (ow, oh), interpolation=cv2.INTER_NEAREST)
    cs, _ = cv2.findContours(m, cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)
    cs = [c for c in cs if cv2.contourArea(c) > 30 * S * S]
    cv2.drawContours(ov, cs, -1, col, 1, cv2.LINE_AA)
m = cv2.resize(sil[y0:y1, x0:x1].astype(np.uint8), (ow, oh), interpolation=cv2.INTER_NEAREST)
cs, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
cv2.drawContours(ov, cs, -1, (255, 255, 255), 1, cv2.LINE_AA)
Image.fromarray(ov).save(out)
