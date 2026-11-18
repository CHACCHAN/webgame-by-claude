"""
plan.py: the planform photo (aircraft dark against the sky, seen from below at an angle) -> the silhouette rectified
by an affine map: across = the line between the two wing tips' leading-edge corners (published span 13.05 m), along =
nose -> the middle of that line, scaled so that the silhouette is the published 19.43 m long.

  py.sh plan.py <pl.jpg> <annot.json> <outdir>
Writes plan.png (100 px/m, nose at the top, a 1 m grid, the right half mirrored over the left in red) and plan.json:
{"rows": [[d, [x0, x1], ...]]} (d = metres aft of the nose, runs of dark pixels in metres from the axis, + = left wing).
"""
import json
import sys

import cv2
import numpy as np

src, annot, out = sys.argv[1], sys.argv[2], sys.argv[3]
A = json.load(open(annot))['pl']['pts']
im = cv2.imread(src)
g = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)
g = cv2.GaussianBlur(g, (0, 0), 1.0)
mask = (g < 110).astype(np.uint8)
n, lab, st, cen = cv2.connectedComponentsWithStats(mask, 8)
nose = np.array(A['nose'], float)
li = lab[int(nose[1]) + 25, int(nose[0]) - 3]
m = (lab == li).astype(np.uint8)
SPAN, LEN = 13.05, 19.43
L, R = np.array(A['wtle_l'], float), np.array(A['wtle_r'], float)
# seen from below, the aircraft's left wing is on the picture's right: +x (left) runs from R to L
ex = (L - R) / SPAN
mid = (L + R) / 2
ed0 = (mid - nose)
ys, xs = np.nonzero(m)
P = np.stack([xs, ys], 1).astype(float) - nose
# solve p = x ex + t ed0 for every pixel; t = 1 at the wing tips' station
B = np.linalg.inv(np.stack([ex, ed0], 1))
xt = P @ B.T
t_max = xt[:, 1].max()
t_min = xt[:, 1].min()
d_tip = LEN / (t_max - t_min)        # metres aft of the nose of the wing tips' leading-edge corners
print(f'wing tip LE corner {d_tip:.2f} m aft of the nose; nose at t = {t_min * d_tip:.3f} m')
print('skew of the picture: across . along =', float(ex @ ed0) / np.linalg.norm(ex) / np.linalg.norm(ed0))
S = 100
W, H = int(15 * S), int(20.5 * S)
# inverse map: output (x, d) -> source pixel
jj, ii = np.meshgrid(np.arange(W), np.arange(H))
x = (jj - W / 2) / S
d = ii / S - 0.5
t = d / d_tip + t_min
srcp = nose + x[..., None] * ex + t[..., None] * ed0
rect = cv2.remap(m * 255, srcp[..., 0].astype(np.float32), srcp[..., 1].astype(np.float32), cv2.INTER_LINEAR)
rect = (rect > 127).astype(np.uint8)
flip = rect[:, ::-1]
iou = (rect & flip).sum() / (rect | flip).sum()
print(f'mirror symmetry IoU {iou:.3f}')
pic = np.full((H, W, 3), 255, np.uint8)
pic[rect > 0] = (60, 60, 60)
pic[(flip > 0) & (rect == 0)] = (120, 120, 255)
pic[(flip == 0) & (rect > 0)] = (255, 160, 120)
for i in range(-7, 8):
    cv2.line(pic, (W // 2 + i * S, 0), (W // 2 + i * S, H), (0, 160, 255) if i else (0, 0, 255), 1)
for j in range(0, 21):
    y = int((j + 0.5) * S)
    cv2.line(pic, (0, y), (W, y), (255, 160, 0), 1)
    cv2.putText(pic, str(j), (4, y - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 0), 2)
cv2.imwrite(out + '/plan.png', pic)
cv2.imwrite(out + '/plan_mask.png', rect * 255)
rows = []
for i in range(H):
    xs_ = np.nonzero(rect[i])[0]
    if not len(xs_):
        continue
    runs = []
    s0 = xs_[0]
    for k in range(1, len(xs_)):
        if xs_[k] != xs_[k - 1] + 1:
            runs.append([round((s0 - W / 2) / S, 3), round((xs_[k - 1] - W / 2) / S, 3)])
            s0 = xs_[k]
    runs.append([round((s0 - W / 2) / S, 3), round((xs_[-1] - W / 2) / S, 3)])
    rows.append([round(i / S - 0.5, 3)] + runs)
json.dump({'d_tip': d_tip, 'rows': rows}, open(out + '/plan.json', 'w'))
