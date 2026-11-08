"""bake.py <fitN.json> <state.json> <cams_out.json> : write fitdata/shiden/ffd.json (all lattices, last from state D)
and the state's cameras in silrender format."""
import json, sys
c = json.load(open(sys.argv[1])); s = json.load(open(sys.argv[2]))
Ls = []
for i, L in enumerate(c['lattices']):
    L = dict(L)
    if i == len(c['lattices']) - 1:
        L['D'] = s['D']
    L['D'] = [[round(x, 5) for x in d] for d in L['D']]
    Ls.append(L)
POST = [{'op': 'ends', 'front': [1.0, 0.5, 0.0647], 'rear': [1.0, 0.5, 0.0300],
         'note': 'overhangs lengthened to the official 4285 mm (the photo fit cannot separate length from camera distance)'}]
json.dump({'note': 'FFD lattices (game coords, cubic B-spline) from the photo silhouette fit; applied in order, then post',
           'lattices': Ls, 'post': POST},
          open('/home/dev/Desktop/service/internal/webgame-by-claude/frontend/tools/blender/cars/fitdata/shiden/ffd.json', 'w'),
          separators=(',', ':'))
json.dump({'cams': s['cams']}, open(sys.argv[3], 'w'))
print('baked', len(Ls), 'lattices')
