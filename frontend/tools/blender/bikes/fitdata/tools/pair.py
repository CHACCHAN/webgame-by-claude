"""pair.py <bike> <loopdir> <photo> <out.png> [crop x0,y0,x1,y1] [height]: photo | shaded fit render side by side"""
import sys, os
from PIL import Image
B = os.path.expanduser('~/.local/opt/carfit/bikes')
bike, ld, n, out = sys.argv[1:5]
ph = Image.open(f'{B}/{bike}/ref/{n}.jpg').convert('RGB')
sh = Image.open(f'{ld}/{n}_shade.png').convert('RGBA').resize(ph.size, Image.LANCZOS)
bg = Image.new('RGBA', ph.size, (200, 205, 210, 255)); bg.alpha_composite(sh); sh = bg.convert('RGB')
if len(sys.argv) > 5 and sys.argv[5] != '-':
    box = tuple(int(v) for v in sys.argv[5].split(',')); ph = ph.crop(box); sh = sh.crop(box)
h = int(sys.argv[6]) if len(sys.argv) > 6 else 700
s = h / ph.size[1]; w = int(ph.size[0] * s)
o = Image.new('RGB', (w * 2 + 6, h), 'white')
o.paste(ph.resize((w, h), Image.LANCZOS), (0, 0)); o.paste(sh.resize((w, h), Image.LANCZOS), (w + 6, 0))
o.save(out)
