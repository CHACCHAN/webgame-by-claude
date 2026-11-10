"""sheet.py <compare_dir> <before_dir> <after_dir> <out.png> [title] [note lines...] : the owner's sheet for raijin:
the standard views, close-up pairs (photo above, our model from the same camera below), photo | render pairs (light
silver), and the silhouette numbers before / after. (After fitdata/hayate/tools/sheet2.py.)
env PAIRS=r02,r10,r13,r16,r17  CREDITS=<ref/list.json>  VIEWS=<dir with front34.png ...> (default: compare_dir)"""
import json, os, sys
from PIL import Image, ImageDraw, ImageFont

cd, bd, ad, out = sys.argv[1:5]
title_txt = sys.argv[5] if len(sys.argv) > 5 else 'raijin: Subaru Impreza WRX STI (GDB-C/D, 2004), our own model'
notes = sys.argv[6:]
W = 2400
font = ImageFont.load_default(size=26)
small = ImageFont.load_default(size=19)
credits = {}
if os.environ.get('CREDITS'):
    for e in json.load(open(os.environ['CREDITS'])):
        credits[e['file'].split('.')[0]] = f"{e['author']}, {e['licence']}, Wikimedia Commons"


def label(im, text, y=0):
    d = ImageDraw.Draw(im)
    d.rectangle((0, y, 12 + 10 * len(text), y + 26), fill=(0, 0, 0))
    d.text((6, y + 3), text, fill='white', font=small)
    return im


blocks = []
title = Image.new('RGB', (W, 60), (20, 20, 24))
ImageDraw.Draw(title).text((20, 14), title_txt, fill='white', font=font)
blocks.append(title)
views = [('front34', 'front 3/4'), ('rear34', 'rear 3/4'), ('side', 'side'), ('front', 'front'), ('rear', 'rear'),
         ('top', 'top')]
vd = os.environ.get('VIEWS', cd)
views = [v for v in views if os.path.exists(f'{vd}/{v[0]}.png')]
rows = (len(views) + 2) // 3
grid = Image.new('RGB', (W, 450 * rows), 'white')
for i, (v, t) in enumerate(views):
    im = label(Image.open(f'{vd}/{v}.png').convert('RGB').resize((800, 450), Image.LANCZOS), t)
    grid.paste(im, ((i % 3) * 800, (i // 3) * 450))
blocks.append(grid)

# close-ups: (photo, box as fractions of one half of the compare image, caption); photo left, model right
CLOSE = [('r16', (0.15, 0.30, 0.85, 0.95), 'front close-up r16'), ('r17', (0.05, 0.20, 0.98, 0.98), 'rear close-up r17'),
         ('r02', (0.30, 0.30, 1.00, 0.85), 'front 3/4 close-up r02'), ('r10', (0.35, 0.10, 1.00, 0.75), 'rear 3/4 close-up r10')]
for n, (x0, y0, x1, y1), cap in CLOSE:
    p = f'{cd}/{n}_compare.png'
    if not os.path.exists(p):
        continue
    cmp_ = Image.open(p).convert('RGB')
    w2 = (cmp_.size[0] - 8) // 2
    ph, rd = cmp_.crop((0, 0, w2, cmp_.size[1])), cmp_.crop((w2 + 8, 0, 2 * w2 + 8, cmp_.size[1]))
    box = (int(x0 * w2), int(y0 * cmp_.size[1]), int(x1 * w2), int(y1 * cmp_.size[1]))
    a, b = ph.crop(box), rd.crop(box)
    k = 1192 / a.size[0]
    a = label(a.resize((1192, int(a.size[1] * k)), Image.LANCZOS), f'{cap}: photo ({credits.get(n, "")})')
    b = label(b.resize((1192, int(b.size[1] * k)), Image.LANCZOS), 'our model, same camera')
    row = Image.new('RGB', (W, a.size[1] + 8), 'white')
    row.paste(a, (0, 0))
    row.paste(b, (1208, 0))
    blocks.append(row)

pairs = os.environ.get('PAIRS', 'r02,r10,r13,r16,r17').split(',')
cells = []
for n in pairs:
    p = f'{cd}/{n}_compare.png'
    if not os.path.exists(p):
        continue
    im = Image.open(p).convert('RGB')
    k = 1192 / im.size[0]
    im = im.resize((1192, int(im.size[1] * k)), Image.LANCZOS)
    label(im, f'{n} photo: {credits.get(n, "")}')
    d = ImageDraw.Draw(im)
    x = im.size[0] // 2 + 4
    d.rectangle((x, 0, x + 260, 26), fill=(0, 0, 0))
    d.text((x + 6, 3), 'our model, same camera', fill='white', font=small)
    cells.append(im)
for i in range(0, len(cells), 2):
    row = cells[i:i + 2]
    h = max(c.size[1] for c in row)
    R = Image.new('RGB', (W, h + 8), 'white')
    for j, c in enumerate(row):
        R.paste(c, (j * 1208, 0))
    blocks.append(R)

names = pairs
lines = [('Silhouette IoU / p95 (% of car width), same masks; before = session start', '', ''), ('photo', 'before', 'now')]
for n in names:
    try:
        b, a = json.load(open(f'{bd}/{n}.json')), json.load(open(f'{ad}/{n}.json'))
    except FileNotFoundError:
        continue

    def fmt(j):
        ok = j['iou'] >= 0.95 and j['render_to_photo_p95_pct'] <= 1.5
        return f'{j["iou"]:.3f} / {j["render_to_photo_p95_pct"]:4.2f}' + ('  pass' if ok else '')
    lines.append((n, fmt(b), fmt(a)))
for t in notes:
    lines.append((t, '', ''))
txt = Image.new('RGB', (W, 40 + 34 * len(lines)), 'white')
d = ImageDraw.Draw(txt)
for i, (c0, c1, c2) in enumerate(lines):
    d.text((20, 20 + 34 * i), c0, fill='black', font=font)
    d.text((300, 20 + 34 * i), c1, fill='black', font=font)
    d.text((900, 20 + 34 * i), c2, fill='black', font=font)
blocks.append(txt)
H = sum(b.size[1] for b in blocks)
S = Image.new('RGB', (W, H), 'white')
y = 0
for b in blocks:
    S.paste(b, (0, y))
    y += b.size[1]
S.save(out)
print(S.size)
