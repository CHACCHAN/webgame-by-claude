"""mkfeat.py <traces3d.json> <out feats.json>: feature anchors for ffdfit (--feat): the head lamp's inner tip and the
bonnet's badge, each seen in three photos (k12 front-left, k68 head-on, k00 front-right: the car's right lamp
there, mirrored), and the lamp's four lens units in k12 and k00 only (they sit some 8 cm deep in the lamp: seen
head-on they are not where the surface point is). The design places are k12's back-projection; the fit moves the
field and the cameras until each point lands on its pixel in every photo. Without them the head-on camera stood
8 cm low with a longer lens and showed the lamps' tips 7 cm apart from where the other two photos have them."""
import json
import sys

T = json.load(open(sys.argv[1]))
k12 = T['k12']
F = {'_note': 'design = k12 back-projected (tools/trace3d.py); obs = pixels of the 1280-px photos (":m" = the right lamp)'}
F['hl_tip'] = {'design': k12['hl_L'][0],
               'obs': {'k12': [333.3, 493.3], 'k68': [953, 406.3], 'k68:m': [303, 407.5], 'k00:m': [916, 451.2]}}
names = ['hlu_ui', 'hlu_uo', 'hlu_li', 'hlu_lo']
k12px = [[462.5, 464.2], [495.8, 459.2], [451.7, 491.7], [486.7, 488]]
k68px = [[1065.1, 354.3], [1104.1, 345.8], [1069.2, 407.3], [1108.6, 395.8]]
k00px = [[776, 418], [742, 412], [788, 450], [750, 444]]
for n, p3, a, b, c in zip(names, k12['hlu_L'], k12px, k68px, k00px):
    F[n] = {'design': p3, 'obs': {'k12': a, 'k00:m': c}}       # not k68: the units sit some 8 cm deep in the lamp
b = k12['badge'][0]
F['badge'] = {'design': [0.0, b[1], b[2]], 'obs': {'k68': [630, 330], 'k12': [238, 436], 'k00': [1029.2, 392.8]}}
json.dump(F, open(sys.argv[2], 'w'), indent=1)
for k, v in F.items():
    if not k.startswith('_'):
        print(k, [round(c, 3) for c in v['design']], v['obs'])
