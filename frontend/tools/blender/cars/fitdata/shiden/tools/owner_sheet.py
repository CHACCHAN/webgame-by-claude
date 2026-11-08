"""owner_sheet.py <views_dir> <run_dir> <before_run> <out.png> [title] : the owner's sheet (2400 px): light-silver
views (pop-ups up / down), close-up pairs photo | render (same solved camera), all compares, silhouette numbers
before / now."""
import json, os, sys
from PIL import Image, ImageDraw, ImageFont
vd, rd, bd, out = sys.argv[1:5]
title_txt = sys.argv[5] if len(sys.argv) > 5 else 'shiden: Mazda RX-7 (FD3S) late Type RS, our own model'
SH = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W = 2400
font = ImageFont.load_default(size=26)
small = ImageFont.load_default(size=20)


def label(im, text):
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, 14 + 11 * len(text), 28), fill=(0, 0, 0))
    d.text((6, 3), text, fill='white', font=small)
    return im


blocks = []
t = Image.new('RGB', (W, 60), (20, 20, 24))
ImageDraw.Draw(t).text((20, 14), title_txt, fill='white', font=font)
blocks.append(t)
views = [('front34', 'pop-ups up'), ('front34_closed', 'pop-ups down'), ('rear34_closed', 'rear 3/4'),
         ('side_closed', 'side'), ('front_closed', 'front'), ('rear_closed', 'rear')]
g = Image.new('RGB', (W, 900), 'white')
for i, (v, tx) in enumerate(views):
    p = f'{vd}/{v}.png'
    if os.path.exists(p):
        g.paste(label(Image.open(p).convert('RGB').resize((800, 450), Image.LANCZOS), tx), ((i % 3) * 800, (i // 3) * 450))
blocks.append(g)
# close-ups: photo name, box in photo pixels, caption
CLOSE = [('r01', (100, 450, 1180, 760), 'front, Type RS (r01)'), ('s08', (150, 380, 1150, 760), 'front (s08)'),
         ('s14', (180, 250, 1110, 740), 'rear (s14)'), ('s13', (640, 120, 1280, 560), 'wing, rear 3/4 (s13)')]
for n, (x0, y0, x1, y1), cap in CLOSE:
    ph = Image.open(f'{SH}/photos/{n}.jpg').convert('RGB')
    rp = f'{rd}/cy/{n}_cy.png'
    if not os.path.exists(rp):
        continue
    rr = Image.open(rp).convert('RGB').resize(ph.size, Image.LANCZOS)
    a, b = ph.crop((x0, y0, x1, y1)), rr.crop((x0, y0, x1, y1))
    k = 1192 / a.size[0]
    a = label(a.resize((1192, int(a.size[1] * k)), Image.LANCZOS), f'{cap}: photo')
    b = label(b.resize((1192, int(b.size[1] * k)), Image.LANCZOS), 'our model, same camera')
    row = Image.new('RGB', (W, a.size[1] + 8), 'white')
    row.paste(a, (0, 0)); row.paste(b, (1208, 0))
    blocks.append(row)
names = ['s08', 's11', 's12', 's13', 's14', 'r01', 'r03', 'r11', 'r18', 'r19']
# all compares, small: photo | render pairs, 4 pairs per row (each pair 600 px)
pairs = []
for n in names:
    rp = f'{rd}/cy/{n}_cy.png'
    if not os.path.exists(rp):
        continue
    ph = Image.open(f'{SH}/photos/{n}.jpg').convert('RGB')
    h = int(ph.size[1] * 296 / ph.size[0])
    a = label(ph.resize((296, h), Image.LANCZOS), n)
    b = Image.open(rp).convert('RGB').resize((296, h), Image.LANCZOS)
    pr = Image.new('RGB', (600, h), 'white'); pr.paste(a, (0, 0)); pr.paste(b, (300, 0))
    pairs.append(pr)
for i in range(0, len(pairs), 4):
    rowh = max(p.size[1] for p in pairs[i:i + 4])
    row = Image.new('RGB', (W, rowh + 6), 'white')
    for k, p in enumerate(pairs[i:i + 4]):
        row.paste(p, (k * 600, 0))
    blocks.append(row)
lines = [('Silhouette per photo: IoU / p95 (% of car width) / worst zone offset (%), same solved cameras', '', ''),
         ('photo', 'before (WIP)', 'now')]


def fmt(j):
    z = max(j['zones'].values(), key=lambda v: abs(v['mean_signed_pct']))['mean_signed_pct'] if j['zones'] else 0
    ok = j['iou'] >= 0.95 and j['render_to_photo_p95_pct'] <= 1.5 and all(abs(v['mean_signed_pct']) <= 1 for v in j['zones'].values())
    return f"{j['iou']:.3f} / {j['render_to_photo_p95_pct']:4.2f} / {z:+.2f}" + ('  PASS' if ok else '')


for n in names:
    try:
        b = json.load(open(f'{bd}/fit/{n}.json')); a = json.load(open(f'{rd}/fit/{n}.json'))
    except FileNotFoundError:
        continue
    lines.append((n, fmt(b), fmt(a)))
for extra in sys.argv[6:]:
    lines.append((extra, '', ''))
txt = Image.new('RGB', (W, 30 + 32 * len(lines)), 'white')
d = ImageDraw.Draw(txt)
for i, (a, b, c) in enumerate(lines):
    y = 12 + 32 * i
    d.text((20, y), a, fill='black', font=small)
    d.text((300, y), b, fill='black', font=small)
    d.text((900, y), c, fill='black', font=small)
blocks.append(txt)
H = sum(b.size[1] for b in blocks)
S = Image.new('RGB', (W, H), 'white')
y = 0
for b in blocks:
    S.paste(b, (0, y)); y += b.size[1]
S.save(out)
print('sheet', S.size)
