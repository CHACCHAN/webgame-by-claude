"""sheet2.py <views_dir> <compare_dir> <before_dir> <after_dir> <out.png> [title] [extra lines...]: the owner's sheet for round 2:
views, rear and front close-up pairs (photo | render, same camera), full compares, before/after numbers"""
import json, os, sys
from PIL import Image, ImageDraw, ImageFont

vd, cd, bd, ad, out = sys.argv[1:6]
title_txt = sys.argv[6] if len(sys.argv) > 6 else 'hayate: Sprinter Trueno AE86 GT-APEX (late), our own model, round 2'
W = 2400
font = ImageFont.load_default(size=26)
small = ImageFont.load_default(size=20)


def label(im, text):
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, 12 + 11 * len(text), 28), fill=(0, 0, 0))
    d.text((6, 3), text, fill='white', font=small)
    return im


blocks = []
title = Image.new('RGB', (W, 60), (20, 20, 24))
ImageDraw.Draw(title).text((20, 14), title_txt, fill='white', font=font)
blocks.append(title)

views = [('front34', 'pop-ups up'), ('front34_closed', 'pop-ups down'), ('rear34_closed', 'rear 3/4'),
         ('side_closed', 'side'), ('front_closed', 'front'), ('rear_closed', 'rear')]
grid = Image.new('RGB', (W, 900), 'white')
for i, (v, t) in enumerate(views):
    im = label(Image.open(f'{vd}/{v}.png').convert('RGB').resize((800, 450), Image.LANCZOS), t)
    grid.paste(im, ((i % 3) * 800, (i // 3) * 450))
blocks.append(grid)

# close-up pairs: (photo, box as fractions of the image (x0, y0, x1, y1), caption)
CLOSE = [('r08', (0.0, 0.18, 0.62, 0.62), 'rear close-up r08'), ('q02', (0.25, 0.25, 0.95, 0.72), 'rear close-up q02'),
         ('r03', (0.0, 0.30, 0.62, 0.78), 'front close-up r03'), ('n24', (0.0, 0.28, 0.62, 0.72), 'front close-up n24')]
for n, (x0, y0, x1, y1), cap in CLOSE:
    try:
        cmp_ = Image.open(f'{cd}/{n}_compare.png').convert('RGB')
    except FileNotFoundError:
        continue
    w2 = cmp_.size[0] // 2
    ph, rd = cmp_.crop((0, 0, w2, cmp_.size[1])), cmp_.crop((w2, 0, 2 * w2, cmp_.size[1]))
    box = (int(x0 * w2), int(y0 * cmp_.size[1]), int(x1 * w2), int(y1 * cmp_.size[1]))
    a, b = ph.crop(box), rd.crop(box)
    k = 1192 / a.size[0]
    a = label(a.resize((1192, int(a.size[1] * k)), Image.LANCZOS), f'{cap}: photo')
    b = label(b.resize((1192, int(b.size[1] * k)), Image.LANCZOS), 'our model, same camera')
    row = Image.new('RGB', (W, a.size[1] + 8), 'white')
    row.paste(a, (0, 0))
    row.paste(b, (1208, 0))
    blocks.append(row)

names = ['r03', 'n24', 'r08', 'q02', 'n32', 'n06']
# optional middle column (env MID=<dir>, MID_LABEL), and column labels (env BEFORE_LABEL, NOW_LABEL, HEADER)
md = os.environ.get('MID')
lines = [(os.environ.get('HEADER', 'Silhouette (IoU / p95 % of car width) and dark/lamp line distance (mean / p90 % of car '
                                    'width), same cameras'), '', '', ''),
         ('photo', os.environ.get('BEFORE_LABEL', 'before (round 1)'), os.environ.get('MID_LABEL', '') if md else '',
          os.environ.get('NOW_LABEL', 'now'))]
for n in names:
    try:
        b, a = json.load(open(f'{bd}/{n}.json')), json.load(open(f'{ad}/{n}.json'))
        bdk, adk = json.load(open(f'{bd}/{n}_dark.json')), json.load(open(f'{ad}/{n}_dark.json'))
        m, mdk = (json.load(open(f'{md}/{n}.json')), json.load(open(f'{md}/{n}_dark.json'))) if md else (None, None)
    except FileNotFoundError:
        continue

    def fmt(j, dk):
        s = f'{j["iou"]:.3f} / {j["render_to_photo_p95_pct"]:4.2f}'
        dkc = dk.get('classes', dk)
        for c in ('dark', 'lamp'):
            v = dkc.get(c)
            if isinstance(v, dict) and 'mean_pct' in v:
                s += f'   {c} {v["mean_pct"]:4.2f} / {v["p90_pct"]:4.2f}'
        return s
    lines.append((n, fmt(b, bdk), fmt(m, mdk) if md else '', fmt(a, adk)))
for extra in sys.argv[7:]:
    lines.append((extra, '', '', ''))
txt = Image.new('RGB', (W, 40 + 34 * len(lines)), 'white')
d = ImageDraw.Draw(txt)
cols = (140, 900, 1660) if md else (140, None, 1240)
for i, (c0, c1, cm, c2) in enumerate(lines):
    d.text((20, 20 + 34 * i), c0, fill='black', font=font)
    d.text((cols[0], 20 + 34 * i), c1, fill='black', font=font)
    if cols[1]:
        d.text((cols[1], 20 + 34 * i), cm, fill='black', font=font)
    d.text((cols[2], 20 + 34 * i), c2, fill='black', font=font)
blocks.append(txt)

H = sum(b.size[1] for b in blocks)
S = Image.new('RGB', (W, H), 'white')
y = 0
for b in blocks:
    S.paste(b, (0, y))
    y += b.size[1]
S.save(out)
print(S.size)
