"""lampsheet.py: the owner's lamp sheet (1200 px wide): per lamp the photo crop | outlines (green = photo, magenta =
model) | our model in the photo car's paint (lampfit.py crops of the current model), with IoU and outline p95 / max
before -> now; and a compare sheet: photo | model before | model now (full frames, same camera and pose).

  py lampsheet.py lamps <lf_before> <lf_after> <out.png> <title> [--lamps ph:lamp,...] [--note text]...
  py lampsheet.py compare <photodir> <rdir_before> <rdir_after> <out.png> <title> --photos a,b [--note text]...
"""
import json, os, sys
from PIL import Image, ImageDraw, ImageFont

a = sys.argv[1:]
mode = a[0]
W = 1200
font = ImageFont.load_default(size=22)
small = ImageFont.load_default(size=16)
notes = [a[i + 1] for i, t in enumerate(a) if t == '--note']


def label(im, text, x=0, y=0, f=small):
    d = ImageDraw.Draw(im)
    w = d.textlength(text, font=f)
    d.rectangle((x, y, x + w + 12, y + f.size + 8), fill=(0, 0, 0))
    d.text((x + 6, y + 3), text, fill='white', font=f)


def header(title, extra):
    lines = [title] + extra
    h = 16 + 28 * len(lines)
    im = Image.new('RGB', (W, h), (255, 255, 255))
    d = ImageDraw.Draw(im)
    for i, t in enumerate(lines):
        d.text((12, 8 + 28 * i), t, fill=(0, 0, 0), font=font if i == 0 else small)
    return im


def stack(parts, out):
    H = sum(p.height + 8 for p in parts)
    o = Image.new('RGB', (W, H), (255, 255, 255))
    y = 0
    for p in parts:
        o.paste(p, (0, y))
        y += p.height + 8
    o.save(out)
    print(out, o.size)


if mode == 'lamps':
    lf0, lf1, out, title = a[1:5]
    r0 = json.load(open(os.path.join(lf0, 'lamps.json')))
    r1 = json.load(open(os.path.join(lf1, 'lamps.json')))
    sel = [tuple(s.split(':')) for s in a[a.index('--lamps') + 1].split(',')] if '--lamps' in a else \
        [(ph, l) for ph in r1 for l in r1[ph]]
    parts = [header(title, ['per lamp: photo | outlines (green = photo, magenta = our model) | our model, same camera',
                            'numbers: IoU and outline p95 / max (px at the photo size), before -> now'] + notes)]
    for ph, l in sel:
        p = os.path.join(lf1, f'{ph}_{l}.png')
        if not os.path.exists(p):
            continue
        im = Image.open(p).convert('RGB')
        if im.width > W:
            im = im.resize((W, round(im.height * W / im.width)), Image.LANCZOS)
        row = Image.new('RGB', (W, im.height + 30), (255, 255, 255))
        row.paste(im, (0, 30))
        b, n = r0.get(ph, {}).get(l), r1[ph][l]
        t = f'{ph} {l}:  IoU ' + (f"{b['iou']:.3f} -> " if b else '') + f"{n['iou']:.3f}   p95 " + \
            (f"{b['p95_px']:.0f} -> " if b else '') + f"{n['p95_px']:.0f} px   max " + (f"{b['max_px']:.0f} -> " if b else '') + \
            f"{n['max_px']:.0f} px"
        ImageDraw.Draw(row).text((6, 6), t, fill=(0, 0, 0), font=small)
        parts.append(row)
    stack(parts, out)
else:
    pdir, rb, ra, out, title = a[1:6]
    phs = a[a.index('--photos') + 1].split(',')
    box = {}
    if '--box' in a:
        for s in a[a.index('--box') + 1].split(';'):
            k, v = s.split('=')
            box[k] = tuple(int(x) for x in v.split(','))
    parts = [header(title, ['photo | our model before | our model now (same solved camera and pose; the model in the photo car\'s paint)'] + notes)]
    w3 = (W - 16) // 3
    for ph in phs:
        cand = lambda d: next((os.path.join(d, f'{ph}{s}.png') for s in ('_full', '_lamps') if os.path.exists(os.path.join(d, f'{ph}{s}.png'))), None)
        pb, pa = cand(rb), cand(ra)
        if not pb or not pa:
            continue
        A = Image.open(pa).convert('RGB')
        P = Image.open(os.path.join(pdir, f'{ph}.jpg')).convert('RGB').resize(A.size, Image.LANCZOS)
        Bm = Image.open(pb).convert('RGB').resize(A.size, Image.LANCZOS)
        ims = [P, Bm, A]
        if ph in box:
            ims = [i.crop(box[ph]) for i in ims]
        ims = [i.resize((w3, round(i.height * w3 / i.width)), Image.LANCZOS) for i in ims]
        row = Image.new('RGB', (W, ims[0].height), (255, 255, 255))
        for i, im in enumerate(ims):
            row.paste(im, (i * (w3 + 8), 0))
        label(row, ph)
        parts.append(row)
    stack(parts, out)
