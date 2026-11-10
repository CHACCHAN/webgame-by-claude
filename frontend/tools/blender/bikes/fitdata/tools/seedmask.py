"""seedmask.py <photo> <sil.png> <out_mask.png> [band px] : a photo mask by GrabCut seeded from a model silhouette:
eroded silhouette = sure bike, outside the dilated silhouette = sure background, the band between is decided by the
photo. Then IoU of the model silhouette against it (whole bike, and the band only)."""
import sys
import cv2, numpy as np
ph = cv2.imread(sys.argv[1]); H, W = ph.shape[:2]
s = cv2.imread(sys.argv[2], cv2.IMREAD_UNCHANGED)
sil = cv2.resize(s[:, :, 3], (W, H), interpolation=cv2.INTER_NEAREST) > 127
b = int(sys.argv[4]) if len(sys.argv) > 4 else 30
k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * b + 1, 2 * b + 1))
inner = cv2.erode(sil.astype(np.uint8), k).astype(bool)
outer = cv2.dilate(sil.astype(np.uint8), k).astype(bool)
m = np.full((H, W), cv2.GC_PR_BGD, np.uint8)
m[sil] = cv2.GC_PR_FGD
m[inner] = cv2.GC_FGD
m[~outer] = cv2.GC_BGD
bg, fg = np.zeros((1, 65), np.float64), np.zeros((1, 65), np.float64)
cv2.grabCut(ph, m, None, bg, fg, 6, cv2.GC_INIT_WITH_MASK)
M = (m == cv2.GC_FGD) | (m == cv2.GC_PR_FGD)
M = cv2.morphologyEx(M.astype(np.uint8), cv2.MORPH_OPEN, np.ones((5, 5), np.uint8)).astype(bool)
cv2.imwrite(sys.argv[3], (M * 255).astype(np.uint8))
band = outer & ~inner
iou = (M & sil).sum() / (M | sil).sum()
ib = (M & sil & band).sum() / ((M | sil) & band).sum()
print(f'IoU {iou:.4f} band-IoU {ib:.4f}')
ov = ph.copy() // 2
ov[M & ~sil] = (0, 200, 0); ov[sil & ~M] = (0, 0, 220)
cv2.imwrite(sys.argv[3].replace('.png', '_ov.jpg'), cv2.resize(ov, (W // 2, H // 2)))
