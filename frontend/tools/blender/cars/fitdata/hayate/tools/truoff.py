"""the model's TRUENO letters ('rim' pixels near the face centre in the ids render) against the photo's TRUENO box"""
import json, sys, numpy as np
from PIL import Image
rdir = sys.argv[1]
boxes = {'r03': (402.5, 691, 492.5, 721), 'n06': (232.5, 742.5, 280, 760)}
pal = json.load(open(f'{rdir}/palette.json')); names = sorted(pal); cols = np.array([pal[k] for k in names], float)
for ph, (x0, y0, x1, y1) in boxes.items():
    ids = np.array(Image.open(f'{rdir}/{ph}_ids.png').convert('RGBA'))
    lab = np.argmin(((ids[:, :, :3].reshape(-1, 3).astype(float)[:, None, :] - cols[None]) ** 2).sum(-1), 1).reshape(ids.shape[:2])
    lab[ids[:, :, 3] < 128] = -1
    m = lab == names.index('rim')
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    win = np.zeros_like(m); win[int(cy - 60):int(cy + 40), int(cx - 60):int(cx + 140)] = True
    yy, xx = np.nonzero(m & win)
    print(f'{ph}: photo TRUENO centre ({cx:.0f}, {cy:.0f}) w {x1 - x0:.0f} h {y1 - y0:.0f}; model letters centre ({xx.mean():.0f}, {yy.mean():.0f}) '
          f'w {xx.max() - xx.min() + 1} h {yy.max() - yy.min() + 1} -> offset model - photo ({xx.mean() - cx:+.0f}, {yy.mean() - cy:+.0f}) px')
