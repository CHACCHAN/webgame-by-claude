"""
sil.py: the model's silhouette from a solved camera (numpy + OpenCV, no Blender), and its comparison with a photo mask.

  py sil.py overlay <cams.json> <photo> <workdir> <out.png> [--shape shape.json] [--cars 3]
      the photo with the model's outline (magenta) and the mask's (green, if <workdir>/masks/<photo>.png exists)
  py sil.py score <cams.json> <workdir> [--photos a,b] [--shape shape.json]
      IoU and outline distances (p95, max; px of the working copy) per photo, over the mask's car / not-car pixels

Masks: <workdir>/masks/<photo>.png, 255 train, 0 not train, 128 ignore (occluders: the guideway's walls, masts,
anything in front of the train, and the train beyond the three cars the model has).
Shape: an optional JSON {"nose": [[d, top, yw, hw, bot, nt, nb, lean, tuck], ...], "body": {...}} replacing l0_shape's
table (the fit's working shape).
"""
import json, os, sys

import cv2
import numpy as np

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, '..', '..', '..', 'parts'))
import cam as C
import l0_shape as S


def load_shape(path):
    if path and os.path.exists(path):
        sh = json.load(open(path))
        S.load_shape(sh)


_MESH = {}


def train_mesh(key='3'):
    if key not in _MESH:
        _MESH.clear()
        _MESH[key] = S.train_mesh()
    return _MESH[key]


def raster(cam, W, H, V=None, F=None, scale=1):
    """the model's silhouette (bool H × W) from a camera"""
    if V is None:
        V, F = train_mesh()
    P = C.project(cam, V, W, H)
    ok = P[:, 2] > 0.1
    tri = F[ok[F].all(1)]
    pts = np.round(P[:, :2] * 16 * scale).astype(np.int32)[tri]
    m = np.zeros((H * scale, W * scale), np.uint8)
    # one triangle at a time (fillPoly with many contours fills by parity: overlaps would cancel)
    for t in pts:
        cv2.fillConvexPoly(m, t, 1, lineType=cv2.LINE_8, shift=4)
    return m > 0


def edge(m):
    m8 = m.astype(np.uint8)
    return (m8 - cv2.erode(m8, np.ones((3, 3), np.uint8))) > 0


def compare(model, mask):
    """IoU over the decided pixels, and the outline distances both ways (p95, max) where the mask decides"""
    car = mask == 255
    known = mask != 128
    inter = (model & car & known).sum()
    union = ((model | car) & known).sum()
    iou = inter / max(union, 1)
    # outlines, away from the ignored pixels (a band of 3 px round them)
    ign = cv2.dilate((~known).astype(np.uint8), np.ones((7, 7), np.uint8)) > 0
    em = edge(model) & ~ign
    ep = edge(car) & ~ign
    dt_p = cv2.distanceTransform((~ep).astype(np.uint8), cv2.DIST_L2, 5)
    dt_m = cv2.distanceTransform((~em).astype(np.uint8), cv2.DIST_L2, 5)
    d = np.concatenate([dt_p[em], dt_m[ep]]) if em.any() and ep.any() else np.array([99.0])
    return dict(iou=float(iou), p95=float(np.percentile(d, 95)), max=float(d.max()), mean=float(d.mean()))


def overlay(photo_path, model, mask=None):
    img = cv2.imread(photo_path)
    H, W = model.shape
    img = cv2.resize(img, (W, H)) if img.shape[:2] != (H, W) else img
    out = img.copy()
    if mask is not None:
        out[edge(mask == 255)] = (0, 220, 0)
        ign = mask == 128
        out[ign] = (out[ign] * 0.6 + np.array([90, 90, 90]) * 0.4).astype(np.uint8)
    e = cv2.dilate(edge(model).astype(np.uint8), np.ones((2, 2), np.uint8)) > 0
    out[e] = (255, 0, 255)
    return out


def main():
    a = sys.argv[1:]
    cmd = a[0]

    def opt(k, d=None):
        return a[a.index(k) + 1] if k in a else d
    load_shape(opt('--shape'))
    if cmd == 'overlay':
        cams, photo, wd, out = json.load(open(a[1]))['cams'], a[2], a[3], a[4]
        c = cams[photo]
        W, H = c[7]
        m = raster(c[:7], W, H)
        mp = os.path.join(wd, 'masks', photo + '.png')
        mask = cv2.imread(mp, cv2.IMREAD_GRAYSCALE) if os.path.exists(mp) else None
        cv2.imwrite(out, overlay(os.path.join(wd, 'work', photo + '.jpg'), m, mask))
        if mask is not None:
            print(photo, compare(m, mask))
    elif cmd == 'score':
        cams, wd = json.load(open(a[1]))['cams'], a[2]
        only = opt('--photos')
        for p, c in cams.items():
            if only and p not in only.split(','):
                continue
            mp = os.path.join(wd, 'masks', p + '.png')
            if not os.path.exists(mp):
                continue
            W, H = c[7]
            r = compare(raster(c[:7], W, H), cv2.imread(mp, cv2.IMREAD_GRAYSCALE))
            print(f'{p}: IoU {r["iou"]:.4f}  outline p95 {r["p95"]:.2f} px  max {r["max"]:.1f} px  mean {r["mean"]:.2f}')


if __name__ == '__main__':
    main()
