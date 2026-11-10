"""cleanmask.py <photo> <model sil.png> <trace.json> <out_mask.png> [band] : the photo's bike mask = GrabCut seeded from
the model silhouette (band px either side undecided) ∪ hand traces where GrabCut fails (trace.json: "ellipses": tyre
outline points → filled fitted ellipse; "polys": filled polygons, e.g. a clear windscreen; "bg_polys": background cut out again; "ignore_polys": parts that differ from the stock bike, left out of both masks); holes filled. Prints the
IoU of the model silhouette (holes filled) against it, and writes an overlay (green photo only, red model only).
With an existing <out_mask.png> and --reuse, only the IoU is recomputed (the photo mask stays fixed between rounds)."""
import sys, json
import cv2, numpy as np
ph = cv2.imread(sys.argv[1]); H, W = ph.shape[:2]
s = cv2.imread(sys.argv[2], cv2.IMREAD_UNCHANGED)
sil = cv2.resize(s[:, :, 3], (W, H), interpolation=cv2.INTER_NEAREST) > 127


def fill_holes(m):
    m = m.astype(np.uint8)
    cs, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    out = np.zeros_like(m)
    cv2.drawContours(out, cs, -1, 1, -1)
    return out.astype(bool)


T = json.load(open(sys.argv[3]))
if '--reuse' in sys.argv:
    M = cv2.imread(sys.argv[4], cv2.IMREAD_GRAYSCALE) > 127
else:
    b = int(sys.argv[5]) if len(sys.argv) > 5 and sys.argv[5].isdigit() else 30
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * b + 1, 2 * b + 1))
    inner = cv2.erode(sil.astype(np.uint8), k).astype(bool)
    outer = cv2.dilate(sil.astype(np.uint8), k).astype(bool)
    m = np.full((H, W), cv2.GC_PR_BGD, np.uint8)
    m[sil] = cv2.GC_PR_FGD
    m[inner] = cv2.GC_FGD
    m[~outer] = cv2.GC_BGD
    hand = np.zeros((H, W), np.uint8)
    shadow = np.zeros((H, W), np.uint8)
    for pts in T.get('ellipses', {}).values():
        e = cv2.fitEllipse(np.array(pts, np.float32))
        cv2.ellipse(hand, e, 1, -1)
        # the ground shadow round a tyre's lower half is not bike: a ring outside the traced tyre, below its centre
        ring = np.zeros((H, W), np.uint8)
        cv2.ellipse(ring, (e[0], (e[1][0] + 90, e[1][1] + 90), e[2]), 1, -1)
        ring[:int(e[0][1]) + int(0.25 * e[1][1] / 2)] = 0
        shadow |= ring
    for pts in T.get('polys', {}).values():
        cv2.fillPoly(hand, [np.array(pts, np.int32)], 1)
    m[(shadow > 0) & (hand == 0)] = cv2.GC_BGD
    m[hand > 0] = cv2.GC_FGD
    bg, fg = np.zeros((1, 65), np.float64), np.zeros((1, 65), np.float64)
    cv2.grabCut(ph, m, None, bg, fg, 6, cv2.GC_INIT_WITH_MASK)
    M = (m == cv2.GC_FGD) | (m == cv2.GC_PR_FGD)
    M = cv2.morphologyEx(M.astype(np.uint8), cv2.MORPH_OPEN, np.ones((5, 5), np.uint8)).astype(bool)
    n, lab, st, _ = cv2.connectedComponentsWithStats(M.astype(np.uint8))
    if n > 1:
        M = lab == 1 + np.argmax(st[1:, cv2.CC_STAT_AREA])
    M = fill_holes(M)
    cv2.imwrite(sys.argv[4], (M * 255).astype(np.uint8))
# background seen through gaps that GrabCut took for the bike (trace.json "bg_polys"): always cut out
for poly in T.get('bg_polys', []):
    bg = np.zeros((H, W), np.uint8)
    cv2.fillPoly(bg, [np.array(poly, np.int32)], 1)
    M = M & ~bg.astype(bool)
S = fill_holes(sil)
for poly in T.get('ignore_polys', []):
    ig = np.zeros((H, W), np.uint8)
    cv2.fillPoly(ig, [np.array(poly, np.int32)], 1)
    M = M & ~ig.astype(bool); S = S & ~ig.astype(bool)
iou = (M & S).sum() / (M | S).sum()
print(f'IoU {iou:.4f}  model-only {(S & ~M).sum() / M.sum() * 100:.1f}%  photo-only {(M & ~S).sum() / M.sum() * 100:.1f}%')
ov = ph.copy() // 2
ov[M & ~S] = (0, 200, 0); ov[S & ~M] = (0, 0, 220)
cv2.imwrite(sys.argv[4].replace('.png', '_ov.jpg'), cv2.resize(ov, (W // 2, H // 2)))
