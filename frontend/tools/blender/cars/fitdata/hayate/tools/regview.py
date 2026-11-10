"""regview.py <rdir> <out>: per photo (r03, n06): the photo crop with the traced lamp (green) and the model's lamp
lenses (magenta) in the solved camera, the same after the bumper registration (shift from regfit.REG), and the bumper's
own edges (cyan: the model's bar groove / trim, the TRUENO letters) in both"""
import json, sys, cv2, numpy as np
from PIL import Image, ImageDraw, ImageFont
rdir, out = sys.argv[1:3]
REG = {'r03': {'dy': 27.5, 'truo': (448, -70.0), 'wheel': 1060, 'box': (600, 660, 960, 800)},
       'n06': {'dy': 22.0, 'truo': (256, -42.0), 'wheel': 795, 'box': (200, 700, 580, 800)}}
db = json.load(open('lamps.json'))
pal = json.load(open(f'{rdir}/palette.json')); names = sorted(pal); cols = np.array([pal[k] for k in names], float)
font = ImageFont.load_default(size=18)
rows = []
for ph, R in REG.items():
    ids = np.array(Image.open(f'{rdir}/{ph}_ids.png').convert('RGBA'))
    H, W = ids.shape[:2]
    lab = np.argmin(((ids[:, :, :3].reshape(-1, 3).astype(float)[:, None, :] - cols[None]) ** 2).sum(-1), 1).reshape(H, W)
    lab[ids[:, :, 3] < 128] = -1
    x0, y0, x1, y1 = R['box']
    S = 1180 / 2 / (x1 - x0)
    src = np.array(Image.open(f'../photos_hi/{ph}.jpg').convert('RGB'))
    k = src.shape[1] / W
    crop = cv2.resize(src[int(y0 * k):int(y1 * k), int(x0 * k):int(x1 * k)], (int((x1 - x0) * S), int((y1 - y0) * S)), interpolation=cv2.INTER_AREA)
    lens = np.isin(lab, [names.index('amber'), names.index('headlight')]).astype(np.uint8)
    roi = np.zeros_like(lens); roi[y0:y1, x0:x1] = 1
    lens &= roi
    # the bumper's own features: the groove (trim) above the lamp, the TRUENO letters (rim, near the face's centre)
    feat = ((lab == names.index('trim')) | (lab == names.index('rim'))).astype(np.uint8) & roi
    yy, xx = np.nonzero(lens)
    xc = xx.mean() if len(xx) else (x0 + x1) / 2
    xt, dxt = R['truo']
    M = np.float32([[1, 0, dxt * (R['wheel'] - xc) / (R['wheel'] - xt)], [0, 1, R['dy']]])
    panels = []
    for reg in (False, True):
        im = crop.copy()
        for m, col in ((feat, (0, 220, 255)), (lens, (255, 0, 255))):
            mm = cv2.warpAffine(m, M, (W, H), flags=cv2.INTER_NEAREST) if reg else m
            cs, _ = cv2.findContours(mm[y0:y1, x0:x1].copy(), cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)
            cs = [np.round((c.astype(float) + 0.5) * S).astype(np.int32) for c in cs if cv2.contourArea(c) > 4]
            cv2.drawContours(im, cs, -1, col, 1, cv2.LINE_AA)
        for lamp in ('ba_N', 'bc_N'):
            q = np.round((np.array(db['photos'][ph][lamp]['poly']) - [x0, y0]) * S).astype(np.int32)
            cv2.polylines(im, [q], True, (0, 255, 0), 2, cv2.LINE_AA)
        p = Image.fromarray(im)
        d = ImageDraw.Draw(p)
        t = f'{ph}: solved camera' if not reg else f'{ph}: moved by the bumper\'s own offset ({M[0, 2]:+.0f}, {M[1, 2]:+.0f}) px'
        d.rectangle((0, 0, 9 * len(t) + 10, 24), fill=(0, 0, 0))
        d.text((5, 2), t, fill=(255, 255, 255), font=font)
        panels.append(np.array(p))
    rows.append(np.concatenate([panels[0], np.full((panels[0].shape[0], 8, 3), 255, np.uint8), panels[1]], 1))
w = max(r.shape[1] for r in rows)
Image.fromarray(np.concatenate([np.pad(r, ((0, 8), (0, w - r.shape[1]), (0, 0)), constant_values=255) for r in rows], 0)).save(out)
