"""mkfit.py <cams.json> <out fit.json> [--masks]: the fit configuration of the SU7 (photos, bands, ignore boxes) and
the wheel centres read off the photos (annot.json's hub points) as fitdata/su7/det/det_<photo>.json for ffdfit."""
import json
import os
import sys

H = os.path.expanduser('~/.local/opt/carfit/su7')
FIT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
cams, out = sys.argv[1], sys.argv[2]
masks = '--masks' in sys.argv
IGN = {
    'k21': [[0, 430, 420, 853]],            # a black car stands before the tail's lower corner
    'k07': [[640, 300, 1120, 372]],         # this car's spoiler is raised (the model's is retracted)
}
photos = {}
for n in ('k13', 'k14', 'k12', 'k16', 'k21', 'k32', 'k68', 'k00'):
    e = {'photo': f'{H}/ref/{n}.jpg', 'band': float(os.environ.get('BAND', 0.08))}
    if n in IGN:
        e['ignore'] = IGN[n]
    if masks and os.path.exists(f'{H}/masks/{n}_w.png'):
        e['mask'] = f'{H}/masks/{n}_w.png'
    photos[n] = e
annot = json.load(open(f'{FIT}/annot.json'))
os.makedirs(f'{FIT}/det', exist_ok=True)
for n, a in annot.items():
    if n.startswith('_'):
        continue
    det = {}
    for k, xy in a.get('pts', {}).items():
        if k.startswith('hub_'):
            det[f'w{k[4]}_{k[5]}'] = {'centre': xy}
    json.dump(det, open(f'{FIT}/det/det_{n}.json', 'w'))
json.dump({'cams': os.path.abspath(cams), 'photos': photos, 'det': f'{FIT}/det', 'hub_x': {'f': 0.901, 'r': 0.893}},
          open(out, 'w'), indent=1)
print('wrote', out, len(photos))
