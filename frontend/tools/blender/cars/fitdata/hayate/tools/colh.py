"""per column: the model lamp's vertical extent (ids render, given materials) vs the traced lens (lamps.json) -> real
height estimate = model height * photo px / model px"""
import json, sys, cv2, numpy as np
from PIL import Image
rdir, ph, lamp, mats, hm = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4].split(','), float(sys.argv[5])
ids = np.array(Image.open(f'{rdir}/{ph}_ids.png').convert('RGBA'))
H, W = ids.shape[:2]
pal = json.load(open(f'{rdir}/palette.json')); names = sorted(pal); cols = np.array([pal[k] for k in names], float)
lab = np.argmin(((ids[:, :, :3].reshape(-1, 3).astype(float)[:, None, :] - cols[None]) ** 2).sum(-1), 1).reshape(H, W)
lab[ids[:, :, 3] < 128] = -1
poly = np.array(json.load(open('lamps.json'))['photos'][ph][lamp]['poly'])
tm = np.zeros((H, W), np.uint8); cv2.fillPoly(tm, [np.round(poly * 4).astype(np.int32)], 1, shift=2)
x0, x1 = int(poly[:, 0].min()), int(poly[:, 0].max())
y0, y1 = int(poly[:, 1].min()) - 40, int(poly[:, 1].max()) + 40
mm = np.isin(lab, [names.index(m) for m in mats if m in names])
mm[:y0] = False; mm[y1:] = False
out = []
for x in range(x0, x1 + 1):
    t = np.nonzero(tm[:, x])[0]; m = np.nonzero(mm[:, x])[0]
    if len(t) > 3 and len(m) > 3:
        out.append((x, t.min(), t.max() - t.min() + 1, m.min(), m.max() - m.min() + 1))
o = np.array(out, float)
if len(o):
    print(f'{rdir} {ph} {lamp}: cols {len(o)}  photo h {np.median(o[:,2]):.1f}px  model h {np.median(o[:,4]):.1f}px  top offset (model-photo) {np.median(o[:,3]-o[:,1]):+.1f}px  -> real h {hm*np.median(o[:,2]/o[:,4]):.3f} m')
else:
    print(rdir, ph, lamp, 'no overlap columns')
