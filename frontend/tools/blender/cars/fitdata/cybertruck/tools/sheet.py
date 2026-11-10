"""
sheet.py <compare_dir> <out.png> [--table silfit.txt] [--lamps lampfit.json] [--title text] [--note text]...
The owner's sheet for the cybertruck, 1200 px wide: photo | render pairs from the solved cameras (compare.py), the lamp
close-ups (photo crop with the tracing in green | render crop with the model's lamp outline in red, and the numbers),
the silhouette table. env PAIRS (default p22,p23,p16,p169,p120,p150), LAMPCROPS (photo:x0,y0,x1,y1 list).
"""
import json, math, os, sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, '..', '..', '..')))
sys.dont_write_bytecode = True
import cybertruck_shape as CS  # noqa: E402
import cybertruck_parts as PT  # noqa: E402

a = sys.argv[1:]
cd, out = a[0], a[1]


def opt(k, d=None):
    return a[a.index(k) + 1] if k in a else d


notes = [a[i + 1] for i, v in enumerate(a) if v == '--note']
W = 1200
font = ImageFont.load_default(size=22)
small = ImageFont.load_default(size=15)
FD = os.path.abspath(os.path.join(HERE, '..'))
fit = json.load(open(os.path.join(FD, 'shape.json')))
P = CS.load()
S = CS.Shape(P)
LO = PT.lamp_outlines(P, S)
TR = json.load(open(os.path.join(FD, 'lamps.json')))
LR = json.load(open(opt('--lamps'))) if opt('--lamps') else {}
credits = {e['file'].split('.')[0]: f"{e['author']}, {e['licence']}" for e in json.load(open(os.path.join(FD, 'ref', 'list.json')))}


def label(im, text, xy=(0, 0)):
    d = ImageDraw.Draw(im)
    w = d.textlength(text, font=small)
    d.rectangle((xy[0], xy[1], xy[0] + w + 10, xy[1] + 20), fill=(0, 0, 0))
    d.text((xy[0] + 5, xy[1] + 2), text, fill='white', font=small)


def basis(yaw, pitch, roll):
    d = np.array([math.sin(yaw) * math.cos(pitch), math.sin(pitch), math.cos(yaw) * math.cos(pitch)])
    r = np.cross(d, [0, 1, 0]); r /= np.linalg.norm(r)
    u = np.cross(r, d)
    c, s = math.cos(roll), math.sin(roll)
    return d, c * r + s * u, -s * r + c * u


def project(ph, X):
    cam, pose = fit['cams'][ph], fit['pose'].get(ph, {})
    X = np.asarray(X, float).copy()
    dy, th = pose.get('dy', 0.0), math.radians(pose.get('pitch_deg', 0.0))
    c, s = math.cos(th), math.sin(th)
    y, z = X[:, 1].copy(), X[:, 2].copy()
    X[:, 1] = c * y + s * z + dy
    X[:, 2] = -s * y + c * z
    x0, y0, z0, yaw, pitch, roll, f = cam[:7]
    Wc, Hc = cam[7]
    d, r, u = basis(yaw, pitch, roll)
    Q = X - np.array([x0, y0, z0])
    zc = Q @ d
    return np.stack([Wc / 2 + f * (Q @ r) / zc, Hc / 2 - f * (Q @ u) / zc], axis=-1)


rows = []
title = Image.new('RGB', (W, 64), 'white')
d = ImageDraw.Draw(title)
d.text((10, 6), opt('--title', 'cybertruck: Tesla Cybertruck (production, 2023-), our own model; photo | render from the solved camera'), fill='black', font=font)
for i, n in enumerate(notes[:1]):
    d.text((10, 36), n, fill=(60, 60, 60), font=small)
rows.append(title)
for n in os.environ.get('PAIRS', 'p22,p23,p16,p169,p120,p150').split(','):
    p = os.path.join(cd, f'{n}_compare.png')
    if not os.path.exists(p):
        continue
    im = Image.open(p).convert('RGB')
    im = im.resize((W, int(W * im.height / im.width)), Image.LANCZOS)
    label(im, f'{n} photo ({credits.get(n, "")}, Wikimedia Commons)', (0, 0))
    label(im, 'our model, same camera', (W // 2 + 4, 0))
    rows.append(im)
# lamp close-ups
crops = os.environ.get('LAMPCROPS', 'p169:120,370,1190,690;p150:620,300,1240,380;p120:40,250,1210,370').split(';')
for spec in crops:
    n, box = spec.split(':')
    x0, y0, x1, y1 = map(int, box.split(','))
    ph = Image.open(os.path.join(os.path.dirname(cd), 'photos', f'{n}.jpg')).convert('RGB') if os.path.exists(os.path.join(os.path.dirname(cd), 'photos', f'{n}.jpg')) else None
    if ph is None:
        ph = Image.open(json.load(open(os.environ['FITJSON']))['photos'][n]['photo']).convert('RGB')
    rd = Image.open(os.path.join(cd, f'{n}_render.png')).convert('RGB').resize(ph.size, Image.LANCZOS)
    s = (W // 2 - 4) / (x1 - x0)
    tiles = []
    for im, col, polys in ((ph, (0, 255, 0), {k: v for k, v in TR.get(n, {}).items() if k != 'lit'}),
                           (rd, (255, 40, 40), {k: project(n, LO[k]) for k in TR.get(n, {}) if k in LO})):
        c = im.crop((x0, y0, x1, y1)).resize((W // 2 - 4, int((y1 - y0) * s)), Image.LANCZOS)
        dd = ImageDraw.Draw(c)
        for k, poly in polys.items():
            dd.polygon([((u - x0) * s, (v - y0) * s) for u, v in poly], outline=col)
        tiles.append(c)
    row = Image.new('RGB', (W, tiles[0].height + 22), 'white')
    row.paste(tiles[0], (0, 0)); row.paste(tiles[1], (W // 2 + 4, 0))
    lit = TR.get(n, {}).get('lit', [])
    label(row, f'{n} lamps: photo, traced (green){" - lit: " + ",".join(lit) if lit else " - unlit"}', (0, 0))
    label(row, 'model, its lamp outlines (red)', (W // 2 + 4, 0))
    txt = '   '.join(f'{k}: IoU {v["iou"]:.2f} max {v["max"]:.1f} p95 {v["p95"]:.1f} px' for key, v in LR.items()
                     for k in [key.split('/')[1]] if key.startswith(n + '/'))
    ImageDraw.Draw(row).text((6, tiles[0].height + 3), txt, fill='black', font=small)
    rows.append(row)
if opt('--table'):
    lines = open(opt('--table')).read().strip().splitlines()
    t = Image.new('RGB', (W, 20 * len(lines) + 16), 'white')
    for i, ln in enumerate(lines):
        ImageDraw.Draw(t).text((10, 8 + 20 * i), ln, fill='black', font=small)
    rows.append(t)
H = sum(r.height for r in rows) + 6 * len(rows)
sheet = Image.new('RGB', (W, H), 'white')
y = 0
for r in rows:
    sheet.paste(r, (0, y)); y += r.height + 6
sheet.save(out)
print(out, sheet.size)
