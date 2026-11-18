"""endmask.py [check dir]: run after mkmask.py. The masks of the two side photos with the car's ends judged by hand. GrabCut, seeded by the model, had
taken the wall and the bushes behind the tail for the car (the model's tail was longer in these views than the car's),
and boxes over the tail (k13) and over the nose and the upper tail (k14) left the rest out of the fit: so the side
photos never said where the car ends. The outlines are read off zoomed panels of the photos (panels/k13_tl.png,
k13_tail_sil.png, k13_under_r.png, k14_tail2.png, k14_nose.png): inside a box the car is what the polygon holds, the
rest of the box is not car; nothing in the box stays unjudged. The mask as mkmask.py left it is kept beside it
(<n>_w.before_ends.png) and is what a second run starts from; a check picture per box goes to [check dir]. The
precision gate keeps its own copy of a mask (gate/<id>/masks/<n>_shell.png): remove it after a mask has changed.
A lesson for other cars: a mask grown from the model's own outline agrees with the model's mistakes, and a box of
"not judged" over an end of the car takes that end out of the fit; judge the ends in the side photos by hand."""
import os
import shutil
import sys

import cv2
import numpy as np

M = os.path.expanduser('~/.local/opt/carfit/su7/masks')
R = os.path.expanduser('~/.local/opt/carfit/su7/ref')
P = sys.argv[1] if len(sys.argv) > 1 else None
ENDS = {
    'k13': [  # the tail: deck, the lip's tip, under the lip, the lamp's rear edge, the bumper, its black lower part
        ((1150, 325, 1280, 562),
         [(1150, 338.3), (1170, 342.5), (1193.3, 346.7), (1208.3, 350), (1218.3, 355), (1220.8, 359.2), (1216.7, 368.3),
          (1215, 378.3), (1213.3, 382.5), (1223.3, 396.7), (1231.7, 408.3), (1233.3, 413.3), (1236.7, 423.3), (1237.5, 430),
          (1238.3, 446.7), (1240.8, 461.7), (1242.5, 471.7), (1241.7, 485), (1240.8, 496.7), (1239, 513), (1228, 521),
          (1223, 533), (1213, 540), (1150, 555)]),
    ],
    'k14': [
        # the tail: rear glass, deck, the lip's corner, the rear face's far edge, the bumper's corner and underside
        ((1080, 290, 1280, 604),
         [(1080, 347.8), (1098.8, 357.2), (1123.8, 369.7), (1142.5, 375.9), (1183.1, 385.3), (1217.5, 391.6), (1225.3, 394.7),
          (1226.9, 402.5), (1224.4, 415), (1228.4, 427.5), (1237.8, 436.9), (1239.4, 443.1), (1245.6, 452.5), (1245, 477.5),
          (1247.2, 493.1), (1252.5, 502.5), (1251.9, 515), (1247.2, 540), (1242.5, 555.6), (1233.1, 565), (1205, 572.8),
          (1151.9, 585.3), (1111.3, 596.3), (1080, 602.5)]),
        # the nose: wing, the lamp's front, the bumper's corner, its underside to the tyre
        ((90, 430, 220, 609),
         [(220, 430), (190, 442), (170, 452), (154, 460), (136, 470), (122, 480), (112, 490), (107.6, 498), (108, 510),
          (109, 522), (110, 534), (108.4, 542), (108, 558), (109, 570), (111, 580), (118, 585), (136, 590), (156, 594),
          (168, 602), (172, 608), (220, 608)]),
    ],
}
for n, ends in ENDS.items():
    src = f'{M}/{n}_w.png'
    bak = f'{M}/{n}_w.before_ends.png'
    if not os.path.exists(bak):
        shutil.copy(src, bak)
    m = cv2.imread(bak, 0)
    ph = cv2.imread(f'{R}/{n}.jpg')
    for k, ((x0, y0, x1, y1), poly) in enumerate(ends):
        box = m[y0:y1, x0:x1]
        was = ((box == 255).sum(), (box == 0).sum(), (box == 128).sum())
        new = np.zeros_like(box)
        cv2.fillPoly(new, [np.round(np.array(poly, np.float32) - [x0, y0]).astype(np.int32)], 255)
        m[y0:y1, x0:x1] = new
        print(n, k, 'was car/not/unjudged', was, '-> car', int((new == 255).sum()), 'not', int((new == 0).sum()))
        a, b, c, d = max(0, x0 - 40), max(0, y0 - 30), min(m.shape[1], x1 + 10), min(m.shape[0], y1 + 30)
        crop = ph[b:d, a:c].copy()
        mm = m[b:d, a:c]
        crop[mm == 255] = (crop[mm == 255] * 0.65 + np.array([0, 80, 0])).astype(np.uint8)
        crop[mm == 128] = (crop[mm == 128] * 0.65 + np.array([0, 0, 80])).astype(np.uint8)
        if P:
            cv2.imwrite(f'{P}/end_{n}_{k}.png', cv2.resize(crop, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC))
    cv2.imwrite(src, m)
