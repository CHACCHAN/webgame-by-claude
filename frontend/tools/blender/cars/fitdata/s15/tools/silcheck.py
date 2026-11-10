"""silcheck.py <maskdir> <rdir_before> <rdir_after> ph,ph,...: silhouette IoU against the photo masks (valid where the
mask is clearly in or out) before / after, and the pixels that changed"""
import sys
import numpy as np
from PIL import Image
md, r0, r1, phs = sys.argv[1:5]
for p in phs.split(','):
    m = np.array(Image.open(f'{md}/{p}.png').convert('L'))
    a = np.array(Image.open(f'{r0}/{p}_sil.png'))[..., 3] > 127
    b = np.array(Image.open(f'{r1}/{p}_sil.png'))[..., 3] > 127
    if m.shape != a.shape:
        m = np.array(Image.fromarray(m).resize((a.shape[1], a.shape[0])))
    v = (m < 50) | (m > 200)
    t = m > 127

    def iou(s):
        return ((s & t) & v).sum() / max(1, ((s | t) & v).sum())
    print(f'{p}: IoU {iou(a):.4f} -> {iou(b):.4f}   changed px {int((a ^ b).sum())}')
