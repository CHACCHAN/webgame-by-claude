"""cmp.py: photo | render | blend crops side by side.
  py cmp.py <photo> <render> <x0,y0,x1,y1 | full> <out.jpg> [--h 360]
The render is at the photo's calibrated size; the photo is resized to it."""
import sys
from PIL import Image
a = sys.argv[1:]
ph = Image.open(a[0]).convert('RGB')
rd = Image.open(a[1]).convert('RGB')
if ph.size != rd.size:
    ph = ph.resize(rd.size, Image.LANCZOS)
box = None if a[2] == 'full' else tuple(int(float(v)) for v in a[2].split(','))
H = int(a[a.index('--h') + 1]) if '--h' in a else 360
p = ph.crop(box) if box else ph
r = rd.crop(box) if box else rd
b = Image.blend(p, r, 0.5)
k = H / p.height
p, r, b = (im.resize((round(im.width * k), H), Image.LANCZOS) for im in (p, r, b))
out = Image.new('RGB', (p.width * 3 + 8, H), (255, 255, 255))
for i, im in enumerate((p, r, b)):
    out.paste(im, (i * (p.width + 4), 0))
out.save(a[3], quality=90)
