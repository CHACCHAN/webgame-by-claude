"""zeropose.py <cams.json>: the body poses back to zero (ride height and pitch are found again by the next fit)"""
import json
import sys

c = json.load(open(sys.argv[1]))
for n in c['pose']:
    c['pose'][n] = {'dy': 0.0, 'pitch_deg': 0.0}
json.dump(c, open(sys.argv[1], 'w'), indent=1)
print('poses zeroed')
