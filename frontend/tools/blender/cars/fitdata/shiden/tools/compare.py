"""compare.py <run> <names> : <run>/cmp/<n>.png = photo | Cycles render (same camera), 640 px each"""
import sys, os, cv2, numpy as np
run, names = sys.argv[1], sys.argv[2].split(',')
os.makedirs(f'{run}/cmp', exist_ok=True)
for n in names:
    p = cv2.imread(f'photos/{n}.jpg'); r = cv2.imread(f'{run}/cy/{n}_cy.png')
    h = int(p.shape[0] * 640 / p.shape[1])
    p = cv2.resize(p, (640, h), interpolation=cv2.INTER_AREA); r = cv2.resize(r, (640, h), interpolation=cv2.INTER_AREA)
    im = np.hstack([p, np.full((h, 4, 3), 255, np.uint8), r])
    cv2.putText(im, n, (8, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
    cv2.imwrite(f'{run}/cmp/{n}.png', im)
