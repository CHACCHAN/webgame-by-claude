"""
mkdata.py: su7_data.py from the back-projected traces (tools/trace3d.py output): the head lamp, the tail band (k21's
right half mirrored to the left), the black sections, shut lines, handles, the charge port, the badges' places (the rear's from k21).

  py mkdata.py <traces3d.json> [su7_data.py]
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
T = json.load(open(sys.argv[1]))
P = sys.argv[2] if len(sys.argv) > 2 else os.path.abspath(os.path.join(HERE, '..', '..', '..', 'su7_data.py'))


def pts(photo, key, close=False):
    row = [p for p in T[photo][key] if p is not None]
    if len(row) < len(T[photo][key]):
        print(f'{photo} {key}: {len(T[photo][key]) - len(row)} point(s) off the body, left out')
    if close:
        row = row + row[:1]
    return row


def centred(row):
    """a half outline / line across the centre line: its ends put on x = 0"""
    row = [list(p) for p in row]
    for i in (0, -1):
        if abs(row[i][0]) < 0.12:
            row[i][0] = 0.0
    return row


def fmt(row):
    return '[' + ', '.join('(%.3f, %.3f, %.3f)' % tuple(p) for p in row) + ']'


def wrap(name, row, per=3):
    out = [f'{name} = [']
    for i in range(0, len(row), per):
        out.append('    ' + ', '.join('(%.3f, %.3f, %.3f)' % tuple(p) for p in row[i:i + per]) + ',')
    out.append(']')
    return '\n'.join(out)


HL = pts('k12', 'hl_L')
HLU, HLG = pts('k12', 'hlu_L'), pts('k12', 'hlg_L')
HLS = [pts('k12', 'hls1_L'), pts('k12', 'hls2_L')]
assert len(HLU) == 4, 'a lens unit is off the body'


def lamp_frame(row):
    """the outline's best plane: its middle, the normal (outward) and the long axis (toward the outer side)"""
    import numpy as np
    a = np.array(row)
    c = a.mean(0)
    _u, _s, vt = np.linalg.svd(a - c)
    e1, d = vt[0], vt[2]
    if d @ np.array([0.3, 0.35, 0.9]) < 0:
        d = -d
    if e1[0] < 0:
        e1 = -e1
    return c, d, e1


HL_C, HL_D, HL_E1 = lamp_frame(HL)
# the tail band: across the rear from k21 (the car's right half, mirrored); its end on the flank from the side photo
# k13 (from behind the flank lies along the line of sight: back-projected from k21 alone the tip came out 13 cm short)
_rear = centred(pts('k21', 'tl_R_toL'))
_tip = max(range(len(_rear)), key=lambda i: _rear[i][0])
X_REAR = 0.76
TL = ([p for p in _rear[:_tip] if p[0] < X_REAR] + [list(p) for p in pts('k13', 'tl_L')]
      + [p for p in _rear[_tip + 1:] if p[0] < X_REAR])
assert TL[5] == _rear[5], 'TL_KINK counts from the centre'  
hood = centred(pts('k00', 'hood_L'))
PATCH = [
    ('blade', 'side', 'trim', 0.003, 'LR', pts('k13', 'blade_L')),
    ('curtain', 'fq', 'grille', 0.003, 'LR', pts('k12', 'curtain_L')),
    ('vent', 'rq', 'grille', 0.003, 'LR', pts('k13', 'vent_L')),
    ('intake', 'front', 'grille', 0.003, 'C', centred(pts('k12', 'intake_L'))),
    ('valance', 'rear', 'trim', 0.003, 'C', centred(pts('k21', 'valance_R_toL'))),
    ('insert', 'rear', 'paint', 0.0055, 'LR', pts('k21', 'insert_R_toL')),
    ('recess', 'rear', 'grille', 0.0075, 'LR', pts('k21', 'recess_R_toL')),
    ('reflector', 'rear', 'reflector', 0.0095, 'LR', pts('k21', 'reflector_R_toL')),
]
LINE = [
    ('arch', 'front', 'paint', 0.022, 'LR', pts('k12', 'arch_L')),
    ('hood', 'nose', 'trim', 0.004, 'C', hood),
    ('boot', 'rear', 'trim', 0.004, 'C', centred(pts('k21', 'boot_R_toL'))),
    ('bootside', 'rq', 'trim', 0.004, 'LR', pts('k21', 'bootside_R_toL')),
    # the retracted spoiler's seam on the deck: not traced (no photo shows the deck from above); k32 has it some
    # 7 cm above the lettering, running the lid's width and turning back to the trailing edge at its ends
    ('spoiler', 'top', 'trim', 0.004, 'C',
     [(0.665, 1.0, -2.385), (0.655, 1.0, -2.33), (0.60, 1.0, -2.29), (0.40, 1.0, -2.30), (0.0, 1.0, -2.31)]),
    ('handle_f', 'side', 'trim', 0.005, 'LR', pts('k13', 'handle_f_L', close=True)),
    ('handle_r', 'side', 'trim', 0.005, 'LR', pts('k13', 'handle_r_L', close=True)),
    ('door_f', 'side', 'trim', 0.004, 'LR', pts('k13', 'door_f_L')),
    ('door_b', 'side', 'trim', 0.004, 'LR', pts('k13', 'door_b_L')),
    ('door_r', 'side', 'trim', 0.004, 'LR', pts('k13', 'door_r_L')),
    ('charge', 'side', 'trim', 0.004, 'L', pts('k13', 'charge_L', close=True)),
]
badge = pts('k12', 'badge')[0]
plate_f = pts('k12', 'plate')[0]
letters = pts('k21', 'letters')[0]
model = pts('k21', 'model_R')[0]
plate = pts('k21', 'plate')[0]

old = open(P).read()
doc = old[:old.index('"""', 3) + 3]
fixed = old[old.index('# fixed'):] if '# fixed' in old else '# fixed\nHL_D = (0.45, 0.5, 0.74)\nTL_AXIS = (-1.5, 1.0)\nTL_KINK = 5\nPLATE_F = (0.50, 0.010)\nPLATE_R = (0.43, 0.006)\nLETTER_H = 0.034\n'
t3 = lambda v: '(%.4f, %.4f, %.4f)' % tuple(v)
body = [doc, wrap('HL', HL), 'HL_C, HL_D, HL_E1 = %s, %s, %s' % (t3(HL_C), t3(HL_D), t3(HL_E1)),
        'HLU = ' + fmt(HLU), 'HLG = ' + fmt(HLG), 'HLS = [' + ', '.join(fmt(r) for r in HLS) + ']',
        wrap('TL', TL), 'PATCH = [']
for name, fr, mat, lift, sym, row in PATCH:
    body.append(f'    ({name!r}, {fr!r}, {mat!r}, {lift}, {sym!r},\n     {fmt(row)}),')
body += [']', 'LINE = [']
for name, fr, mat, w, sym, row in LINE:
    body.append(f'    ({name!r}, {fr!r}, {mat!r}, {w}, {sym!r},\n     {fmt(row)}),')
body += [']', 'BADGE_F = (%.3f, %.3f)' % (badge[1], badge[2]), 'LETTER_Y = %.3f' % letters[1],
         'MODEL_BADGE = (%.3f, %.3f)' % (model[0], model[1]), fixed.rstrip('\n')]
text = '\n'.join(body) + '\n'
import re
text = re.sub(r'PLATE_R = \(([0-9.]+), ', 'PLATE_R = (%.3f, ' % plate[1], text)
text = re.sub(r'PLATE_F = \(([0-9.]+), ', 'PLATE_F = (%.3f, ' % plate_f[1], text)
open(P, 'w').write(text)
print('wrote', P)
