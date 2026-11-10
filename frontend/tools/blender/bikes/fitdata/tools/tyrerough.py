"""tyrerough.py <rims.json> <out.json> <kf> <kr> : rough tyre outlines = the rim lip ellipses scaled about their centres"""
import sys, json, math
R = json.load(open(sys.argv[1])); k = {'f': float(sys.argv[3]), 'r': float(sys.argv[4])}
out = {}
for w, v in R.items():
    cx, cy, a, b, ang = v['ellipse']; t = math.radians(ang); a *= k[w]; b *= k[w]
    out[w] = [[cx + a * math.cos(q) * math.cos(t) - b * math.sin(q) * math.sin(t), cy + a * math.cos(q) * math.sin(t) + b * math.sin(q) * math.cos(t)]
              for q in [i * 2 * math.pi / 12 for i in range(12)]]
json.dump(out, open(sys.argv[2], 'w'))
