"""blend.py <photo> <shade.png> <out.png>: photo | photo with the model's shaded render laid over at 55 % | the render on grey"""
import sys
from PIL import Image
ph, sh, out = sys.argv[1:4]
r = Image.open(sh).convert('RGBA')
p = Image.open(ph).convert('RGB').resize(r.size, Image.LANCZOS)
a = r.split()[3].point(lambda v: int(v * 0.55))
bl = p.copy()
bl.paste(r.convert('RGB'), (0, 0), a)
grey = Image.new('RGB', r.size, (90, 96, 104))
grey.paste(r.convert('RGB'), (0, 0), r.split()[3])
W, H = r.size
o = Image.new('RGB', (3 * W + 16, H), 'white')
for i, im in enumerate((p, bl, grey)):
    o.paste(im, (i * (W + 8), 0))
o.save(out)
