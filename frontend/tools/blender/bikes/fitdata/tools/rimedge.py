"""rimedge.py <photo> <rough.json> <out.json> <overlay.png> [r0,r1 fraction] : rim lip ellipse from the bright-rim →
dark-tyre edge: along rays from the rough ellipse's centre, the strongest outward drop in brightness between r0 and
r1 times the rough radius; ellipse fitted with iterative trimming. rough.json {wheel: [[u,v] ≥5 on the lip]}
(optionally {"pts": [...], "skip": [[a0,a1] deg ranges to ignore (image angles, 0 = right, 90 = down)]})"""
import json, sys, math
import cv2, numpy as np
img = cv2.imread(sys.argv[1]); g = cv2.GaussianBlur(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32), (3, 3), 0)
H, W = g.shape
R = json.load(open(sys.argv[2]))
r0, r1 = [float(v) for v in sys.argv[5].split(',')] if len(sys.argv) > 5 else (0.85, 1.15)
dark_in = len(sys.argv) > 6 and sys.argv[6] == 'tyre'      # tyre mode: dark inside, brighter outside
out = {}; ov = img.copy()
for w, v in R.items():
    pts = v['pts'] if isinstance(v, dict) else v
    skip = v.get('skip', []) if isinstance(v, dict) else []
    (cx, cy), (A, B), ang = cv2.fitEllipse(np.array(pts, np.float32))
    a, b, t = A / 2, B / 2, math.radians(ang)
    F = []
    for th in np.linspace(0, 2 * math.pi, 360, endpoint=False):
        ex = a * math.cos(th) * math.cos(t) - b * math.sin(th) * math.sin(t)
        ey = a * math.cos(th) * math.sin(t) + b * math.sin(th) * math.cos(t)
        deg = math.degrees(math.atan2(ey, ex)) % 360
        if any(s0 <= deg <= s1 for s0, s1 in skip): continue
        ss = np.linspace(r0, r1, 80)
        xs, ys = cx + ex * ss, cy + ey * ss
        ok = (xs >= 1) & (xs < W - 1) & (ys >= 1) & (ys < H - 1)
        if not ok.all(): continue
        vals = cv2.remap(g, xs.astype(np.float32).reshape(1, -1), ys.astype(np.float32).reshape(1, -1), cv2.INTER_LINEAR)[0]
        dv = np.diff(vals)
        if dark_in:
            k = int(np.argmax(dv))
            if dv[k] < 10: continue
            if vals[max(0, k - 4):k + 1].mean() > 45 or vals[k + 1:k + 6].mean() < vals[max(0, k - 4):k + 1].mean() + 20: continue
        else:
            k = int(np.argmin(dv))
            if dv[k] > -12: continue
            # bright inside, dark outside
            if vals[max(0, k - 4):k + 1].mean() < 90 or vals[k + 1:k + 6].mean() > 80: continue
        s = (ss[k] + ss[k + 1]) / 2
        F.append((cx + ex * s, cy + ey * s))
    F = np.array(F, np.float32)
    for it in range(4):
        (ecx, ecy), (EA, EB), eang = cv2.fitEllipse(F)
        ea, eb, et = EA / 2, EB / 2, math.radians(eang)
        q = F - [ecx, ecy]; xr = q[:, 0] * math.cos(et) + q[:, 1] * math.sin(et); yr = -q[:, 0] * math.sin(et) + q[:, 1] * math.cos(et)
        e = np.abs(np.sqrt((xr / ea) ** 2 + (yr / eb) ** 2) - 1) * (ea + eb) / 2
        F = F[e < max(1.2, np.percentile(e, 80))]
    out[w] = {'ellipse': [ecx, ecy, ea, eb, eang], 'found': F.round(1).tolist()}
    print(w, 'centre (%.1f, %.1f) axes %.1f %.1f ang %.1f n %d resid p80 %.2f' % (ecx, ecy, ea, eb, eang, len(F), np.percentile(e, 80)))
    cv2.ellipse(ov, ((ecx, ecy), (EA, EB), eang), (255, 0, 255), 1)
    for x, y in F: cv2.circle(ov, (int(x), int(y)), 2, (0, 255, 0), -1)
json.dump(out, open(sys.argv[3], 'w'))
cv2.imwrite(sys.argv[4], ov)
