"""p2mask.py <segdir> <outdir> names [fit.json state.json] : probability map -> mask (255 car p>0.6 in the largest
blob, 128 for 0.35..0.6, 0 else). With a fit state: rays that miss the car's box (+MARGIN) -> 0, rays entering the
box below YLOW (ground shadow / reflections under the car) -> 128."""
import sys, os, json
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cv2, numpy as np
import fitlib as F
MARGIN, YLOW = float(os.environ.get('MARGIN', 0.06)), float(os.environ.get('YLOW', 0.10))
sd, od = sys.argv[1], sys.argv[2]; os.makedirs(od, exist_ok=True)
st = None
if len(sys.argv) > 5:
    cfg = json.load(open(sys.argv[4])); st = json.load(open(sys.argv[5]))
    Vb = np.load(cfg['mesh'])['body_v']
def boxtest(c, W, H):
    lo = Vb.min(0) - MARGIN; hi = Vb.max(0) + MARGIN; lo[1] = 0.0
    d, r, u = F.basis(*c[3:6]); f = c[6]
    xs, ys = np.meshgrid(np.arange(W, dtype=np.float32) + 0.5, np.arange(H, dtype=np.float32) + 0.5)
    D = d[None, None] * f + r[None, None] * (xs - W / 2)[..., None] - u[None, None] * (ys - H / 2)[..., None]
    C = np.array(c[:3])
    with np.errstate(divide='ignore', invalid='ignore'):
        t1 = (lo - C) / D; t2 = (hi - C) / D
    tmin = np.nanmax(np.minimum(t1, t2), axis=2); tmax = np.nanmin(np.maximum(t1, t2), axis=2)
    miss = (tmax < tmin) | (tmax < 0)
    ent = C[None, None] + D * tmin[..., None]
    return miss, ~miss & (ent[..., 1] < YLOW)
for n in sys.argv[3].split(','):
    p = cv2.imread(f'{sd}/{n}_p.png', cv2.IMREAD_GRAYSCALE).astype(np.float32) / 255
    car = p > 0.6
    if st is not None:
        miss, low = boxtest(st['cams'][n], p.shape[1], p.shape[0])
        car &= ~miss
    k, lab, stats, _ = cv2.connectedComponentsWithStats(car.astype(np.uint8), 8)
    big = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    m = np.zeros(p.shape, np.uint8)
    m[(p >= 0.35)] = 128
    m[lab == big] = 255
    if st is not None:
        m[miss] = 0
        m[low] = 128
    cv2.imwrite(f'{od}/{n}.png', m)
    print(n, 'car', int((m == 255).sum()), 'ign', int((m == 128).sum()), 'blobs', k - 1)
