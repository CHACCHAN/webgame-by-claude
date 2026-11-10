"""
sheet.py: the owner's sheet for the U9, 1200 px wide: photo | render pairs from the solved cameras (compare.py), the
lamp close-ups (photo crops with the tracing in green and the model's outline in magenta, lampscore.py --crops) with
their numbers, the silhouette table and notes.

  py sheet.py <compare_dir> <lampscore_dir> <out.png> [--pairs c00,c17,c14,c12,c18] [--table silfit.txt]
      [--title text] [--note text]...
"""
import json, os, sys

from PIL import Image, ImageDraw, ImageFont

a = sys.argv[1:]
cd, ld, out = a[:3]


def opt(k, d=None):
    return a[a.index(k) + 1] if k in a else d


notes = [a[i + 1] for i, v in enumerate(a) if v == '--note']
W = 1200
font = ImageFont.load_default(size=22)
small = ImageFont.load_default(size=15)
LABEL = {'c00': 'front 3/4 (regular U9)', 'c17': 'rear 3/4 (Xtreme)', 'c14': 'side (regular U9, wide-angle photo)',
         'c12': 'front', 'c18': 'rear (Xtreme)', 'c01': 'rear 3/4 (regular U9)', 'c32': 'front 3/4 high (Xtreme)'}
blocks = []
t = Image.new('RGB', (W, 44), (20, 20, 24))
ImageDraw.Draw(t).text((14, 10), opt('--title', 'u9: Yangwang U9 Xtreme, our own model'), fill='white', font=font)
blocks.append(t)
for n in opt('--pairs', 'c00,c17,c14,c12,c18').split(','):
    f = os.path.join(cd, f'{n}_compare.png')
    if not os.path.exists(f):
        continue
    im = Image.open(f).convert('RGB')
    im = im.resize((W, int(im.height * W / im.width)), Image.LANCZOS)
    d = ImageDraw.Draw(im)
    txt = f'{n}: {LABEL.get(n, "")}   photo | model (same camera, Cycles)'
    d.rectangle((0, 0, 9 * len(txt) + 12, 22), fill=(0, 0, 0))
    d.text((6, 3), txt, fill='white', font=small)
    blocks.append(im)
# lamp close-ups
ls = json.load(open(os.path.join(ld, 'lampscore.json')))
crops = []
for n, lamps in ls.items():
    for k, v in lamps.items():
        f = os.path.join(ld, f'crop_{n}_{k}.png')
        if os.path.exists(f):
            crops.append((n, k, v, Image.open(f).convert('RGB')))
row_h = 170
rows, cur, x = [], [], 0
for n, k, v, im in crops:
    s = row_h / im.height
    w = int(im.width * s)
    if w > W:
        s = W / im.width
        w = W
    im = im.resize((w, int(im.height * s)), Image.LANCZOS)
    d = ImageDraw.Draw(im)
    txt = f'{n} {k}: IoU {v["iou"]:.2f}  p95 {v["p95"]:.0f}  max {v["max"]:.0f} px'
    d.rectangle((0, 0, 8 * len(txt) + 10, 20), fill=(0, 0, 0))
    d.text((5, 2), txt, fill='white', font=small)
    if x + w > W and cur:
        rows.append(cur)
        cur, x = [], 0
    cur.append(im)
    x += w + 4
if cur:
    rows.append(cur)
hdr = Image.new('RGB', (W, 26), (20, 20, 24))
ImageDraw.Draw(hdr).text((10, 4), 'lamps: tracing green, model magenta (px of the 1280-wide photo)', fill='white', font=small)
blocks.append(hdr)
for r in rows:
    h = max(i.height for i in r)
    im = Image.new('RGB', (W, h), (40, 40, 40))
    x = 0
    for i in r:
        im.paste(i, (x, 0))
        x += i.width + 4
    blocks.append(im)
lines = []
if opt('--table'):
    lines += open(opt('--table')).read().rstrip().split('\n')
lines += notes
if lines:
    im = Image.new('RGB', (W, 12 + 19 * len(lines)), 'white')
    d = ImageDraw.Draw(im)
    for i, l in enumerate(lines):
        d.text((10, 6 + 19 * i), l, fill='black', font=small)
    blocks.append(im)
H = sum(b.height + 4 for b in blocks)
sheet = Image.new('RGB', (W, H), 'white')
y = 0
for b in blocks:
    sheet.paste(b, (0, y))
    y += b.height + 4
sheet.save(out)
print('wrote', out, sheet.size)
