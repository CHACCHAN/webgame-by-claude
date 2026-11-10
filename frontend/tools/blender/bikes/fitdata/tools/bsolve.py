"""bsolve.py <annot.json> <cams.json> [names] : camera solve for a motorcycle photo from its two rim lips.
Bike frame (game): metres, x = bike's left, y up, z forward, origin on the ground midway between the axles.
annot.json: {"_bike": {"wb", "rf", "rr", "rake_deg", "trail", "lip_f", "lip_r", "rho"},
  name: {"size": [W, H], "rims": "<rimcol json>", "init": [x, y, z, yaw_deg, pitch_deg, roll_deg, f],
         "side": "r"|"l" (which side faces the camera), "pts": {name: [[x,y,z], [u,v], weight]}, "prior": {...}}}
Unknowns: camera (7), steer (rad, + = front wheel turned to the bike's left), lip radius, lip offsets.
The steer rotates the front wheel about the steering axis (through the ground point trail ahead of the front contact,
tilted back by the rake). Writes cams.json {"cams": {n: [x,y,z,yaw,pitch,roll,f,[W,H]]}, "steer": {n: rad}, "rms": {n: px}}"""
import json, math, os, sys
import numpy as np


def basis(yaw, pitch, roll):
    d = np.array([math.sin(yaw) * math.cos(pitch), math.sin(pitch), math.cos(yaw) * math.cos(pitch)])
    r = np.cross(d, [0, 1, 0]); r /= np.linalg.norm(r)
    u = np.cross(r, d)
    c, s = math.cos(roll), math.sin(roll)
    return d, c * r + s * u, -s * r + c * u


def project(cam, P, W, H):
    C = np.array(cam[:3]); d, r, u = basis(*cam[3:6]); f = cam[6]
    Q = P - C; z = Q @ d
    return np.stack([W / 2 + f * (Q @ r) / z, H / 2 - f * (Q @ u) / z], 1)


def rot_axis(v, a, ang):
    """rotate vectors v (n,3) about unit axis a by ang (Rodrigues)"""
    c, s = math.cos(ang), math.sin(ang)
    return v * c + np.cross(a, v) * s + np.outer(v @ a, a) * (1 - c)


def steer_frame(bk, steer):
    """front axle position and wheel normal for a steer angle"""
    r = math.radians(bk['rake_deg'])
    a = np.array([0, math.cos(r), -math.sin(r)])
    A0 = np.array([0, 0, bk['wb'] / 2 + bk['trail']])
    P = np.array([[0, bk['rf'], bk['wb'] / 2]]) - A0
    P = rot_axis(P, a, steer)[0] + A0
    n = rot_axis(np.array([[1.0, 0, 0]]), a, steer)[0]
    return P, n


TH = np.linspace(0, 2 * math.pi, 120, endpoint=False)


def pdist(F, C):
    """distance of points F (n,2) to the closed polyline C (m,2): to its segments, not its vertices"""
    A = C; B = np.roll(C, -1, 0); D = B - A
    L = (D ** 2).sum(1) + 1e-12
    t = np.clip(((F[:, None, :] - A[None]) * D[None]).sum(2) / L[None], 0, 1)
    Q = A[None] + t[..., None] * D[None]
    return np.sqrt(((F[:, None, :] - Q) ** 2).sum(2)).min(1)


def circle(centre, normal, radius):
    n = normal / np.linalg.norm(normal)
    e1 = np.cross(n, [0, 0, 1.0]); e1 /= np.linalg.norm(e1)
    e2 = np.cross(n, e1)
    return centre + radius * (np.outer(np.cos(TH), e1) + np.outer(np.sin(TH), e2))


def solve(a, bk, base, verbose=True):
    W, H = a['size']
    rims = json.load(open(os.path.join(base, a['rims'])))
    side = 1 if a.get('side', 'r') == 'l' else -1
    pri = a.get('prior', {})
    i0 = a['init']
    x = np.array([*i0[:3], *[math.radians(v) for v in i0[3:6]], math.log(i0[6]), math.radians(a.get('steer0', 0)), bk['rho'],
                  bk['lip_f'], bk['lip_r'], bk['trail']], float)
    pts = a.get('pts', {})
    P3 = np.array([v[0] for v in pts.values()], float).reshape(-1, 3)
    P2 = np.array([v[1] for v in pts.values()], float).reshape(-1, 2)
    PW = np.array([v[2] if len(v) > 2 else 1.0 for v in pts.values()], float)

    def wheel3d(x, w, sgn=1):
        if w == 'f':
            Pc, n = steer_frame(dict(bk, trail=x[11]), x[7]); lip = x[9]
        else:
            Pc, n = np.array([0, bk['rr'], -bk['wb'] / 2]), np.array([1.0, 0, 0]); lip = x[10]
        return circle(Pc + n * side * lip * sgn, n, abs(x[8]))

    tyres = json.load(open(os.path.join(base, a['tyres']))) if a.get('tyres') else {}

    def tyre3d(x, w, sgn):
        """a tyre's outer silhouette ≈ the crown's edge circles at ±0.3 of the tyre width (radius R - 4 mm)"""
        if w == 'f':
            Pc, n = steer_frame(dict(bk, trail=x[11]), x[7]); R, tw = bk['rf'], bk.get('wf', 0.11)
        else:
            Pc, n = np.array([0, bk['rr'], -bk['wb'] / 2]), np.array([1.0, 0, 0]); R, tw = bk['rr'], bk.get('wr', 0.15)
        return circle(Pc + n * 0.3 * tw * sgn, n, R - 0.004)

    def res(x, detail=False):
        cam = list(x[:6]) + [math.exp(x[6])]
        r = []; dd = {}
        for w in ('f', 'r'):
            if w not in tyres: continue
            F = np.array(tyres[w]['found'], float)
            if len(F) > 40: F = F[np.linspace(0, len(F) - 1, 40).astype(int)]
            c1 = project(cam, tyre3d(x, w, 1), W, H); c2 = project(cam, tyre3d(x, w, -1), W, H)
            d = np.minimum(pdist(F, c1), pdist(F, c2))
            dd['tyre_' + w] = d
            r.append(d * math.sqrt(a.get('tyre_weight', 30.0) / len(F)))
        for w in ('f', 'r'):
            if w not in rims: continue
            F = np.array(rims[w]['found'], float)
            if len(F) > 48: F = F[np.linspace(0, len(F) - 1, 48).astype(int)]
            if a.get('two_lips', True):
                # the outermost rim colour is on the union of both lips (near one side, far one the other)
                c1 = project(cam, wheel3d(x, w, 1), W, H); c2 = project(cam, wheel3d(x, w, -1), W, H)
                d = np.minimum(pdist(F, c1), pdist(F, c2))
            else:
                cuv = project(cam, wheel3d(x, w), W, H)
                d = pdist(F, cuv)
            dd[w] = d
            r.append(d * math.sqrt(60.0 / len(F)))
        if len(P3):
            uv = project(cam, P3, W, H); e = (uv - P2) * PW[:, None]; r.append(e.ravel()); dd['pts'] = np.hypot(*(uv - P2).T)
        for k, i in (('x', 0), ('y', 1), ('z', 2)):
            if k in pri: r.append(np.array([(x[i] - pri[k][0]) / pri[k][1]]))
        for k, i in (('yaw', 3), ('pitch', 4), ('roll', 5), ('steer', 7)):
            if k in pri: r.append(np.array([(x[i] - math.radians(pri[k][0])) / math.radians(pri[k][1])]))
        if 'f' in pri: r.append(np.array([(math.exp(x[6]) - pri['f'][0]) / pri['f'][1]]))
        sr, sl = a.get('rho_sigma', 0.008), a.get('lip_sigma', 0.02)
        r.append(np.array([(abs(x[8]) - bk['rho']) / sr, (x[9] - bk['lip_f']) / sl, (x[10] - bk['lip_r']) / sl,
                           (x[11] - bk['trail']) / a.get('trail_sigma', 0.001)]))
        rr = np.concatenate(r)
        return (rr, dd) if detail else rr

    lam = 1e-3; r = res(x); cost = r @ r
    for it in range(150):
        J = np.zeros((len(r), len(x)))
        for j in range(len(x)):
            h = 1e-6 * max(1, abs(x[j])); xp = x.copy(); xp[j] += h; xm = x.copy(); xm[j] -= h
            J[:, j] = (res(xp) - res(xm)) / (2 * h)
        g = J.T @ r; A = J.T @ J
        ok = False
        for _ in range(20):
            dx = -np.linalg.solve(A + lam * np.diag(np.diag(A) + 1e-9), g)
            rn = res(x + dx); cn = rn @ rn
            if cn < cost:
                x, r, cost, lam, ok = x + dx, rn, cn, lam * 0.3, True; break
            lam *= 10
        if not ok or np.abs(dx).max() < 1e-10: break
    rr, dd = res(x, True)
    allerr = np.concatenate(list(dd.values()))
    rms = float(np.sqrt((allerr ** 2).mean()))
    cam = [float(v) for v in x[:6]] + [float(math.exp(x[6]))]
    if verbose:
        for w, d in dd.items():
            print(f'   {w}: mean {d.mean():.2f} max {d.max():.2f} px (n {len(d)})')
        print(f'   trail {x[11]:.3f}  steer {math.degrees(x[7]):+.1f} deg  lip radius {x[8]:.3f}  lip offsets f {x[9]:.3f} r {x[10]:.3f}  cost {cost:.1f}')
    Pf, nf = steer_frame(dict(bk, trail=x[11]), x[7])
    solve.axle = [round(float(v), 4) for v in Pf]
    return cam + [[W, H]], rms, float(x[7]), cost, float(x[11])


if __name__ == '__main__':
    a = sys.argv[1:]
    A = json.load(open(a[0])); out = a[1]; base = os.path.dirname(os.path.abspath(a[0]))
    bk = A['_bike']
    names = a[2].split(',') if len(a) > 2 else [k for k in A if not k.startswith('_')]
    C = json.load(open(out)) if os.path.exists(out) else {'cams': {}, 'rms': {}, 'steer': {}}
    for n in names:
        print(n)
        best = None
        inits = A[n]['inits'] if 'inits' in A[n] else [A[n]['init']]
        for i0 in inits:
            A[n]['init'] = i0
            cam, rms, st, cost, tr = solve(A[n], bk, base, verbose=False)
            if best is None or cost < best[3]: best = (cam, rms, st, cost, i0)
        A[n]['init'] = best[4]
        cam, rms, st, cost, tr = solve(A[n], bk, base)
        print(f' {n}: rms {rms:.2f} px  cam ({cam[0]:.2f},{cam[1]:.2f},{cam[2]:.2f}) yaw {math.degrees(cam[3]):.1f} pitch {math.degrees(cam[4]):.1f} roll {math.degrees(cam[5]):.2f} f {cam[6]:.0f}  dist {math.hypot(*cam[:3]):.2f}')
        C['cams'][n] = cam; C['rms'][n] = round(rms, 2); C['steer'][n] = st; C.setdefault('trail', {})[n] = tr; C.setdefault('axle_f', {})[n] = solve.axle
    json.dump(C, open(out, 'w'), indent=1)
