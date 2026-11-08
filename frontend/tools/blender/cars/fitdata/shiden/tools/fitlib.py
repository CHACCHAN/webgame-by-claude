"""fitlib: cameras, rasterised silhouettes, FFD lattice, outline correspondences (numpy + OpenCV, no Blender).
Game frame: x = car's left, y up, z forward. Camera [x, y, z, yaw, pitch, roll, f] as silrender.py."""
import json
import math

import cv2
import numpy as np

WB = 2.425
TRACK = 1.46
WHEEL_Y = 0.31
WHEELS = {'fl': (1, WB / 2), 'fr': (-1, WB / 2), 'rl': (1, -WB / 2), 'rr': (-1, -WB / 2)}


# ---------------------------------------------------------------- camera

def basis(yaw, pitch, roll):
    d = np.array([math.sin(yaw) * math.cos(pitch), math.sin(pitch), math.cos(yaw) * math.cos(pitch)])
    r = np.cross(d, [0, 1, 0]); r /= np.linalg.norm(r)
    u = np.cross(r, d)
    c, s = math.cos(roll), math.sin(roll)
    return d, c * r + s * u, -s * r + c * u


def project(cam, P, W, H):
    """cam: [x,y,z,yaw,pitch,roll,f]; P (N,3) → uv (N,2), depth (N,)"""
    C = np.asarray(cam[:3]); d, r, u = basis(*cam[3:6]); f = cam[6]
    Q = P - C
    z = Q @ d
    return np.stack([W / 2 + f * (Q @ r) / z, H / 2 - f * (Q @ u) / z], 1), z


def proj_jac(cam, P, W, H):
    """d(uv)/dP for each point: (N, 2, 3)"""
    C = np.asarray(cam[:3]); d, r, u = basis(*cam[3:6]); f = cam[6]
    Q = P - C
    zc = Q @ d; xc = Q @ r; yc = Q @ u
    J = np.empty((len(P), 2, 3))
    J[:, 0, :] = f * (r[None] / zc[:, None] - xc[:, None] * d[None] / zc[:, None] ** 2)
    J[:, 1, :] = -f * (u[None] / zc[:, None] - yc[:, None] * d[None] / zc[:, None] ** 2)
    return J


def look_at(eye, target, f, roll=0.0):
    d = np.asarray(target, float) - np.asarray(eye, float)
    d /= np.linalg.norm(d)
    return [*eye, math.atan2(d[0], d[2]), math.asin(d[1]), roll, f]


# ---------------------------------------------------------------- raster

def raster(uv, tris, W, H, mask=None):
    """union of triangles (uv: (N,2) float px; tris (M,3)) → uint8 mask"""
    if mask is None:
        mask = np.zeros((H, W), np.uint8)
    pts = np.round(uv[tris] * 4).astype(np.int32)       # 2 bits of sub-pixel
    lo = pts.min(axis=1); hi = pts.max(axis=1)
    keep = (hi[:, 0] >= 0) & (lo[:, 0] < W * 4) & (hi[:, 1] >= 0) & (lo[:, 1] < H * 4)
    for p in pts[keep]:
        cv2.fillConvexPoly(mask, p, 255, lineType=cv2.LINE_8, shift=2)
    return mask


def outline(m):
    m8 = (m > 0).astype(np.uint8)
    return (m8 - cv2.erode(m8, np.ones((3, 3), np.uint8))).astype(bool)


def largest(mask):
    n, lab, stats, _ = cv2.connectedComponentsWithStats(mask.astype(np.uint8), 8)
    if n <= 1:
        return mask.astype(bool)
    k = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    m = lab == k
    inv = (~m).astype(np.uint8)
    n2, lab2, stats2, _ = cv2.connectedComponentsWithStats(inv, 4)
    h, w = m.shape
    for j in range(1, n2):
        x, y, ww, hh = stats2[j, :4]
        if x > 0 and y > 0 and x + ww < w and y + hh < h:
            m[lab2 == j] = True
    return m


def sdf(P):
    """signed distance (px) to the boundary of boolean mask P: + outside, - inside; and its gradient"""
    P8 = P.astype(np.uint8)
    dout = cv2.distanceTransform(1 - P8, cv2.DIST_L2, 5)
    din = cv2.distanceTransform(P8, cv2.DIST_L2, 5)
    S = (dout - din + np.where(P, 0.5, -0.5)).astype(np.float32)
    Sb = cv2.GaussianBlur(S, (0, 0), 1.0)
    gx = cv2.Sobel(Sb, cv2.CV_32F, 1, 0, ksize=3) / 8.0
    gy = cv2.Sobel(Sb, cv2.CV_32F, 0, 1, ksize=3) / 8.0
    return S, gx, gy


def bilinear(img, uv):
    m = cv2.remap(img, uv[:, 0].astype(np.float32)[None], uv[:, 1].astype(np.float32)[None], cv2.INTER_LINEAR,
                  borderMode=cv2.BORDER_REPLICATE)
    return m[0]


# ---------------------------------------------------------------- mesh topology

def edges_of(tris):
    """unique edges (E,2), and for each the two adjacent faces (−1 if boundary; non-manifold: first two)"""
    e = np.concatenate([tris[:, [0, 1]], tris[:, [1, 2]], tris[:, [2, 0]]])
    f = np.tile(np.arange(len(tris)), 3)
    key = np.sort(e, axis=1)
    order = np.lexsort((key[:, 1], key[:, 0]))
    key = key[order]; f = f[order]
    new = np.r_[True, np.any(key[1:] != key[:-1], axis=1)]
    idx = np.cumsum(new) - 1
    E = key[new]
    F = -np.ones((len(E), 2), int)
    first = np.nonzero(new)[0]
    F[:, 0] = f[first]
    nxt = first + 1
    ok = (nxt < len(key)) & ~np.r_[new[1:], True][first]
    F[ok, 1] = f[nxt[ok]]
    return E, F


# ---------------------------------------------------------------- FFD lattice (cubic uniform B-spline, x-mirrored)

def bspline_w(t):
    """t in [0,1) → 4 cubic B-spline weights"""
    t2, t3 = t * t, t * t * t
    return np.stack([(1 - t) ** 3 / 6, (3 * t3 - 6 * t2 + 4) / 6, (-3 * t3 + 3 * t2 + 3 * t + 1) / 6, t3 / 6], -1)


class Lattice:
    def __init__(self, lo, hi, seg):
        self.lo = np.asarray(lo, float); self.hi = np.asarray(hi, float); self.seg = np.asarray(seg, int)
        self.n = self.seg + 3
        self.ncp = int(np.prod(self.n))
        self.D = np.zeros((self.ncp, 3))
        # symmetric free parameters: x index i ↔ n_x−1−i, Dx antisymmetric
        nx = self.n[0]
        cols = []
        S = []
        rows = self.ncp * 3
        pid = 0
        for i in range((nx + 1) // 2):
            for j in range(self.n[1]):
                for k in range(self.n[2]):
                    a = self.cp(i, j, k); b = self.cp(nx - 1 - i, j, k)
                    for c in range(3):
                        if a == b and c == 0:
                            continue
                        col = np.zeros(rows)
                        col[a * 3 + c] = 1.0
                        if a != b:
                            col[b * 3 + c] = -1.0 if c == 0 else 1.0
                        S.append(col)
        self.S = np.array(S).T            # (ncp*3, nfree)
        self.nfree = self.S.shape[1]

    def cp(self, i, j, k):
        return (i * self.n[1] + j) * self.n[2] + k

    def weights(self, P):
        """(N,64) control point indices and weights"""
        u = (P - self.lo) / (self.hi - self.lo) * self.seg
        u = np.clip(u, 0, self.seg - 1e-9)
        b = np.floor(u).astype(int)
        t = u - b
        wx, wy, wz = bspline_w(t[:, 0]), bspline_w(t[:, 1]), bspline_w(t[:, 2])
        I = b[:, 0, None] + np.arange(4)[None]
        J = b[:, 1, None] + np.arange(4)[None]
        K = b[:, 2, None] + np.arange(4)[None]
        idx = ((I[:, :, None, None] * self.n[1] + J[:, None, :, None]) * self.n[2] + K[:, None, None, :]).reshape(len(P), 64)
        w = (wx[:, :, None, None] * wy[:, None, :, None] * wz[:, None, None, :]).reshape(len(P), 64)
        # outside the box the deformation fades out (no extrapolation)
        inside = np.all((P >= self.lo) & (P <= self.hi), axis=1)
        w[~inside] = 0.0
        return idx, w

    def apply(self, P, idx=None, w=None):
        if idx is None:
            idx, w = self.weights(P)
        return P + np.einsum('nk,nkc->nc', w, self.D[idx])

    def set_free(self, p):
        self.D = (self.S @ p).reshape(self.ncp, 3)

    def get_free(self):
        return np.linalg.lstsq(self.S, self.D.reshape(-1), rcond=None)[0]

    def reg(self):
        """smoothness (neighbour differences) as a matrix on the full D vector"""
        rows = []
        n = self.n
        for i in range(n[0]):
            for j in range(n[1]):
                for k in range(n[2]):
                    a = self.cp(i, j, k)
                    for di, dj, dk in ((1, 0, 0), (0, 1, 0), (0, 0, 1)):
                        if i + di < n[0] and j + dj < n[1] and k + dk < n[2]:
                            rows.append((a, self.cp(i + di, j + dj, k + dk)))
        L = np.zeros((len(rows) * 3, self.ncp * 3))
        for r, (a, b) in enumerate(rows):
            for c in range(3):
                L[r * 3 + c, a * 3 + c] = 1; L[r * 3 + c, b * 3 + c] = -1
        return L

    def to_json(self):
        return {'lo': self.lo.tolist(), 'hi': self.hi.tolist(), 'seg': self.seg.tolist(),
                'D': np.round(self.D, 6).tolist()}

    @staticmethod
    def from_json(j):
        L = Lattice(j['lo'], j['hi'], j['seg'])
        L.D = np.array(j['D'], float)
        return L


def pose_apply(P, dy, pitch):
    """body pose relative to the wheels: pitch about the x axis through the origin (nose down = +), then lift"""
    c, s = math.cos(pitch), math.sin(pitch)
    y = P[:, 1] * c - P[:, 2] * s
    z = P[:, 1] * s + P[:, 2] * c
    return np.stack([P[:, 0], y + dy, z], 1)


# ---------------------------------------------------------------- rims

def rim_circle(side, zc, rr, ox, steer, n=144):
    t = np.linspace(0, 2 * np.pi, n, endpoint=False)
    c = np.array([side * (TRACK / 2 + ox), WHEEL_Y, zc])
    fwd = np.array([math.sin(steer), 0, math.cos(steer)])
    up = np.array([0, 1.0, 0])
    return c[None] + rr * (np.cos(t)[:, None] * fwd[None] + np.sin(t)[:, None] * up[None])


def poly_dist(Q, poly):
    """distance from points Q (M,2) to closed polyline poly (n,2)"""
    A = poly; B = np.roll(poly, -1, axis=0)
    AB = B - A
    L2 = (AB ** 2).sum(1) + 1e-12
    AQ = Q[:, None, :] - A[None]
    t = np.clip((AQ * AB[None]).sum(2) / L2[None], 0, 1)
    D = AQ - t[..., None] * AB[None]
    return np.sqrt((D ** 2).sum(2)).min(1)
