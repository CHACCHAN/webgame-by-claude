"""tile.py <out.png> <width> <img> [img ...] [--cols n] [--labels a,b,...]: images scaled to a common column width, tiled"""
import sys
from PIL import Image, ImageDraw
a = sys.argv[1:]
cols = 2
labels = None
if '--cols' in a:
    i = a.index('--cols'); cols = int(a[i + 1]); a = a[:i] + a[i + 2:]
if '--labels' in a:
    i = a.index('--labels'); labels = a[i + 1].split(','); a = a[:i] + a[i + 2:]
out, W, files = a[0], int(a[1]), a[2:]
cw = W // cols
ims = []
for k, f in enumerate(files):
    im = Image.open(f).convert('RGBA')
    bg = Image.new('RGBA', im.size, (255, 255, 255, 255)); bg.alpha_composite(im); im = bg.convert('RGB')
    im = im.resize((cw - 4, int(im.size[1] * (cw - 4) / im.size[0])), Image.LANCZOS)
    if labels and k < len(labels):
        ImageDraw.Draw(im).text((4, 4), labels[k], fill=(200, 0, 0))
    ims.append(im)
rows = [ims[i:i + cols] for i in range(0, len(ims), cols)]
H = sum(max(i.size[1] for i in r) + 4 for r in rows)
S = Image.new('RGB', (W, H), 'white')
y = 0
for r in rows:
    for j, im in enumerate(r):
        S.paste(im, (j * cw + 2, y + 2))
    y += max(i.size[1] for i in r) + 4
S.save(out)
