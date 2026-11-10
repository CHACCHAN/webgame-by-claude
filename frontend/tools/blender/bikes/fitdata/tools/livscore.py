"""livscore.py <photo> <loopdir> [x0] : two-tone livery agreement on a photo: the photo's blue / silver (by colour)
against the model's 'paint' / 'accent' material ids, over the pixels where both are one of the two (x >= x0)"""
import sys, json, cv2, numpy as np
from PIL import Image
ph = cv2.imread(sys.argv[1]); H, W = ph.shape[:2]; ld = sys.argv[2]; x0 = int(sys.argv[3]) if len(sys.argv) > 3 else 0
pal = json.load(open(ld + '/palette.json'))
ids = np.array(Image.open(ld + '/r01_ids.png').convert('RGB').resize((W, H), Image.NEAREST)).astype(int)
mb = np.abs(ids - np.array(pal['paint'])).sum(2) < 6
ms = np.abs(ids - np.array(pal['accent'])).sum(2) < 6
hsv = cv2.cvtColor(ph, cv2.COLOR_BGR2HSV).astype(int)
Hh, S, V = hsv[..., 0], hsv[..., 1], hsv[..., 2]
pb = (Hh >= 104) & (Hh <= 132) & (S > 90) & (V > 30) & (V < 215)
ps = (S < 70) & (V > 110)
roi = np.zeros((H, W), bool); roi[:, x0:] = True
e = cv2.erode(((mb | ms) & roi).astype(np.uint8), np.ones((7, 7), np.uint8)) > 0     # away from part edges
both = e & (pb | ps)
agree = (mb & pb) | (ms & ps)
acc = (agree & both).sum() / max(1, both.sum())
iou_b = (mb & pb & e).sum() / max(1, ((mb | pb) & e & (pb | ps)).sum())
iou_s = (ms & ps & e).sum() / max(1, ((ms | ps) & e & (pb | ps)).sum())
print(f'livery agreement {acc:.3f}  blue IoU {iou_b:.3f}  silver IoU {iou_s:.3f}  (n {both.sum()})')
ov = ph.copy() // 2
ov[both & mb & ps] = (0, 0, 255); ov[both & ms & pb] = (255, 0, 0); ov[both & agree] = (0, 160, 0)
cv2.imwrite(ld + '/livery_ov.jpg', cv2.resize(ov, (W // 2, H // 2)))
