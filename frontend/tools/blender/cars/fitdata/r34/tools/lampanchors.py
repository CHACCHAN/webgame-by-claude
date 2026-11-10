"""lampanchors.py (Blender): the lamps as camera anchors. Points that are easy to find on the photos (the head lamps'
inner corners, the indicators' and the round tail lamps' centres) are paired with the same points of the design
(r34_fit: head lamps by Unrolled, indicators and tail lamps by ray casts), moved by the starting FFD field (the
anchors are given in the fitted frame; ffdfit --bodyanchors pulls them back through it). Left/right pairs tie the
cameras' roll and yaw, which the silhouettes hardly hold. Appends them (body flag 1, weight w) to an anchors file.

  blender.sh -b --factory-startup --python lampanchors.py -- <anchors_in.json> <lattice.json> <lamps.json> <anchors_out.json> [--w 0.4]
"""
import json, os, sys

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, '..', '..', '..')))
import bpy
import numpy as np

argv = sys.argv[sys.argv.index('--') + 1:]
anc = json.load(open(argv[0]))
import r34
import r34_body
import r34_ffd
import r34_fit as FIT
import r34_kit as K
K.clear_scene()
r34_body.CUT_FRONT = False
L = r34_ffd.Lattice.load(argv[1])
root, mats, _ = r34.build({'ffd': False})
lamps = json.load(open(argv[2]))['photos']
w = float(argv[argv.index('--w') + 1]) if '--w' in argv else 0.4
shell = bpy.data.objects['shell']
surf = FIT.Surface(shell)
U = FIT.Unrolled(surf)


def hl_point(kind, a, y, side):
    p, _ = U.at(U.s_of(kind, a, y), y, 0.003)
    return p * np.array((side, 1, 1))


def front_point(x, y, side):
    return surf.onto(abs(x), y, 'z', 1, 0.0025) * np.array((side, 1, 1))


def tail_point(x, y, side):
    return surf.onto(abs(x), y, 'z', -1) * np.array((side, 1, 1)) + np.array((0, 0, 0.006))


ic = np.array(FIT.INDICATOR).mean(axis=0)
pts3 = {
    'hl_in_top': lambda s: hl_point('x', 0.452, 0.712, s),
    'hl_in_bot': lambda s: hl_point('x', 0.456, 0.602, s),
    'ind': lambda s: front_point(ic[0], ic[1], s),
    'tl_O': lambda s: tail_point(FIT.TAIL_LAMPS[0][0], FIT.TAIL_LAMPS[0][1], s),
    'tl_I': lambda s: tail_point(FIT.TAIL_LAMPS[1][0], FIT.TAIL_LAMPS[1][1], s),
}


def img_pts(ph, lamp):
    d = lamps[ph][lamp]
    P = np.array(d['poly'], float)
    if lamp.startswith('tl'):
        return {'tl_' + lamp[-1]: d['ellipse'][:2]}
    if lamp.startswith('ind'):
        return {'ind': P.mean(axis=0).tolist()}
    if lamp.startswith('hl'):
        # inner corners: the outline's points nearest the car's centre line, top and bottom
        side = 1 if lamp.endswith('L') else -1
        return dict(INNER[ph][lamp])
    return {}


# the head lamps' inner corners as traced (pixel points of the outlines in lamps.json)
INNER = {'r29': {'hl_R': {'hl_in_top': [433.0, 420.5], 'hl_in_bot': [439.0, 476.0]},
                 'hl_L': {'hl_in_top': [840.0, 427.5], 'hl_in_bot': [840.0, 472.5]}},
         'r07': {'hl_L': {'hl_in_top': [318.75, 411.25], 'hl_in_bot': [306.25, 458.75]}}}
for ph, ls in lamps.items():
    if ph not in anc or anc[ph] is None:
        anc[ph] = anc.get(ph) or []
    for lamp in ls:
        side = 1 if lamp.split('_')[1].startswith('L') else -1
        for key, uv in img_pts(ph, lamp).items():
            P = pts3[key](side)
            Pd = P + L.displace(P[None])[0]
            anc[ph].append([round(float(v), 4) for v in Pd] + [round(float(uv[0]), 2), round(float(uv[1]), 2), w, w, 1, 0])
            print(ph, lamp, key, np.round(P, 3), '->', np.round(Pd, 3), uv)
json.dump(anc, open(argv[3], 'w'))
