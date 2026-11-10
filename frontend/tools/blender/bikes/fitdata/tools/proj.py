"""proj.py <cams.json> <name> x,y,z [x,y,z ...] : project game points to pixels (also prints the local px/m along x, y, z)"""
import json, sys, os
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bsolve as S
C = json.load(open(sys.argv[1])); cam = C['cams'][sys.argv[2]]; W, H = cam[7]
for a in sys.argv[3:]:
    p = np.array([float(v) for v in a.split(',')])
    uv = S.project(cam, p[None], W, H)[0]
    d = [S.project(cam, (p + e * 0.1)[None], W, H)[0] - uv for e in np.eye(3)]
    print(f'{a:22s} -> ({uv[0]:7.1f}, {uv[1]:7.1f})   per 10cm: x {d[0].round(1)} y {d[1].round(1)} z {d[2].round(1)}')
