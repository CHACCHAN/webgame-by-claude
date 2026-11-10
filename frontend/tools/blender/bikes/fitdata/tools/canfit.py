"""canfit.py: tune the H2 stock can (chamfered_can parameters) against its outline traced on r07 (solved camera):
projects the can's rings, takes the convex hull, scores the traced points' distances to it; writes an overlay"""
import json, sys, math
import numpy as np, cv2
sys.path.insert(0, '/home/dev/.local/opt/carfit/bikes/tools')
import bsolve
B = '/home/dev/.local/opt/carfit/bikes/ninjah2/'
cam = json.load(open(B + 'fit/cams.json'))['cams']['r07']
# traced on r07 (orig px): the can's free outline (its rear end and bottom edge; the top front hides under the shield)
T = np.array([(225, 442), (190, 478), (170, 515), (150, 550), (155, 590), (175, 640), (280, 690), (370, 730), (490, 790)], float)


def unit(v):
    return v / np.linalg.norm(v)


def rings(a, b, hw, hh, slant, chamfer=0.45, n=8):
    a, b = np.array(a, float), np.array(b, float)
    d = unit(b - a); up = unit(np.array([0, 1.0, 0]) - d * d[1]); side = np.cross(d, up)
    fw = lambda s: np.interp(s, np.linspace(0, 1, len(hw)), hw)
    fh = lambda s: np.interp(s, np.linspace(0, 1, len(hh)), hh)
    out = []
    for i in range(n):
        s = i / (n - 1); w, h = fw(s), fh(s); c = a + (b - a) * s
        for u, v in [(w, chamfer * h), (chamfer * w, h), (-chamfer * w, h), (-w, chamfer * h), (-w, -chamfer * h),
                     (-chamfer * w, -h), (chamfer * w, -h), (w, -chamfer * h)]:
            q = c + side * u + up * v
            if i == n - 1:
                q = q + d * slant * (v / h)
            out.append(q)
    return np.array(out)


def outline(pr):
    uv = bsolve.project(cam[:7], pr, *cam[7])
    return cv2.convexHull(uv.astype(np.float32)).reshape(-1, 2)


HW = [0.055, 0.068, 0.074, 0.072, 0.066, 0.06]
HH = [0.07, 0.092, 0.104, 0.102, 0.094, 0.084]
A0 = (-0.17, 0.34, -0.235)


def score(p, verbose=False):
    bx, by, bz, slant, kh = p
    bx = min(-0.19, max(-0.215, bx))
    pr = rings(A0, (bx, by, bz), HW, [h * (1 + (kh - 1) * i / 5) for i, h in enumerate(HH)], slant)
    hull = outline(pr)
    d = bsolve.pdist(T, hull)
    if verbose:
        print(' '.join(f'{v:.0f}' for v in d))
    return float((d ** 2).mean())


x0 = [-0.20, 0.585, -0.71, 0.05, 1.0]
print('start', round(math.sqrt(score(x0, True)), 1))


class R:
    pass


def nelder(f, x0, steps, it=1500):
    n = len(x0); S = [np.array(x0, float)] + [np.array(x0, float) + np.eye(n)[i] * steps[i] for i in range(n)]
    F = [f(s) for s in S]
    for _ in range(it):
        o = np.argsort(F); S = [S[i] for i in o]; F = [F[i] for i in o]
        c = np.mean(S[:-1], axis=0); xr = c + (c - S[-1]); fr = f(xr)
        if fr < F[0]:
            xe = c + 2 * (c - S[-1]); fe = f(xe)
            S[-1], F[-1] = (xe, fe) if fe < fr else (xr, fr)
        elif fr < F[-2]:
            S[-1], F[-1] = xr, fr
        else:
            xc = c + 0.5 * (S[-1] - c); fc = f(xc)
            if fc < F[-1]:
                S[-1], F[-1] = xc, fc
            else:
                S = [S[0] + 0.5 * (s - S[0]) for s in S]; F = [f(s) for s in S]
    r = R(); r.x = S[int(np.argmin(F))]; return r


r = nelder(score, x0, [0.02, 0.03, 0.05, 0.03, 0.1])
print('fit', [round(float(v), 3) for v in r.x], 'rms px', round(math.sqrt(score(r.x, True)), 1))
img = cv2.imread(B + 'ref/r07.jpg')
for p, col in ((x0, (0, 0, 255)), (r.x, (0, 255, 0))):
    bx, by, bz, slant, kh = p
    bx = min(-0.19, max(-0.215, bx))
    hull = outline(rings(A0, (bx, by, bz), HW, [h * (1 + (kh - 1) * i / 5) for i, h in enumerate(HH)], slant))
    cv2.polylines(img, [hull.astype(np.int32)], True, col, 2)
for t in T:
    cv2.circle(img, tuple(int(v) for v in t), 5, (255, 0, 255), -1)
cv2.imwrite(sys.argv[1] if len(sys.argv) > 1 else '/tmp/canfit.jpg', img[350:900, 40:760])
