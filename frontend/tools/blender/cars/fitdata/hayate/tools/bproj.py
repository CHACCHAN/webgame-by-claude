"""bproj.py <cams.json> <photo> <plane: x=0 | z=val | y=val> px,py ... : back-project image points onto a game-frame plane
(body frame: the photo's body pose undone)"""
import sys, json, math
import numpy as np
c = json.load(open(sys.argv[1]))
n = sys.argv[2]
cam = c['cams'][n]
W, H = cam[7]
pose = c.get('pose', {}).get(n, {'dy': 0, 'pitch_deg': 0})
dy, th = pose['dy'], math.radians(pose['pitch_deg'])
yaw, pitch, roll = cam[3:6]
d = np.array([math.sin(yaw) * math.cos(pitch), math.sin(pitch), math.cos(yaw) * math.cos(pitch)])
r = np.cross(d, [0, 1, 0]); r /= np.linalg.norm(r)
u = np.cross(r, d)
cr, sr = math.cos(roll), math.sin(roll)
r, u = cr * r + sr * u, -sr * r + cr * u
f = cam[6]
C = np.array(cam[:3])
ax, val = sys.argv[3].split('=')
k = 'xyz'.index(ax)
val = float(val)
for s in sys.argv[4:]:
    px, py = (float(v) for v in s.split(','))
    ray = d + (px - W / 2) / f * r - (py - H / 2) / f * u
    # ground frame plane test in the body frame: transform the ray into the body frame
    # ground = Rth body + (0,dy,0)  ->  body = Rth^T (ground - (0,dy,0))
    ct, st = math.cos(th), math.sin(th)
    Rth = np.array([[1, 0, 0], [0, ct, st], [0, -st, ct]])
    Cb = Rth.T @ (C - np.array([0, dy, 0]))
    rb = Rth.T @ ray
    t = (val - Cb[k]) / rb[k]
    P = Cb + t * rb
    print(s, '->', np.round(P, 3).tolist())
