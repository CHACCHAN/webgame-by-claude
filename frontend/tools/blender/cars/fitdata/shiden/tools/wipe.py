"""wipe.py <photo> <render> x0,y0,x1,y1 <out> [--step 40] [--k 3]: photo / render in alternating vertical stripes"""
import sys
import numpy as np
from PIL import Image
a = sys.argv[1:]
rd = Image.open(a[1]).convert('RGB')
ph = Image.open(a[0]).convert('RGB').resize(rd.size, Image.LANCZOS)
box = tuple(int(v) for v in a[2].split(','))
st = int(a[a.index('--step') + 1]) if '--step' in a else 40
k = float(a[a.index('--k') + 1]) if '--k' in a else 3
A = np.array(ph.crop(box)); B = np.array(rd.crop(box))
o = A.copy()
for x in range(0, A.shape[1], st):
    o[:, x + st // 2:x + st] = B[:, x + st // 2:x + st]
Image.fromarray(o).resize((int(A.shape[1] * k), int(A.shape[0] * k)), Image.LANCZOS).save(a[3])
