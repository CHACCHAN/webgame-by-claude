"""sheet.py <dir> <out.png> <names> [width per tile] [cols] [suffix]: tile <dir>/<name><suffix> images, cropped to the car"""
import sys, json, os
from PIL import Image, ImageDraw
d, out, names = sys.argv[1], sys.argv[2], sys.argv[3].split(',')
tw = int(sys.argv[4]) if len(sys.argv) > 4 else 800
cols = int(sys.argv[5]) if len(sys.argv) > 5 else 2
suf = sys.argv[6] if len(sys.argv) > 6 else '_overlay.png'
tiles = []
for n in names:
    im = Image.open(os.path.join(d, n + suf)).convert('RGB')
    sil = Image.open(os.path.join(d, n + '_sil.png')).convert('RGBA').resize(im.size)
    bb = sil.getchannel('A').getbbox()
    if bb:
        mx, my = int((bb[2] - bb[0]) * 0.08), int((bb[3] - bb[1]) * 0.12)
        im = im.crop((max(0, bb[0] - mx), max(0, bb[1] - my), min(im.size[0], bb[2] + mx), min(im.size[1], bb[3] + my)))
    im.thumbnail((tw, tw))
    dr = ImageDraw.Draw(im)
    dr.rectangle((0, 0, 60, 14), fill='black'); dr.text((3, 1), n, fill='white')
    tiles.append(im)
rows = (len(tiles) + cols - 1) // cols
hs = [max(t.size[1] for t in tiles[r * cols:(r + 1) * cols]) for r in range(rows)]
S = Image.new('RGB', (tw * cols, sum(hs)), 'white')
y = 0
for r in range(rows):
    for c, t in enumerate(tiles[r * cols:(r + 1) * cols]):
        S.paste(t, (c * tw, y))
    y += hs[r]
S.save(out)
