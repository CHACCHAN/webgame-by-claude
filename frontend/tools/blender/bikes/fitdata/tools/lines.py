"""lines.py <photo> <sil.png> <ids.png> <out.png> [crop x0,y0,x1,y1] [scale]: the photo with the model's outline (red)
and material borders (yellow) drawn on it, no masks"""
import sys
import cv2, numpy as np
from PIL import Image
ph = np.array(Image.open(sys.argv[1]).convert('RGB')).astype(np.float32)
h, w = ph.shape[:2]
S = np.array(Image.open(sys.argv[2]).convert('RGBA').resize((w, h), Image.NEAREST))[:, :, 3] > 127
L = np.array(Image.open(sys.argv[3]).convert('RGBA').resize((w, h), Image.NEAREST)).astype(np.int32)
c = L[:, :, :3]; a = L[:, :, 3] > 127
lm = np.zeros((h, w), bool)
dx = np.abs(c[:, 1:] - c[:, :-1]).sum(axis=2) > 24
dy = np.abs(c[1:] - c[:-1]).sum(axis=2) > 24
lm[:, 1:] |= dx & a[:, 1:] & a[:, :-1]
lm[1:] |= dy & a[1:] & a[:-1]
s8 = S.astype(np.uint8)
ol = (s8 - cv2.erode(s8, np.ones((3, 3), np.uint8))).astype(bool)
out = ph * 0.85
out[lm] = [255, 235, 40]
out[cv2.dilate(ol.astype(np.uint8), np.ones((2, 2), np.uint8)).astype(bool)] = [255, 40, 40]
im = Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))
if len(sys.argv) > 5 and sys.argv[5] != '-':
    im = im.crop(tuple(int(v) for v in sys.argv[5].split(',')))
if len(sys.argv) > 6:
    k = float(sys.argv[6]); im = im.resize((int(im.size[0] * k), int(im.size[1] * k)), Image.LANCZOS)
im.save(sys.argv[4])
