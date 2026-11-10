"""
lampscore.py: our lamp panel's outlines (l0_shape: lamp windows, camera windows; laid on the shell along −z as the
model's plates are) through a photo's solved camera, against the outlines traced on the photo (lamps.json).

  py lampscore.py <cams.json> <workdir> <lamps.json> <shape.json> [--photos c07,c12] [--sheet out_dir]
      -> per photo and part: IoU, outline distance p95 / max (px); with --sheet, crops for the sheet:
         <out_dir>/lamp_<photo>_photo.png (the photo), _lines.png (traced green, ours magenta)
"""
import json, math, os, sys

import cv2
import numpy as np

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, '..', '..', '..', 'parts'))
import cam as C
import l0_shape as S
import measure as M


def rrect(cx, cy, w, h, r, n=10):
    pts = []
    for (ox, oy, a0) in ((cx + w / 2 - r, cy + h / 2 - r, 0), (cx - w / 2 + r, cy + h / 2 - r, 90),
                         (cx - w / 2 + r, cy - h / 2 + r, 180), (cx + w / 2 - r, cy - h / 2 + r, 270)):
        for k in range(n + 1):
            a = math.radians(a0 + 90 * k / n)
            pts.append((ox + r * math.cos(a), oy + r * math.sin(a)))
    return pts


def ours():
    x0, x1, y0, y1, r = S.LAMP_WIN
    out = {'lamp_l': rrect((x0 + x1) / 2, (y0 + y1) / 2, x1 - x0, y1 - y0, r),
           'lamp_r': rrect(-(x0 + x1) / 2, (y0 + y1) / 2, x1 - x0, y1 - y0, r)}
    x, y, w, h = S.CAM_WIN
    out['cam'] = rrect(x, y, w, h, 0.012)
    x, y, w, h = S.CAM_LOW
    out['cam_low'] = rrect(x, y, w, h, 0.012)
    return out


def laid(pts2, V, F):
    P = []
    for x, y in pts2:
        h = M.hit_mesh(np.array([x, y, 40.0]), np.array([0.0, 0.0, -1.0]), V, F)
        P.append(h if h is not None else [x, y, S.NOSE_TIP])
    return np.array(P)


def score(poly_a, poly_b, W, H, scale=4):
    """IoU and outline distances (px) of two polygons (px), drawn at `scale`× for sub-pixel accuracy"""
    a = np.zeros((H * scale // 8 + 1, W * scale // 8 + 1), np.uint8)
    xs = np.concatenate([poly_a[:, 0], poly_b[:, 0]])
    ys = np.concatenate([poly_a[:, 1], poly_b[:, 1]])
    ox, oy = xs.min() - 10, ys.min() - 10
    w, h = int((xs.max() - ox + 20) * scale), int((ys.max() - oy + 20) * scale)
    ma, mb = np.zeros((h, w), np.uint8), np.zeros((h, w), np.uint8)
    cv2.fillPoly(ma, [np.round((poly_a - [ox, oy]) * scale * 16).astype(np.int32)], 1, shift=4)
    cv2.fillPoly(mb, [np.round((poly_b - [ox, oy]) * scale * 16).astype(np.int32)], 1, shift=4)
    iou = (ma & mb).sum() / max((ma | mb).sum(), 1)
    ea = ma - cv2.erode(ma, np.ones((3, 3), np.uint8))
    eb = mb - cv2.erode(mb, np.ones((3, 3), np.uint8))
    da = cv2.distanceTransform((1 - ea).astype(np.uint8), cv2.DIST_L2, 5)
    db = cv2.distanceTransform((1 - eb).astype(np.uint8), cv2.DIST_L2, 5)
    d = np.concatenate([db[ea > 0], da[eb > 0]]) / scale
    return float(iou), float(np.percentile(d, 95)), float(d.max())


def main():
    a = sys.argv[1:]

    def opt(k, d=None):
        return a[a.index(k) + 1] if k in a else d
    cams = json.load(open(a[0]))['cams']
    wd = a[1]
    traces = json.load(open(a[2]))
    if a[3] != '-':
        S.load_shape(json.load(open(a[3])))
    V, F = S.shell_mesh('end')
    near = V[:, 2] > S.NOSE_TIP - 1.5
    keep = near[F].any(1)
    F = F[keep]
    mine = {k: laid(v, V, F) for k, v in ours().items()}
    photos = opt('--photos', ','.join(k for k in traces if not k.startswith('_'))).split(',')
    sheet = opt('--sheet')
    allr = []
    for p in photos:
        c = cams[p]
        W, H = c[7]
        lines = []
        for name, tr in traces[p].items():
            tr = np.array(tr, float)
            pr = C.project(c[:7], mine[name], W, H)[:, :2]
            iou, p95, mx = score(pr, tr, W, H)
            allr.append((p, name, iou, p95, mx))
            print(f'{p} {name:8s} IoU {iou:.3f}  outline p95 {p95:.2f} px  max {mx:.2f} px')
            lines.append((tr, pr))
        if sheet:
            os.makedirs(sheet, exist_ok=True)
            img = cv2.imread(os.path.join(wd, 'work', p + '.jpg'))
            pts = np.vstack([np.vstack([t, q]) for t, q in lines])
            x0, y0 = pts.min(0) - 25
            x1, y1 = pts.max(0) + 25
            x0, y0, x1, y1 = int(max(x0, 0)), int(max(y0, 0)), int(min(x1, W)), int(min(y1, H))
            k = 900 / (x1 - x0)
            full = cv2.imread(os.path.join(wd, 'full', p + '.jpg'))
            src = full if full is not None else img
            f = src.shape[1] / W
            crop = src[int(y0 * f):int(y1 * f), int(x0 * f):int(x1 * f)]
            crop = cv2.resize(crop, (int((x1 - x0) * k), int((y1 - y0) * k)), interpolation=cv2.INTER_CUBIC)
            cv2.imwrite(os.path.join(sheet, f'lamp_{p}_photo.png'), crop)
            ov = (crop * 0.55 + 255 * 0.45).astype(np.uint8)
            for t, q in lines:
                cv2.polylines(ov, [np.round((t - [x0, y0]) * k * 16).astype(np.int32)], True, (0, 170, 0), 2, cv2.LINE_AA, 4)
                cv2.polylines(ov, [np.round((q - [x0, y0]) * k * 16).astype(np.int32)], True, (200, 0, 200), 2, cv2.LINE_AA, 4)
            cv2.imwrite(os.path.join(sheet, f'lamp_{p}_lines.png'), ov)
            json.dump({'box': [x0, y0, x1, y1], 'k': k}, open(os.path.join(sheet, f'lamp_{p}_box.json'), 'w'))
    json.dump(allr, open(os.path.join(sheet or '.', 'lampscore.json'), 'w'))


if __name__ == '__main__':
    main()
