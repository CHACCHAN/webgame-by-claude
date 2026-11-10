"""
mkdata.py: u9_data.py from the back-projected traces (tools/trace3d.py output): the head lamp (c12 hl_R mirrored to
the left), its gate bars, the paint edges, the tail band, the number plate, the hood's shut line; the docstring and the
fixed constants are kept from the current u9_data.py (everything after the line '# fixed').

  py mkdata.py <traces3d.json> [u9_data.py] [--lamps lampfit.json (HL / TL moved by tools/lampfit.py)]
"""
import json, os, re, sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
args = [a for i, a in enumerate(sys.argv[1:]) if a != '--lamps' and (i == 0 or sys.argv[i] != '--lamps')]
LF = json.load(open(sys.argv[sys.argv.index('--lamps') + 1])) if '--lamps' in sys.argv else {}
P = args[1] if len(args) > 1 else os.path.abspath(os.path.join(HERE, '..', '..', '..', 'u9_data.py'))
d = json.load(open(args[0]))
src = open(P).read()
doc = src[:src.index('"""', 3) + 4]
fixed = src[src.index('# fixed'):] if '# fixed' in src else ''
r3 = lambda p: tuple(round(float(v), 3) for v in p)
t3 = lambda p: '(' + ', '.join(f'{v:.3f}' for v in p) + ')'


def fmt(name, pts, per=3):
    s = f'{name} = [\n'
    row = []
    for p in pts:
        row.append(t3(p))
        if len(row) == per:
            s += '    ' + ', '.join(row) + ',\n'
            row = []
    if row:
        s += '    ' + ', '.join(row) + ',\n'
    return s + ']\n'


hl = [r3(p) for p in LF['HL']] if 'HL' in LF else [r3((-p[0], p[1], p[2])) for p in d['c12']['hl_R']]
fp = [r3(q) for q in d['c12']['fpaint_R'] if q]
fp[-1] = (0.0,) + fp[-1][1:]
tl = [r3(q) for q in (LF['TL'] if 'TL' in LF else d['c18']['tl_L'])]
tl[0], tl[-1] = (0.0,) + tl[0][1:], (0.0,) + tl[-1][1:]
rp = [r3(q) for q in d['c18']['rpaint_L']]
H = np.array(hl)


def along(idx, t):
    Q = H[idx]
    seg = np.linalg.norm(np.diff(Q, axis=0), axis=1)
    c = np.concatenate([[0], np.cumsum(seg)])
    x = t * c[-1]
    j = min(np.searchsorted(c, x, side='right') - 1, len(Q) - 2)
    u = (x - c[j]) / max(seg[j], 1e-9)
    return Q[j] + (Q[j + 1] - Q[j]) * u


bars = []
for k in range(18):
    t = 0.03 + 0.89 * k / 17
    a, b = along(list(range(9, 19)), t), along(list(range(25, 17, -1)), t)
    bars.append((a + (b - a) * 0.16, a + (b - a) * 0.84))
out = doc + fmt('HL', hl)
out += 'HL_OUTER = 19                # HL[:19] is the outer contour (inner tip of the upper arm -> lower arm tip)\n'
out += 'HL_BARS = [\n' + ''.join(f'    ({t3(a)}, {t3(b)}),\n' for a, b in bars) + ']\n'
out += fmt('FPAINT', fp) + fmt('TL', tl) + fmt('RPAINT', rp)
c12 = d['c12']
if c12.get('plate'):                 # the number plate: a symmetric rectangle (half width, bottom, top, z)
    pl = np.array([q for q in c12['plate'] if q])
    out += f'PLATE = ({np.abs(pl[:, 0]).mean():.3f}, {pl[:, 1].min():.3f}, {pl[:, 1].max():.3f}, {pl[:, 2].mean():.3f})\n'
if d['c18'].get('plate'):            # and the rear one
    pl = np.array([q for q in d['c18']['plate'] if q])
    out += f'PLATE_R = ({np.abs(pl[:, 0]).mean():.3f}, {pl[:, 1].min():.3f}, {pl[:, 1].max():.3f}, {pl[:, 2].mean():.3f})\n'
for ph, key in (('c12', 'BADGE_F'), ('c18', 'BADGE_R')):     # the emblems' centres (y, z) on the centre line
    if d[ph].get('badge') and d[ph]['badge'][0]:
        q = d[ph]['badge'][0]
        out += f'{key} = ({q[1]:.3f}, {q[2]:.3f})\n'
if c12.get('hoodline_R'):            # the hood's front shut line, right inner lamp tip -> centre, mirrored across
    hr = [r3(q) for q in c12['hoodline_R'] if q]
    hr[-1] = (0.0,) + hr[-1][1:]
    out += fmt('HOODLINE', hr + [(-p[0], p[1], p[2]) for p in reversed(hr[:-1])])
# the side (c14, the right side mirrored to the left): the dark intake slot and the sill as one outline (its lower edge,
# under the car's side out of the photo's sight, at y 0.15), the black strip along the side, the door's shut lines
c14 = d.get('c14', {})
L_ = lambda pts: [r3((-p[0], p[1], p[2])) for p in pts if p]
if 'side_R' in c14:
    side = L_(c14['side_R'])
    side += [(0.95, 0.15, side[-1][2]), (0.95, 0.15, side[0][2])]
    out += fmt('SIDE', side) + fmt('CHARLINE', L_(c14['charline_R']))
    out += 'DOOR_LINES = [\n' + ''.join('    [' + ', '.join(t3(p) for p in L_(c14[k])) + '],\n'
                                       for k in ('doorrear_R', 'doorfront_R') if k in c14) + ']\n'
out += fixed or ('# fixed: estimated or read off the photos by hand (kept by tools/mkdata.py)\n'
                 'HL_D = (0.25, 0.60, 0.76)\nHL_UV = (0.0, 0.0, 0.9, 0.9)\nUV_WHITE = (0.975, 0.975)\n'
                 'FRONT_BLACK_BOTTOM = 0.10\nDIFFUSER_TOP = 0.585\nDIFFUSER_BOTTOM = 0.31\nFIN_X = (0.07, 0.375, 0.74)\n'
                 'SPLIT_HALF = 0.97\nSPLIT_Z = 2.52\nSPLIT_SWEEP = 0.22\nSPLIT_Y = 0.085\n')
open(P, 'w').write(out)
print('wrote', P)
