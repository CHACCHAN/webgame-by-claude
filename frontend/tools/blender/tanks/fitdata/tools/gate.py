"""
gate.py <tris.npz> <fit dir> <out dir> [photos]: the model against the photographs through their solved cameras (the
precision gate of a tank's fit; numbers and overlays, nothing changes).

  <tris.npz>  the model's triangles in the game frame (`<id>.py --dump`: P (n,3,3), O object index, names, zones)
  <fit dir>   fitdata/<id>: fit/ba.json (cameras, each photo's turret traverse psi and gun elevation theta) and
              masks/<photo>.png (white = the tank, black = not, grey 128 = not judged; made by mask.py, the ends
              outlined by hand)
  PHOTOS      the photographs (not in the repository; default ~/.local/opt/carfit/tanks/<id>/ref)
  AXIS        "tz,gy,gz" of the MODEL (traverse axis z, trunnion height and z at 0°): the photo's psi / theta turn the
              model's turret / gun about these (default: read from the npz's `axis` if there, else ba.json's)
  SHIFT       "dy,dz": the model moved by this before judging (the photos' frame has its origin only from guesses: the
              model's origin is the middle of its track contact; the shift that fits best is reported with the gate)

Objects whose name starts with `turret` turn with the photo's psi, `gun` with theta then psi (the dump names them
after their node). Per photo: IoU of the silhouette on the judged pixels, the outline's distance to the photo's
outline (mean / p95, px and cm at the tank's distance), and the share of the model's outline more than 2 % of the
picture's height off. Writes <out>/<photo>_ov.jpg (photo, model outline red, mask outline green, unjudged dimmed)
and <out>/gate.json; prints a table.
"""
import json
import math
import os
import sys

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from ba import project, turret_pose, gun_pose  # noqa: E402


def outline(mask):
    e = cv2.morphologyEx(mask, cv2.MORPH_GRADIENT, np.ones((3, 3), np.uint8))
    return e > 0


def silhouette(uv, W, H):
    m = np.zeros((H, W), np.uint8)
    pts = np.round(uv * 8).astype(np.int32)
    for t in pts:
        cv2.fillConvexPoly(m, t, 255, shift=3)
    return m


def main():
    npz, fit, out = sys.argv[1], sys.argv[2].rstrip('/'), sys.argv[3]
    only = sys.argv[4].split(',') if len(sys.argv) > 4 else None
    Z = np.load(npz, allow_pickle=True)
    P = Z['P'].astype(np.float64)
    O = Z['O']
    names = [str(n) for n in Z['names']]
    ba = json.load(open(fit + '/fit/ba.json'))
    tid = os.path.basename(fit)
    photos_dir = os.environ.get('PHOTOS', os.path.expanduser(f'~/.local/opt/carfit/tanks/{tid}/ref'))
    if 'AXIS' in os.environ:
        tz, gy, gz = (float(v) for v in os.environ['AXIS'].split(','))
    elif 'axis' in Z.files:
        tz, gy, gz = (float(v) for v in Z['axis'])
    else:
        tz, gy, gz = ba['axis']['tz'], ba['axis']['gy'], ba['axis']['gz']
    sy, sz = (float(v) for v in os.environ.get('SHIFT', '0,0').split(','))
    P[..., 1] += sy
    P[..., 2] += sz
    tz, gy, gz = tz + sz, gy + sy, gz + sz
    kind = np.array(['gun' if names[o].startswith('gun') else 'turret' if names[o].startswith('turret') else 'hull' for o in O])
    os.makedirs(out, exist_ok=True)
    rows = {}
    for ph, cam in ba['cams'].items():
        if only and ph not in only:
            continue
        mpath = f'{fit}/masks/{ph}.png'
        if not os.path.exists(mpath):
            continue
        W, H = cam[7]
        pose = ba['pose'][ph]
        psi, th = math.radians(pose['psi_deg']), math.radians(pose['theta_deg'])
        V = P.reshape(-1, 3).copy()
        k3 = np.repeat(kind, 3)
        g = k3 == 'gun'
        V[g] = gun_pose(V[g], th, gy, gz)
        t = (k3 == 'turret') | g
        V[t] = turret_pose(V[t], psi, tz)
        uv = project(cam, V, W, H).reshape(-1, 3, 2)
        sil = silhouette(uv, W, H)
        mask = cv2.imread(mpath, cv2.IMREAD_GRAYSCALE)
        judged = mask != 128
        tank = mask > 200
        s = sil > 0
        inter = (s & tank & judged).sum()
        union = ((s | tank) & judged).sum()
        iou = inter / max(union, 1)
        # outline distances: the model's outline (judged part) to the photo's outline
        mo = outline(sil) & judged
        po = outline(tank.astype(np.uint8) * 255) & judged
        dist = cv2.distanceTransform((~po).astype(np.uint8), cv2.DIST_L2, 5)
        d = dist[mo]
        # cm per px at the tank's middle
        C = np.array(cam[:3])
        depth = float(np.linalg.norm(C - np.array([0, 1.2, 0])))
        cm = depth / cam[6] * 100
        far = float((d > 0.02 * H).mean()) if len(d) else 0.0
        rows[ph] = {'iou': round(float(iou), 4), 'mean_px': round(float(d.mean()), 2) if len(d) else None,
                    'p95_px': round(float(np.percentile(d, 95)), 2) if len(d) else None, 'cm_per_px': round(cm, 2),
                    'p95_cm': round(float(np.percentile(d, 95)) * cm, 1) if len(d) else None, 'far_share': round(far, 4)}
        im = cv2.imread(f'{photos_dir}/{ph}.jpg')
        if im is not None:
            im = cv2.resize(im, (W, H))
            im[~judged] = (im[~judged] * 0.35).astype(np.uint8)
            im[cv2.dilate(po.astype(np.uint8), np.ones((3, 3), np.uint8)) > 0] = (60, 230, 60)
            im[cv2.dilate(mo.astype(np.uint8), np.ones((3, 3), np.uint8)) > 0] = (40, 40, 255)
            txt = f"{ph}  IoU {iou:.3f}  p95 {rows[ph]['p95_px']} px = {rows[ph]['p95_cm']} cm"
            cv2.putText(im, txt, (20, 50), cv2.FONT_HERSHEY_SIMPLEX, 1.4, (0, 0, 0), 6)
            cv2.putText(im, txt, (20, 50), cv2.FONT_HERSHEY_SIMPLEX, 1.4, (255, 255, 255), 2)
            cv2.imwrite(f'{out}/{ph}_ov.jpg', im, [cv2.IMWRITE_JPEG_QUALITY, 85])
    json.dump(rows, open(f'{out}/gate.json', 'w'), indent=1)
    print(f"{'photo':8s} {'IoU':>6s} {'mean px':>8s} {'p95 px':>7s} {'p95 cm':>7s} {'far':>6s}")
    for ph, r in rows.items():
        print(f"{ph:8s} {r['iou']:6.3f} {r['mean_px']!s:>8s} {r['p95_px']!s:>7s} {r['p95_cm']!s:>7s} {r['far_share']:6.3f}")
    if rows:
        print(f"{'mean':8s} {np.mean([r['iou'] for r in rows.values()]):6.3f}            "
              f"{np.mean([r['p95_px'] for r in rows.values() if r['p95_px'] is not None]):7.2f} "
              f"{np.mean([r['p95_cm'] for r in rows.values() if r['p95_cm'] is not None]):7.1f}")


if __name__ == '__main__':
    main()
