"""ovl.py <photo> <rdir> <lamps.json> <ph> <lamp> <x0,y0,x1,y1> <out.png> [--scale 2] [--rdir2 dir]: zoomed overlay of
one lamp: photo with the trace (green) and the model's lamp region outline from the id render (magenta; --rdir2: a
second render dir in cyan)"""
import json, sys
import cv2
import numpy as np
from PIL import Image
a = sys.argv[1:]
photo, rdir, lj, ph, lamp, box, out = a[:7]
S = float(a[a.index('--scale') + 1]) if '--scale' in a else 2.0
x0, y0, x1, y1 = (int(v) for v in box.split(','))
L = json.load(open(lj))
kinds = L['kinds'][lamp.split('_')[0]]
img = np.array(Image.open(photo).convert('RGB'))
crop = cv2.resize(img[y0:y1, x0:x1], (int((x1 - x0) * S), int((y1 - y0) * S)), interpolation=cv2.INTER_CUBIC)
poly = np.array(L['photos'][ph][lamp]['poly'])
cv2.polylines(crop, [np.round((poly - [x0, y0]) * S).astype(np.int32)], True, (0, 255, 0), 1, cv2.LINE_AA)


def model(rd, col):
    pal = json.load(open(rd + '/palette.json'))
    ids = np.array(Image.open(f'{rd}/{ph}_ids.png').convert('RGB')).astype(int)
    m = np.zeros(ids.shape[:2], np.uint8)
    for k in kinds:
        m |= (np.abs(ids - np.array(pal[k])).sum(-1) < 6).astype(np.uint8)
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))[y0:y1, x0:x1]
    m = cv2.resize(m, (crop.shape[1], crop.shape[0]), interpolation=cv2.INTER_NEAREST)
    cs, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    cv2.drawContours(crop, cs, -1, col, 1, cv2.LINE_AA)


model(rdir, (255, 0, 255))
if '--rdir2' in a:
    model(a[a.index('--rdir2') + 1], (0, 255, 255))
Image.fromarray(crop).save(out)
