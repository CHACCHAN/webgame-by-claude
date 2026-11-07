"""owner_sheet.py <out.png>: the owner's one-page sheet (final views, photo | render pairs, numbers)"""
import json, sys
from PIL import Image, ImageDraw, ImageFont
W = 2400
font = ImageFont.load_default(size=26)
small = ImageFont.load_default(size=20)
before = {n: json.load(open(f'fit2/{n}.json')) for n in ['r03', 'n24', 'r08', 'q02', 'n32', 'n06']}
after = {n: json.load(open(f'final/{n}.json')) for n in before}
blocks = []

def label(im, text):
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, 12 + 13 * len(text), 30), fill=(0, 0, 0))
    d.text((6, 3), text, fill='white', font=small)
    return im

views = [('front34', 'pop-ups up'), ('front34_closed', 'pop-ups down'), ('rear34_closed', 'rear 3/4'),
         ('side_closed', 'side'), ('front_closed', 'front'), ('rear_closed', 'rear')]
tiles = [label(Image.open(f'out/views/{v}.png').convert('RGB').resize((800, 450), Image.LANCZOS), t) for v, t in views]
grid = Image.new('RGB', (W, 900), 'white')
for i, t in enumerate(tiles):
    grid.paste(t, ((i % 3) * 800, (i // 3) * 450))
blocks.append(grid)
names = {'r03': 'r03 museum 1986 (reference)', 'n24': 'n24 red, near head-on', 'r08': 'r08 rear 3/4',
         'q02': 'q02 rear (early model)', 'n32': 'n32 side-rear (spoiler ignored)', 'n06': 'n06 front 3/4 (lowered)'}
pairs = []
for n in names:
    im = Image.open(f'out/compare/{n}_compare.png').convert('RGB')
    k = 1192 / im.size[0]
    pairs.append(label(im.resize((1192, int(im.size[1] * k)), Image.LANCZOS), f'{names[n]}: photo | our model, same camera'))
for a, b in zip(pairs[0::2], pairs[1::2]):
    h = max(a.size[1], b.size[1])
    row = Image.new('RGB', (W, h + 8), 'white')
    row.paste(a, (0, 0))
    row.paste(b, (1208, 0))
    blocks.append(row)
# numbers
lines = ['Silhouette fit (silfit; IoU / p95 % of car width / worst zone %)    before = WIP + BA cameras    after = this model + refined cameras',
         'target per photo: IoU >= 0.95, p95 <= 1.5 %, zones within +-1 %']
for n in names:
    b, a = before[n], after[n]
    wz = lambda j: max(abs(v['mean_signed_pct']) for v in j['zones'].values())
    lines.append(f'{n}:  before {b["iou"]:.3f} / {b["render_to_photo_p95_pct"]:5.2f} / {wz(b):5.2f}     after {a["iou"]:.3f} / {a["render_to_photo_p95_pct"]:5.2f} / {wz(a):5.2f}')
lines.append('38,580 triangles, 16 materials. Light silver = paint and black panels in one colour for the surfaces; lamps lit as in daylight.')
txt = Image.new('RGB', (W, 40 + 36 * len(lines)), 'white')
d = ImageDraw.Draw(txt)
for i, l in enumerate(lines):
    d.text((20, 20 + 36 * i), l, fill='black', font=font)
blocks.append(txt)
title = Image.new('RGB', (W, 60), (20, 20, 24))
ImageDraw.Draw(title).text((20, 14), 'hayate: Toyota Sprinter Trueno AE86 GT-APEX (late model), our own model fitted to 6 photos (WIP, not in the game)', fill='white', font=font)
blocks.insert(0, title)
H = sum(b.size[1] for b in blocks)
S = Image.new('RGB', (W, H), 'white')
y = 0
for b in blocks:
    S.paste(b, (0, y))
    y += b.size[1]
S.save(sys.argv[1])
print(S.size)
