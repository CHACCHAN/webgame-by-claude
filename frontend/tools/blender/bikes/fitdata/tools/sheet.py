"""sheet.py <config.json> : compare sheet (≤ 1200 px wide). config: {"out": path, "title": str, "lines": [str],
"rows": [[{"img": path, "crop": [x0,y0,x1,y1] | null, "label": str, "bg": true (composite alpha on grey),
"poly": [[u,v]..] (green outline, image px), "mask": {"ids": path, "palette": path, "mat": name} (red outline)}...]...]}
Each row is scaled to the sheet width keeping the images' aspect ratios at a common height."""
import sys, json
import cv2, numpy as np
from PIL import Image, ImageDraw, ImageFont
C = json.load(open(sys.argv[1]))
WID = C.get('width', 1200)
F = ImageFont.load_default(size=15); FS = ImageFont.load_default(size=13)


def tile(t):
    im = Image.open(t['img'])
    if im.mode == 'RGBA' or t.get('bg'):
        im = im.convert('RGBA'); bg = Image.new('RGBA', im.size, (150, 156, 164, 255)); bg.alpha_composite(im); im = bg
    im = im.convert('RGB')
    W0, H0 = im.size
    ref = t.get('ref_size', [W0, H0])           # the image px frame of poly / crop (photo size)
    sx, sy = W0 / ref[0], H0 / ref[1]
    d = ImageDraw.Draw(im)
    if t.get('mask'):
        mk = t['mask']; pal = json.load(open(mk['palette']))
        ids = np.array(Image.open(mk['ids']).convert('RGBA').resize((W0, H0), Image.NEAREST)).astype(int)
        col = np.array(pal[mk['mat']])
        M = ((np.abs(ids[:, :, :3] - col).sum(2) < 12) & (ids[:, :, 3] > 127)).astype(np.uint8)
        if t.get('crop'):
            x0, y0, x1, y1 = t['crop']; box = np.zeros_like(M); box[int(y0 * sy):int(y1 * sy), int(x0 * sx):int(x1 * sx)] = 1; M &= box
        M = cv2.morphologyEx(M, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8), iterations=2)
        cs, _ = cv2.findContours(M, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
        for c in cs:
            if len(c) > 4:
                d.line([tuple(p[0]) for p in c] + [tuple(c[0][0])], fill=(255, 50, 50), width=max(1, int(2 * sx)))
    if t.get('poly'):
        p = [(u * sx, v * sy) for u, v in t['poly']]
        d.line(p + [p[0]], fill=(40, 255, 40), width=max(1, int(2 * sx)))
    if t.get('crop'):
        x0, y0, x1, y1 = t['crop']; im = im.crop((int(x0 * sx), int(y0 * sy), int(x1 * sx), int(y1 * sy)))
    return im


rows = []
for row in C['rows']:
    ims = [tile(t) for t in row]
    ratio = sum(i.size[0] / i.size[1] for i in ims)
    gap = 6
    h = int((WID - gap * (len(ims) - 1)) / ratio)
    r = Image.new('RGB', (WID, h + 20), 'white'); x = 0
    for t, i in zip(row, ims):
        w = int(round(i.size[0] * h / i.size[1])); r.paste(i.resize((w, h), Image.LANCZOS), (x, 20))
        ImageDraw.Draw(r).text((x + 2, 2), t.get('label', ''), fill=(0, 0, 0), font=FS); x += w + gap
    rows.append(r)
head = 26 + 18 * len(C.get('lines', []))
out = Image.new('RGB', (WID, head + sum(r.size[1] for r in rows) + 4), 'white')
d = ImageDraw.Draw(out)
d.text((6, 4), C['title'], fill=(0, 0, 0), font=F)
for k, l in enumerate(C.get('lines', [])):
    d.text((6, 26 + 18 * k), l, fill=(40, 40, 40), font=FS)
y = head
for r in rows:
    out.paste(r, (0, y)); y += r.size[1]
out.save(C['out'])
print(C['out'], out.size)
