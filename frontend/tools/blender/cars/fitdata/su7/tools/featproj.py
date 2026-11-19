"""featproj.py <cams.json> <feats.json>: where each feature's design point (field ignored, <= 2 cm) falls in each photo,
against the observed pixel: dx, dy in px."""
import json
import math
import sys

import numpy as np

C = json.load(open(sys.argv[1]))
F = json.load(open(sys.argv[2]))


def basis(yaw, pitch, roll):
    d = np.array([math.sin(yaw) * math.cos(pitch), math.sin(pitch), math.cos(yaw) * math.cos(pitch)])
    r = np.cross(d, [0, 1, 0])
    r /= np.linalg.norm(r)
    u = np.cross(r, d)
    c, s = math.cos(roll), math.sin(roll)
    return d, c * r + s * u, -s * r + c * u


def proj(c, p):
    d, r, u = basis(*c[3:6])
    W, H = c[7]
    q = np.asarray(p) - np.asarray(c[:3])
    z = q @ d
    return W / 2 + c[6] * (q @ r) / z, H / 2 - c[6] * (q @ u) / z


for name, fv in F.items():
    if name.startswith('_'):
        continue
    for key, xy in fv['obs'].items():
        ph, m = (key.split(':') + [''])[:2]
        p = np.array(fv['design']) * ([-1, 1, 1] if m else [1, 1, 1])
        x, y = proj(C['cams'][ph], p)
        print(f'{name:8s} {key:6s} model ({x:7.1f}, {y:6.1f})  photo ({xy[0]:7.1f}, {xy[1]:6.1f})  d ({xy[0] - x:+6.1f}, {xy[1] - y:+6.1f})')
