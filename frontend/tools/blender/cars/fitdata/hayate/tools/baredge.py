"""r03: the white bar's lower edge above the lamp (photo: per column, the first bright pixel going up from the lamp's
top) vs the model's groove (ids: the lowest 'trim' or 'paint' pixel above the lamp's bezel)"""
import json, sys, numpy as np
from PIL import Image
rdir = sys.argv[1]
ph = 'r03'
photo = np.array(Image.open(f'../photos_hi/{ph}.jpg').convert('L').resize((1600, 979), Image.LANCZOS)).astype(float)
pal = json.load(open(f'{rdir}/palette.json')); names = sorted(pal); cols = np.array([pal[k] for k in names], float)
ids = np.array(Image.open(f'{rdir}/{ph}_ids.png').convert('RGBA'))
lab = np.argmin(((ids[:, :, :3].reshape(-1, 3).astype(float)[:, None, :] - cols[None]) ** 2).sum(-1), 1).reshape(ids.shape[:2])
lab[ids[:, :, 3] < 128] = -1
db = json.load(open('lamps.json'))['photos'][ph]
import cv2
tm = np.zeros(photo.shape, np.uint8); cv2.fillPoly(tm, [np.round(np.array(db['bl_N']['poly']) * 4).astype(np.int32)], 1, shift=2)
lm = np.isin(lab, [names.index('amber'), names.index('headlight')])
out = []
for x in range(680, 861, 20):
    t = np.nonzero(tm[:, x])[0]
    y = t.min() - 1
    while y > 600 and photo[y, x] < 150:
        y -= 1
    pe = y + 0.5
    m = np.nonzero(lm[:, x])[0]
    if not len(m):
        continue
    y = m.min() - 1
    while y > 600 and lab[y, x] not in (names.index('trim'), names.index('paint'), names.index('accent')):
        y -= 1
    # skip the bezel (trim right above the lens): go up through trim to the accent/paint above, then find the groove
    while y > 600 and lab[y, x] == names.index('trim'):
        y -= 1
    while y > 600 and lab[y, x] != names.index('trim') and lab[y, x] != names.index('paint'):
        y -= 1
    me = y + 0.5
    out.append((x, pe, me, t.min(), m.min()))
    print(f'x {x}: photo bar edge {pe:.1f}  lamp top {t.min()}  gap {t.min() - pe:.1f} | model groove/white edge {me:.1f}  lamp top {m.min()}  gap {m.min() - me:.1f} | bar dy model-photo {me - pe:+.1f}')
o = np.array(out)
print(f'median bar dy (model - photo) {np.median(o[:, 2] - o[:, 1]):+.1f} px; lamp top dy {np.median(o[:, 4] - o[:, 3]):+.1f} px')
