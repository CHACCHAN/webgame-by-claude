"""livpoly.py <bike> <photo> <livdir> <regions: key=obj[,key=obj..]> : picked livery contours → side polygons (z, y)
per region (points that hit another part are put on the plane x = xplane by the camera ray). Writes <livdir>/poly.json
and a plot."""
import sys, json, math
import numpy as np
from PIL import Image, ImageDraw
B = '/home/dev/.local/opt/carfit/bikes'
bike, ph, ld = sys.argv[1:4]
C = json.load(open(f'{B}/{bike}/fit/cams.json'))['cams'][ph]
P = json.load(open(f'{ld}/picked.json')); pts = json.load(open(f'{ld}/pts.json'))
W, H = C[7]; f = C[6]
yaw, pitch, roll = C[3:6]
d = np.array([math.sin(yaw) * math.cos(pitch), math.sin(pitch), math.cos(yaw) * math.cos(pitch)])
r = np.cross(d, [0, 1, 0]); r /= np.linalg.norm(r); u = np.cross(r, d)
c, s = math.cos(roll), math.sin(roll); r, u = c * r + s * u, -s * r + c * u
eye = np.array(C[:3])
out = {}
for spec in sys.argv[4].split(','):
    key, obj, xp = spec.split('=')
    xp = float(xp)
    poly = []
    for (pu, pv), hit in zip(pts[key], P[key]):
        if hit and hit['obj'] == obj:
            p = hit['p']
        else:
            g = d + ((pu - W / 2) / f) * r - ((pv - H / 2) / f) * u
            t = (xp - eye[0]) / g[0]
            p = list(eye + t * g)
        poly.append([round(p[2], 4), round(p[1], 4), round(p[0], 4)])
    out[key] = poly
json.dump(out, open(f'{ld}/poly.json', 'w'))
im = Image.new('RGB', (1400, 700), 'white'); dr = ImageDraw.Draw(im)
T = lambda z, y: (700 - z * 600, 650 - y * 600)
for gx in np.arange(-1.0, 1.01, 0.1):
    dr.line([T(gx, 0), T(gx, 1.1)], fill=(220, 220, 220)); dr.text(T(gx, 0), f'{gx:.1f}', fill=(0, 0, 0))
for gy in np.arange(0, 1.11, 0.1):
    dr.line([T(-1.0, gy), T(1.0, gy)], fill=(220, 220, 220)); dr.text(T(1.0, gy), f'{gy:.1f}', fill=(0, 0, 0))
cols = [(220, 30, 30), (30, 60, 220), (30, 140, 30), (200, 120, 0), (150, 0, 150), (0, 150, 150)]
for i, (k, p) in enumerate(out.items()):
    dr.line([T(z, y) for z, y, x in p] + [T(p[0][0], p[0][1])], fill=cols[i % 6], width=2)
    dr.text(T(*p[0][:2]), k, fill=cols[i % 6])
im.save(f'{ld}/poly.png')
