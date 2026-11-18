"""mkmask.py <loop dir> <out dir> [names…]: the photo masks for the fit and the gate, from silfit's GrabCut masks
(<loop dir>/<n>_mask.png, seeded by the model's silhouette <n>_sil.png): white = car, black = not, grey 128 = not
judged. What GrabCut cannot tell is left out: everything from just above the model's lowest line down (the shadow
under the car and the tyres' feet look alike), each photo's boxes (IGN below: another car before this one, a raised
spoiler, bystanders behind the outline) and whatever lies beyond the photo's edge. A check picture per photo
(<out dir>/<n>_chk.jpg: mask outline green, ignored red) is written too. The car's ends in the two side photos
are then judged by hand (endmask.py, which overrules the boxes of k13 and k14 here: under them the fit never saw
where the car ends)."""
import os
import sys

import cv2
import numpy as np

L, O = sys.argv[1], sys.argv[2]
REF = os.path.expanduser('~/.local/opt/carfit/su7/ref')
IGN = {
    'k21': [[0, 430, 420, 853], [290, 100, 850, 196]],
    'k07': [[640, 300, 1120, 372]],
    'k16': [[60, 380, 250, 640], [330, 520, 420, 640], [190, 290, 300, 450]],
    'k12': [[1180, 80, 1280, 240], [1150, 280, 1280, 400]],
    'k14': [[1180, 180, 1280, 330], [30, 455, 112, 535]],
    'k13': [[1180, 330, 1280, 420], [25, 412, 84, 492]],
    'k32': [[0, 150, 270, 460], [820, 0, 1010, 62], [0, 440, 60, 760]],
}
LOW = {'k68': 0.10, 'k32': 0.18}       # share of the car's height above its lowest line that is not judged (default 0.07)
names = sys.argv[3:] or ['k13', 'k14', 'k12', 'k16', 'k21', 'k32', 'k68', 'k00']
os.makedirs(O, exist_ok=True)
for n in names:
    photo = cv2.imread(f'{REF}/{n}.jpg')
    h, w = photo.shape[:2]
    P = cv2.imread(f'{L}/{n}_mask.png', cv2.IMREAD_GRAYSCALE)
    P = cv2.resize(P, (w, h), interpolation=cv2.INTER_NEAREST)
    R = cv2.imread(f'{L}/{n}_sil.png', cv2.IMREAD_UNCHANGED)[:, :, 3]
    R = cv2.resize(R, (w, h), interpolation=cv2.INTER_NEAREST) > 127
    ys, xs = np.nonzero(R)
    bh = ys.max() - ys.min() + 1
    low = np.full(w, -1, int)
    for x in range(xs.min(), xs.max() + 1):
        col = np.nonzero(R[:, x])[0]
        if len(col):
            low[x] = col.max()
    valid = np.nonzero(low >= 0)[0]
    low = np.interp(np.arange(w), valid, low[valid]).astype(int)       # carried on sideways, past the car's ends
    m = P.copy()
    m[(m > 0) & (m < 255)] = 128
    cut = low - int(round(LOW.get(n, 0.07) * bh))
    yy = np.arange(h)[:, None]
    m[yy > cut[None, :]] = 128
    for x0, y0, x1, y1 in IGN.get(n, []):
        m[y0:y1, x0:x1] = 128
    cv2.imwrite(f'{O}/{n}_w.png', m)
    chk = (photo * 0.6).astype(np.uint8)
    chk[m == 128] = (chk[m == 128] * 0.5 + np.array([0, 0, 110])).astype(np.uint8)
    cnt, _ = cv2.findContours((m == 255).astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    cv2.drawContours(chk, cnt, -1, (0, 255, 0), 2)
    cv2.imwrite(f'{O}/{n}_chk.jpg', chk, [cv2.IMWRITE_JPEG_QUALITY, 80])
    print(n, 'car', int((m == 255).sum()), 'ignored', int((m == 128).sum()))
