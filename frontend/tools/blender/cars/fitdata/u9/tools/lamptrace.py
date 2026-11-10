"""
lamptrace.py: a lamp's outline on a photo of a red U9 by colour, inside a loose hand-drawn region: the lens (dark smoked
glass, chrome borders, LEDs) is whatever is not the red paint; holes (reflections) are filled and the largest piece kept.
The result goes into lamps.json after a look at the check crop (outline in green over the photo).

  py lamptrace.py <photo> "<x,y;x,y;...> (region)" <out.json> <check.png> [--key hl_R] [--red 1.5] [--min 55]
      [--close 5] [--n 48] [--add "x,y;..." (a region forced into the lens: a chrome border the colour test misses)]
"""
import json, sys

import cv2
import numpy as np
from PIL import Image, ImageDraw

a = sys.argv[1:]
photo, roi_s, outp, chk = a[:4]


def opt(k, d=None):
    return a[a.index(k) + 1] if k in a else d


key = opt('--key', 'lamp')
im = np.asarray(Image.open(photo).convert('RGB')).astype(np.float32)
H, W = im.shape[:2]
roi = np.array([[float(v) for v in p.split(',')] for p in roi_s.split(';') if p])
m_roi = np.zeros((H, W), np.uint8)
cv2.fillPoly(m_roi, [np.round(roi).astype(np.int32)], 1)
R, G, B = im[..., 0], im[..., 1], im[..., 2]
red = (R > float(opt('--red', '1.5')) * np.maximum(G, B)) & (R > float(opt('--min', '55')))
lens = (~red).astype(np.uint8) & m_roi
if opt('--add'):
    cv2.fillPoly(lens, [np.round([[float(v) for v in p.split(',')] for p in opt('--add').split(';') if p]).astype(np.int32)], 1)
k = int(opt('--close', '5'))
lens = cv2.morphologyEx(lens, cv2.MORPH_CLOSE, np.ones((k, k), np.uint8))
lens = cv2.morphologyEx(lens, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
n, lab, st, _ = cv2.connectedComponentsWithStats(lens)
big = 1 + int(np.argmax(st[1:, cv2.CC_STAT_AREA]))
m = (lab == big).astype(np.uint8)
cs, hier = cv2.findContours(m, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
# fill the holes that are small (reflections), keep the large one (the blade inside a ring-shaped lamp) as is
outer = max(range(len(cs)), key=lambda i: cv2.contourArea(cs[i]) if hier[0][i][3] < 0 else -1)
c = cs[outer][:, 0, :].astype(float)
nn = int(opt('--n', '48'))
L = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(np.vstack([c, c[:1]]), axis=0), axis=1))])
s = np.linspace(0, L[-1], nn, endpoint=False)
pts = [[round(float(np.interp(t, L, np.append(c[:, 0], c[0, 0]))), 1),
        round(float(np.interp(t, L, np.append(c[:, 1], c[0, 1]))), 1)] for t in s]
# keep corners: add the contour points of highest turning (approxPolyDP) too
ap = cv2.approxPolyDP(cs[outer], 2.0, True)[:, 0, :]
res = json.load(open(outp)) if outp and __import__('os').path.exists(outp) else {}
res[key] = {'poly': [[float(x), float(y)] for x, y in ap], 'area': float(m.sum())}
json.dump(res, open(outp, 'w'), indent=1)
x0, y0 = roi.min(0) - 15
x1, y1 = roi.max(0) + 15
crop = Image.open(photo).convert('RGB')
d = ImageDraw.Draw(crop)
d.line([tuple(p) for p in ap.tolist()] + [tuple(ap[0].tolist())], fill=(0, 255, 0), width=1)
d.line([tuple(p) for p in roi.tolist()] + [tuple(roi[0].tolist())], fill=(255, 255, 0), width=1)
crop = crop.crop((int(x0), int(y0), int(x1), int(y1)))
crop = crop.resize((crop.width * 3, crop.height * 3), Image.NEAREST)
crop.save(chk)
print(key, 'points', len(ap), 'area', int(m.sum()))
