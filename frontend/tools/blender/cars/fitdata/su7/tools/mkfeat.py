"""mkfeat.py <traces3d.json> <out feats.json>: feature anchors for ffdfit (--feat). Front: the head lamp's inner tip
and the bonnet's badge, each seen in three photos (k12 front-left, k68 head-on, k00 front-right: the car's right lamp
there, mirrored), and the lamp's four lens units in k12 and k00 only (they sit some 8 cm deep in the lamp: seen head-on
they are not where the surface point is); design places = k12's back-projection. Without them the head-on camera stood
8 cm low with a longer lens. Rear: the tail band's tip on the flank, whose place the side photo k13 gives (the flank
lies at the wheels' depth there), seen in k14 and on both sides in k21 (":m" = the car's right), and the middle of the
boot lid's lettering and of the plate on the centre line: the photo from behind stood 9 cm beside the car's middle."""
import json
import sys

T = json.load(open(sys.argv[1]))
k12 = T['k12']
F = {'_note': 'design = back-projected (tools/trace3d.py: front k12, tail tip k13); obs = pixels of the 1280-px photos (":m" = the car\'s right side)'}
F['hl_tip'] = {'design': k12['hl_L'][0],
               'obs': {'k12': [333.3, 493.3], 'k68': [953, 406.3], 'k68:m': [303, 407.5], 'k00:m': [916, 451.2]}}
names = ['hlu_ui', 'hlu_uo', 'hlu_li', 'hlu_lo']
k12px = [[462.5, 464.2], [495.8, 459.2], [451.7, 491.7], [486.7, 488]]
k00px = [[776, 418], [742, 412], [788, 450], [750, 444]]
for n, p3, a, c in zip(names, k12['hlu_L'], k12px, k00px):
    F[n] = {'design': p3, 'obs': {'k12': a, 'k00:m': c}}
b = k12['badge'][0]
F['badge'] = {'design': [0.0, b[1], b[2]], 'obs': {'k68': [630, 330], 'k12': [238, 436], 'k00': [1029.2, 392.8]}}
F['tl_tip'] = {'design': T['k13']['tl_L'][6],
               'obs': {'k13': [1151.9, 408.75], 'k14': [1067.4, 453.1], 'k21:m': [742.5, 434]}}   # (k21 sees only the corner of the far lamp)
le = T['k21']['letters'][0]
F['letters'] = {'design': [0.0, le[1], le[2]], 'obs': {'k21': [331, 402.5]}}
pl = T['k21']['plate'][0]
F['plate_r'] = {'design': [0.0, pl[1], pl[2]], 'obs': {'k21': [330, 600]}}
json.dump(F, open(sys.argv[2], 'w'), indent=1)
for k, v in F.items():
    if not k.startswith('_'):
        print(k, [round(c, 3) for c in v['design']], v['obs'])
