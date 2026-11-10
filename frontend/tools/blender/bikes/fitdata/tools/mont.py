"""mont.py <out> <cols> <width> img... : simple montage"""
import sys
from PIL import Image
out, cols, W = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
ims = [Image.open(f).convert('RGB') for f in sys.argv[4:]]
ims = [im.resize((W, int(im.size[1] * W / im.size[0]))) for im in ims]
H = max(i.size[1] for i in ims)
rows = (len(ims) + cols - 1) // cols
S = Image.new('RGB', (W * cols, H * rows), 'white')
for k, im in enumerate(ims):
    S.paste(im, ((k % cols) * W, (k // cols) * H))
S.save(out)
