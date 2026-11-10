"""regfit.py <rdir> [<rdir> ...]: the bumper lamps' IoU after registering the solved camera on the bumper itself (not on
the lamp): a shift by the offset of the bar's lower edge (vertical) and of the TRUENO letters at the face's centre,
falling to zero at the near front wheel (the cameras' anchor), at the lamp (horizontal); both measured on the model's
own bumper vs the photo (ba/baredge.py, ba/truoff.py)"""
import json, sys, cv2, numpy as np
from PIL import Image
REG = {'r03': {'dy': 27.5, 'truo': (448, -70.0), 'wheel': 1060},
       'n06': {'dy': 22.0, 'truo': (256, -42.0), 'wheel': 795}}
db = json.load(open('lamps.json'))
kinds = db['kinds']
for rdir in sys.argv[1:]:
    pal = json.load(open(f'{rdir}/palette.json')); names = sorted(pal); cols = np.array([pal[k] for k in names], float)
    for ph, R in REG.items():
        ids = np.array(Image.open(f'{rdir}/{ph}_ids.png').convert('RGBA'))
        H, W = ids.shape[:2]
        lab = np.argmin(((ids[:, :, :3].reshape(-1, 3).astype(float)[:, None, :] - cols[None]) ** 2).sum(-1), 1).reshape(H, W)
        lab[ids[:, :, 3] < 128] = -1
        for lamp in ('ba_N', 'bc_N', 'bl_N'):
            poly = np.array(db['photos'][ph][lamp]['poly'])
            tm = np.zeros((H, W), np.uint8); cv2.fillPoly(tm, [np.round(poly * 4).astype(np.int32)], 1, shift=2)
            x0, y0 = poly.min(0) - 80; x1, y1 = poly.max(0) + 80
            roi = np.zeros((H, W), bool); roi[int(y0):int(y1), int(x0):int(x1)] = True
            mm = (np.isin(lab, [names.index(k) for k in kinds[lamp[:2]] if k in names]) & roi).astype(np.uint8)
            if not mm.any():
                print(f'{rdir} {ph} {lamp}: no model lens'); continue
            yy, xx = np.nonzero(mm)
            xc = xx.mean()
            xt, dxt = R['truo']
            # dxt, dy: photo - model (the model is moved onto the photo); dx falls off linearly to the wheel
            M = np.float32([[1, 0, dxt * (R['wheel'] - xc) / (R['wheel'] - xt)], [0, 1, R['dy']]])
            sh = cv2.warpAffine(mm, M, (W, H), flags=cv2.INTER_NEAREST) > 0
            raw = mm > 0; t = tm > 0
            iou0 = (raw & t).sum() / max(1, (raw | t).sum())
            iou1 = (sh & t).sum() / max(1, (sh | t).sum())
            print(f'{rdir} {ph} {lamp}: shift ({M[0, 2]:+.1f}, {M[1, 2]:+.1f}) px  IoU raw {iou0:.3f}  registered {iou1:.3f}')
