"""sheet.py: the owner's sheets for the r34, 1200 px wide.

  py sheet.py <compare_dir> <before_dir> <after_dir> <lampfit_dir> <lampfit_before_dir> <out_prefix> [title] [notes...]

<out_prefix>_compare.png: photo | our model (light silver, same camera and pose; compare.py) for the front 3/4, the rear
  3/4s, the side, the front and the rear photos, then the silhouette numbers (loop.py) before / now.
<out_prefix>_lamps.png: per lamp the photo crop | both outlines (green = photo, magenta = model) | our model (the
  photo car's paint, same camera; lampfit.py crops), with the lamp's numbers before / now.
(After fitdata/raijin/tools/sheet.py.)
"""
import json, os, sys
from PIL import Image, ImageDraw, ImageFont

cd, bd, ad, lf, lf0, out = sys.argv[1:7]
title_txt = sys.argv[7] if len(sys.argv) > 7 else 'r34: Nissan Skyline GT-R V-spec (BNR34), our own model'
notes = sys.argv[8:]
W = 1200
font = ImageFont.load_default(size=22)
small = ImageFont.load_default(size=16)
PAIRS = [('r07', 'front 3/4'), ('r11', 'rear 3/4'), ('r38', 'rear 3/4 (far)'), ('r36', 'side'), ('r29', 'front'),
         ('r37', 'rear')]
LAMPS = [('r29', 'hl_R'), ('r29', 'hl_L'), ('r07', 'hl_L'), ('r36', 'hl_R'), ('r29', 'ind_L'), ('r07', 'ind_L'),
         ('r37', 'tl_LO'), ('r37', 'tl_LI'), ('r37', 'tl_RI'), ('r37', 'tl_RO'), ('r11', 'tl_RO'), ('r38', 'tl_LO')]


def label(im, text, x=0, y=0):
    d = ImageDraw.Draw(im)
    w = d.textlength(text, font=small)
    d.rectangle((x, y, x + w + 12, y + 22), fill=(0, 0, 0))
    d.text((x + 6, y + 3), text, fill='white', font=small)
    return im


def titled(text, h=44):
    t = Image.new('RGB', (W, h), (20, 20, 24))
    ImageDraw.Draw(t).text((14, (h - 26) // 2), text, fill='white', font=font)
    return t


def stack(blocks, path):
    H = sum(b.size[1] for b in blocks)
    S = Image.new('RGB', (W, H), 'white')
    y = 0
    for b in blocks:
        S.paste(b, (0, y))
        y += b.size[1]
    S.save(path)
    print(path, S.size)


# ---- compare sheet
blocks = [titled(title_txt)]
for n, cap in PAIRS:
    p = f'{cd}/{n}_compare.png'
    if not os.path.exists(p):
        continue
    im = Image.open(p).convert('RGB')
    im = im.resize((W, int(im.size[1] * W / im.size[0])), Image.LANCZOS)
    label(im, f'{n} {cap}: photo')
    label(im, 'our model, same camera', x=W // 2 + 4)
    row = Image.new('RGB', (W, im.size[1] + 6), 'white')
    row.paste(im, (0, 0))
    blocks.append(row)
lines = [('Silhouette IoU / p95 (% of car width); before = session start (no FFD)', '', ''), ('photo', 'before', 'now')]
for n, _ in PAIRS:
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
txt = Image.new('RGB', (W, 24 + 30 * len(lines)), 'white')
d = ImageDraw.Draw(txt)
for i, (c0, c1, c2) in enumerate(lines):
    d.text((14, 12 + 30 * i), c0, fill='black', font=font)
    d.text((200, 12 + 30 * i), c1, fill='black', font=font)
    d.text((520, 12 + 30 * i), c2, fill='black', font=font)
blocks.append(txt)
stack(blocks, f'{out}_compare.png')

# ---- lamp sheet
now = json.load(open(f'{lf}/lamps.json'))
before = json.load(open(f'{lf0}/lamps.json')) if os.path.exists(f'{lf0}/lamps.json') else {}
blocks = [titled('r34 lamps: photo | outlines (green = photo, magenta = our model) | our model, same camera')]
for ph, lamp in LAMPS:
    p = f'{lf}/{ph}_{lamp}.png'
    if not os.path.exists(p) or lamp not in now.get(ph, {}):
        continue
    im = Image.open(p).convert('RGB')
    im = im.resize((W, int(im.size[1] * W / im.size[0])), Image.LANCZOS)
    r = now[ph][lamp]
    b = before.get(ph, {}).get(lamp)
    t = (f'{ph} {lamp}: IoU {r["iou"]:.3f}, outline p95 {r["p95_px"]:.1f} px, max {r["max_px"]:.1f} px, '
         f'centre off ({r["dc_px"][0]:+.0f}, {r["dc_px"][1]:+.0f}) px')
    if b:
        t += f'   (before: IoU {b["iou"]:.3f}, p95 {b["p95_px"]:.1f})'
    label(im, t)
    row = Image.new('RGB', (W, im.size[1] + 6), 'white')
    row.paste(im, (0, 0))
    blocks.append(row)
cap = Image.new('RGB', (W, 74), 'white')
ImageDraw.Draw(cap).multiline_text((14, 8), 'px at 1280-px photo width. hl = head lamp lens, ind = front indicator lens, '
                                   'tl = tail lamp red lens (LO/LI/RI/RO: left outer ... right outer).\n'
                                   'r38 / r11 / r07 offsets that move all lamps of a photo together are camera error '
                                   '(the silhouette solve leaves them free).', fill='black', font=small)
blocks.append(cap)
stack(blocks, f'{out}_lamps.png')
