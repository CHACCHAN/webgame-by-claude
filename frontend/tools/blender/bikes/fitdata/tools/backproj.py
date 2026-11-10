"""backproj.py <cams.json> <name> <pts.json> : image points → game frame on planes. pts.json: {"label": [u, v, "x=-0.2" | "z=0.5" | "y=0.3"], ...}
prints label, (x, y, z)"""
import json, math, sys, os
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bsolve as S
C = json.load(open(sys.argv[1])); cam = C['cams'][sys.argv[2]]; W, H = cam[7]
P = json.load(open(sys.argv[3]))
Cc = np.array(cam[:3]); d, r, u = S.basis(*cam[3:6]); f = cam[6]
out = {}
for k, (uu, vv, plane) in P.items():
    ray = S.basis(*cam[3:6])
    dirv = d + r * (uu - W / 2) / f + u * (H / 2 - vv) / f
    ax, val = plane.split('='); i = 'xyz'.index(ax); val = float(val)
    t = (val - Cc[i]) / dirv[i]
    p = Cc + dirv * t
    out[k] = [round(float(v), 3) for v in p]
    print(f'{k:14s} x {p[0]:+.3f} y {p[1]:.3f} z {p[2]:+.3f}')
json.dump(out, open(sys.argv[3].replace('.json', '_3d.json'), 'w'), indent=0)
