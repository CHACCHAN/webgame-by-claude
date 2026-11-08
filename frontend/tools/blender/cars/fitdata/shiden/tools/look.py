"""look.py <run> <out.jpg> name:x0,y0,x1,y1[:scale][:h] ... : photo | render crops (vertical pairs, or h = side by side)"""
import sys
from PIL import Image
run, out = sys.argv[1:3]
tiles = []
for spec in sys.argv[3:]:
    parts = spec.split(':')
    n = parts[0]; box = tuple(int(v) for v in parts[1].split(','))
    sc = float(parts[2]) if len(parts) > 2 and parts[2] else 1.0
    hz = len(parts) > 3
    ph = Image.open(f'photos/{n}.jpg').convert('RGB')
    rr = Image.open(f'{run}/cy/{n}_cy.png').convert('RGB').resize(ph.size)
    a, b = ph.crop(box), rr.crop(box)
    a = a.resize((int(a.size[0] * sc), int(a.size[1] * sc))); b = b.resize(a.size)
    S = Image.new('RGB', (a.size[0] * 2, a.size[1]) if hz else (a.size[0], a.size[1] * 2))
    S.paste(a, (0, 0)); S.paste(b, (a.size[0], 0) if hz else (0, a.size[1]))
    tiles.append(S)
W = max(t.size[0] for t in tiles); H = sum(t.size[1] for t in tiles)
O = Image.new('RGB', (W, H), 'white'); y = 0
for t in tiles:
    O.paste(t, (0, y)); y += t.size[1]
O.save(out, quality=85); print(O.size)
