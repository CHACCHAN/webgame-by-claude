"""the late bumper lamp traced by hand on the hi-res photos (gridview, ba/*_gridhi*.png), in calibrated px: amber
(ba), clear (bc) and the whole lamp (bl)"""
import json
T = {
 'r03': {'ba_N': [(658.8, 716.3), (680, 717.2), (700, 718.5), (725, 721.5), (750, 725.0), (762.5, 730.0), (762.5, 752), (762.5, 773.6),
                  (750, 771.3), (725, 768.2), (700, 765.3), (680, 762.6), (658.8, 760.2), (658.8, 738)],
         'bc_N': [(763.3, 730.8), (785, 731.6), (809.7, 731.9), (830, 731.0), (846.7, 729.6), (862, 727.6), (872.6, 725.4), (875, 734),
                  (875, 743), (874, 752), (871, 760.7), (860, 764.5), (846.7, 768.0), (830, 771), (809.7, 773.2), (785, 774.2),
                  (763.3, 774.5), (763.3, 752)]},
 'n06': {'ba_N': [(375.8, 746.7), (395, 747.4), (420, 748.3), (439.0, 749.2), (439.0, 767), (439.0, 785.8), (420, 785.5), (395, 785.0),
                  (375.8, 784.6), (375.8, 765)],
         'bc_N': [(440.0, 750.9), (470, 751.0), (500, 751.0), (520, 751.0), (533.5, 751.2), (536.3, 754), (536.4, 768), (536.3, 782),
                  (533.5, 786.5), (520, 786.6), (500, 786.7), (470, 786.7), (440.0, 786.7), (440.0, 768)]},
}
db = json.load(open('lamps.json'))
for ph, ls in T.items():
    for k, p in ls.items():
        db['photos'][ph][k] = {'poly': [list(q) for q in p], 'how': 'hand (hi-res grid) 2026-11-10, late bumper lamp'}
    a, c = ls['ba_N'], ls['bc_N']
    # whole lamp: the amber's top and inner end, the clear's top, outer end and bottom, the amber's bottom
    top = [q for q in a if q[1] < 750 and q[0] < a[5][0] + 0.1][:6] if ph == 'r03' else a[:4]
    whole = top + c[1:-2] + a[7:-1] if ph == 'r03' else a[:4] + c[1:-2] + a[6:-1]
    db['photos'][ph]['bl_N'] = {'poly': [list(q) for q in whole], 'how': 'union of ba_N and bc_N'}
db['kinds']['bc'] = ['headlight']
db['kinds']['ba'] = ['amber']
db['kinds']['bl'] = ['amber', 'headlight']
json.dump(db, open('lamps.json', 'w'), indent=1)
for ph in T:
    print(ph, [tuple(round(v) for v in q) for q in db['photos'][ph]['bl_N']['poly']])
