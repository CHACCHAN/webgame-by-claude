"""camcheck.py <annot.json> <cams.json> <name> <photo> <out.png> [crop x0,y0,x1,y1]: draw the solved wheel circles
(rim lip, tyre outer at the centre plane), the steering axis and the bike's ground box on the photo"""
import json, math, sys, os
import numpy as np
from PIL import Image, ImageDraw
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bsolve as S
A = json.load(open(sys.argv[1])); C = json.load(open(sys.argv[2])); n = sys.argv[3]
bk = A['_bike']; cam = C['cams'][n]; W, H = cam[7]; st = C['steer'][n]
im = Image.open(sys.argv[4]).convert('RGB'); d = ImageDraw.Draw(im)
def poly(P, col, w=2):
    uv = S.project(cam, np.array(P), W, H); d.line([tuple(p) for p in uv] + [tuple(uv[0])], fill=col, width=w)
Pf, nf = S.steer_frame(bk, st)
Pr, nr = np.array([0, bk['rr'], -bk['wb'] / 2]), np.array([1.0, 0, 0])
for P, nn, R in ((Pf, nf, bk['rf']), (Pr, nr, bk['rr'])):
    poly(S.circle(P, nn, R), (0, 255, 0))
    poly(S.circle(P - nn * 0.05, nn, bk['rho']), (255, 0, 255), 1)
r = math.radians(bk['rake_deg']); a = np.array([0, math.cos(r), -math.sin(r)]); A0 = np.array([0, 0, bk['wb'] / 2 + bk['trail']])
uv = S.project(cam, np.array([A0, A0 + a * 1.1]), W, H); d.line([tuple(p) for p in uv], fill=(255, 255, 0), width=2)
g = [[0.3, 0, -1.0], [0.3, 0, 1.0], [-0.3, 0, 1.0], [-0.3, 0, -1.0]]
poly(g, (0, 200, 255), 1)
for y in (0.5, 0.775, 1.06):
    uv = S.project(cam, np.array([[0, y, -1.0], [0, y, 1.0]]), W, H); d.line([tuple(p) for p in uv], fill=(255, 128, 0), width=1)
if len(sys.argv) > 6:
    im = im.crop(tuple(int(v) for v in sys.argv[6].split(',')))
im.save(sys.argv[5])
