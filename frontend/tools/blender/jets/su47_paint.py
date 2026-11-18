"""
The Su-47's textures (tools/blender/jets/su47.py), painted with numpy: one atlas of base colour, occlusion /
roughness / metalness and a normal map. Every sheet of the atlas (su47_skin.Sheet) is painted in its own metres
(`Canvas`: u, v as the skin gave them), so a panel line is where the structure under it would be: frames across a
body, longerons along it, spars and ribs in a wing, the doors and hatches where they are on the aircraft.

The finish is the prototype's: black all over, the leading edges, the fins' caps and the booms' tips white
(dielectric), the engines' rear fairings and the nozzles bare heat-stained metal. Markings are our own and neutral:
the numerals 01 and a chevron of two wings. A black aircraft is read from its seams, the change of gloss from panel
to panel and the lighter wear along edges: that is what is painted here, more than colour.
"""
import math

import numpy as np

import su47_shape as SH

BLACK = '#24262b'
BLACK_ROUGH = 0.40
RADOME = '#2c2e32'
WHITE = '#d9dad4'
METAL = '#5a554f'
PIT = '#4f6f7a'


def lin(h):
    h = h.lstrip('#')
    out = []
    for i in (0, 2, 4):
        c = int(h[i:i + 2], 16) / 255
        out.append(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
    return np.array(out, np.float32)


def to_srgb(a):
    a = np.clip(a, 0, 1)
    return np.where(a <= 0.0031308, a * 12.92, 1.055 * np.power(a, 1 / 2.4) - 0.055).astype(np.float32)


def value_noise(h, w, cu, cv, rng):
    """smooth noise (h, w) in 0..1 with cu × cv cells"""
    g = rng.random((cv + 2, cu + 2), dtype=np.float32)
    u = (np.arange(w) + 0.5) / w * cu
    v = (np.arange(h) + 0.5) / h * cv
    iu, fu = np.floor(u).astype(int), (u % 1.0).astype(np.float32)
    iv, fv = np.floor(v).astype(int), (v % 1.0).astype(np.float32)
    fu, fv = fu * fu * (3 - 2 * fu), fv * fv * (3 - 2 * fv)
    a, b = g[iv][:, iu], g[iv][:, iu + 1]
    c, d = g[iv + 1][:, iu], g[iv + 1][:, iu + 1]
    return (a * (1 - fu) + b * fu) * (1 - fv)[:, None] + (c * (1 - fu) + d * fu) * fv[:, None]


def box_blur(a, r):
    if r <= 0:
        return a
    k = 2 * r + 1
    for _ in range(2):
        p = np.pad(a, ((0, 0), (r, r)), mode='edge')
        c = np.cumsum(np.pad(p, ((0, 0), (1, 0))), 1)
        a = (c[:, k:] - c[:, :-k]) / k
        p = np.pad(a, ((r, r), (0, 0)), mode='edge')
        c = np.cumsum(np.pad(p, ((1, 0), (0, 0))), 0)
        a = (c[k:] - c[:-k]) / k
    return a.astype(np.float32)


class Canvas:
    """a sheet under the brush: linear colour, roughness, metalness, the seams' and the fasteners' masks"""

    def __init__(self, sheet, seed):
        _, _, self.w, self.h = sheet.px
        self.s = sheet.scale
        self.size = sheet.size
        self.name = sheet.name
        self.rng = np.random.default_rng(seed)
        self.base = np.empty((self.h, self.w, 3), np.float32)
        self.rough = np.empty((self.h, self.w), np.float32)
        self.metal = np.zeros((self.h, self.w), np.float32)
        self.seam = np.zeros((self.h, self.w), np.float32)
        self.dot = np.zeros((self.h, self.w), np.float32)
        self.height = np.zeros((self.h, self.w), np.float32)
        u = (np.arange(self.w, dtype=np.float32) + 0.5) / self.s
        v = (np.arange(self.h, dtype=np.float32) + 0.5) / self.s
        self.U, self.V = np.meshgrid(u, v)
        self.fill(BLACK, BLACK_ROUGH)

    # ---- areas
    def fill(self, colour, rough=None, metal=None, mask=None):
        c = lin(colour) if isinstance(colour, str) else np.array(colour, np.float32)
        if mask is None:
            self.base[:] = c
            if rough is not None:
                self.rough[:] = rough
            if metal is not None:
                self.metal[:] = metal
            return
        m = np.clip(mask, 0, 1).astype(np.float32)
        self.base += (c - self.base) * m[..., None]
        if rough is not None:
            self.rough += (rough - self.rough) * m
        if metal is not None:
            self.metal += (metal - self.metal) * m

    def band(self, lo, hi, axis='v', soft=None):
        """mask of lo ≤ coordinate ≤ hi (metres), edges one pixel soft (or `soft` metres)"""
        A = self.V if axis == 'v' else self.U
        k = self.s if soft is None else 1.0 / soft
        return np.clip((A - lo) * k + 0.5, 0, 1) * np.clip((hi - A) * k + 0.5, 0, 1)

    def box(self, u0, v0, u1, v1, soft=None):
        return self.band(u0, u1, 'u', soft) * self.band(v0, v1, 'v', soft)

    def tone(self, mask, colour=1.0, rough=0.0):
        """lighten / darken (× colour) and shift the gloss inside a mask"""
        self.base *= (1 + (colour - 1) * mask)[..., None]
        self.rough += rough * mask

    # ---- lines
    def _stamp(self, target, p0, p1, width):
        (u0, v0), (u1, v1) = p0, p1
        r = width / 2 + 1.0 / self.s
        x0 = max(0, int(math.floor((min(u0, u1) - r) * self.s)))
        x1 = min(self.w, int(math.ceil((max(u0, u1) + r) * self.s)) + 1)
        y0 = max(0, int(math.floor((min(v0, v1) - r) * self.s)))
        y1 = min(self.h, int(math.ceil((max(v0, v1) + r) * self.s)) + 1)
        if x1 <= x0 or y1 <= y0:
            return
        U, V = self.U[y0:y1, x0:x1], self.V[y0:y1, x0:x1]
        du, dv = u1 - u0, v1 - v0
        L = du * du + dv * dv
        t = np.zeros_like(U) if L < 1e-12 else np.clip(((U - u0) * du + (V - v0) * dv) / L, 0, 1)
        dist = np.hypot(U - u0 - t * du, V - v0 - t * dv)
        cov = np.clip((width / 2 - dist) * self.s + 0.5, 0, 1)
        np.maximum(target[y0:y1, x0:x1], cov, out=target[y0:y1, x0:x1])

    def line(self, p0, p1, width=0.012):
        self._stamp(self.seam, p0, p1, width)

    def path(self, pts, width=0.012, closed=False):
        n = len(pts)
        for i in range(n if closed else n - 1):
            self.line(pts[i], pts[(i + 1) % n], width)

    def rect(self, u0, v0, u1, v1, width=0.012, r=0.0):
        if r <= 0:
            self.path([(u0, v0), (u1, v0), (u1, v1), (u0, v1)], width, closed=True)
            return
        pts = []
        for (cu, cv, a0) in ((u1 - r, v1 - r, 0), (u0 + r, v1 - r, 90), (u0 + r, v0 + r, 180), (u1 - r, v0 + r, 270)):
            for k in range(5):
                a = math.radians(a0 + 90 * k / 4)
                pts.append((cu + r * math.cos(a), cv + r * math.sin(a)))
        self.path(pts, width, closed=True)

    def dots(self, p0, p1, pitch=0.06, radius=0.006):
        (u0, v0), (u1, v1) = p0, p1
        L = math.hypot(u1 - u0, v1 - v0)
        n = max(1, int(L / pitch))
        for k in range(n + 1):
            t = k / n
            p = (u0 + (u1 - u0) * t, v0 + (v1 - v0) * t)
            self._stamp(self.dot, p, p, radius * 2)

    def hatch(self, u0, v0, u1, v1, fasteners=0.07, width=0.012, r=0.02, inset=0.035):
        """an access panel: its outline and the fasteners inside it"""
        self.rect(u0, v0, u1, v1, width, r)
        if fasteners:
            a, b, c, d = u0 + inset, v0 + inset, u1 - inset, v1 - inset
            for p0, p1 in (((a, b), (c, b)), ((c, b), (c, d)), ((c, d), (a, d)), ((a, d), (a, b))):
                self.dots(p0, p1, fasteners)

    def louvres(self, u0, v0, u1, v1, n, along='u'):
        """a vent: n dark slats in a frame"""
        self.rect(u0, v0, u1, v1, 0.01)
        for k in range(n):
            t = (k + 0.5) / n
            if along == 'u':
                u = u0 + (u1 - u0) * t
                self.fill('#050506', 0.9, 0.0, self.box(u - 0.012, v0 + 0.02, u + 0.012, v1 - 0.02))
            else:
                v = v0 + (v1 - v0) * t
                self.fill('#050506', 0.9, 0.0, self.box(u0 + 0.02, v - 0.012, u1 - 0.02, v + 0.012))

    def cells(self, us, vs, amount=0.07, gloss=0.05):
        """one tone and gloss per panel of a grid of breaks: neighbouring panels are never quite alike"""
        for i in range(len(us) - 1):
            for j in range(len(vs) - 1):
                k = self.rng.uniform(-1, 1)
                g = self.rng.uniform(-1, 1)
                self.tone(self.box(us[i], vs[j], us[i + 1], vs[j + 1]), 1 + amount * k, gloss * g)

    def grid(self, us, vs, width=0.012, rivets=0.0, u_range=None, v_range=None):
        """frames at `us` and longerons at `vs` (metres)"""
        u0, u1 = u_range or (0.0, self.size[0])
        v0, v1 = v_range or (0.0, self.size[1])
        for u in us:
            self.line((u, v0), (u, v1), width)
            if rivets:
                self.dots((u + 0.03, v0), (u + 0.03, v1), rivets)
        for v in vs:
            self.line((u0, v), (u1, v), width)
            if rivets:
                self.dots((u0, v + 0.03), (u1, v + 0.03), rivets)

    # ---- the finish
    def weather(self, streak='u', amount=1.0):
        """what use leaves: cloudy changes of gloss, streaks along the airflow, a little dust in the colour"""
        h, w = self.h, self.w
        mu, mv = max(2, int(self.size[0] / 0.9)), max(2, int(self.size[1] / 0.9))
        cloud = value_noise(h, w, mu, mv, self.rng) - 0.5
        fine = value_noise(h, w, max(2, int(self.size[0] / 0.12)), max(2, int(self.size[1] / 0.12)), self.rng) - 0.5
        if streak == 'u':
            st = value_noise(h, w, max(2, int(self.size[0] / 1.6)), max(2, int(self.size[1] / 0.035)), self.rng) - 0.5
        else:
            st = value_noise(h, w, max(2, int(self.size[0] / 0.035)), max(2, int(self.size[1] / 1.6)), self.rng) - 0.5
        paint = 1 - self.metal
        self.rough += amount * (0.16 * cloud + 0.05 * fine + 0.10 * st)
        self.base *= (1 + amount * (0.22 * cloud + 0.10 * fine + 0.16 * st) * (0.4 + 0.6 * paint))[..., None]

    def finish(self):
        """seams and fasteners into colour, gloss and relief; returns (sRGB base, ORM, heights in metres)"""
        seam, dot = self.seam, self.dot
        # paint worn thin beside a seam: a lighter, duller rim two or three pixels wide
        rim = np.clip(box_blur(seam, 2) * 1.6 - seam, 0, 1)
        self.base += (np.array([0.05, 0.052, 0.056], np.float32) - self.base) * (0.5 * rim)[..., None] * (self.base.mean(-1, keepdims=True) < 0.2)
        self.rough += 0.10 * rim
        self.base *= (1 - 0.72 * seam)[..., None]
        self.rough += 0.3 * seam
        self.base *= (1 - 0.45 * dot)[..., None]
        self.rough += 0.12 * dot
        self.height -= 0.0016 * seam + 0.0005 * dot
        orm = np.stack([np.ones_like(self.rough), np.clip(self.rough, 0.04, 1), np.clip(self.metal, 0, 1)], -1).astype(np.float32)
        return to_srgb(self.base), orm, self.height


def normal_from_height(hm, metre):
    """a tangent-space normal map (+v up) from heights in metres; `metre`: metres per pixel"""
    hu = np.gradient(hm, axis=1) / metre
    hv = np.gradient(hm, axis=0) / metre
    n = np.stack([-hu, -hv, np.ones_like(hm)], -1)
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    return (n * 0.5 + 0.5).astype(np.float32)


# ------------------------------------------------------------------------------------------------ the sheets

def frac(sheet_h, f):
    return f * sheet_h


def paint_forebody(c):
    L, H = c.size
    d0 = SH.FB_STATIONS[0]
    U = lambda d: d - d0
    # the radome: a duller dielectric, its base ring, the lightning strips from the tip
    rad = c.band(0, U(SH.RADOME), 'u')
    c.fill(RADOME, 0.58, 0.0, rad)
    # the anti-glare panel ahead of the windscreen
    c.fill('#141517', 0.86, 0.0, c.box(U(SH.RADOME), 0.86 * H, U(4.3), H, soft=0.02))
    frames = [3.9, 4.25, 4.8, 5.3, 5.9, 6.5, 6.95, 7.6, 8.3, 9.0, 9.8, 10.6, 11.5, 12.5]
    longs = [0.17, 0.36, 0.50, 0.64, 0.80]
    c.cells([U(SH.RADOME)] + [U(d) for d in frames] + [L], [0] + [f * H for f in longs] + [H])
    c.grid([U(d) for d in frames], [], rivets=0.05)
    for f in longs:
        c.line((U(SH.RADOME), f * H), (L, f * H))
        c.dots((U(SH.RADOME), f * H + 0.03), (L, f * H + 0.03), 0.05)
    c.line((U(SH.RADOME), 0), (U(SH.RADOME), H), 0.02)
    c.line((U(SH.RADOME) - 0.05, 0), (U(SH.RADOME) - 0.05, H), 0.008)
    for f in (0.1, 0.3, 0.5, 0.7, 0.9):
        c.fill('#6b6d70', 0.5, 0.6, c.box(U(1.0), f * H - 0.006, U(2.6), f * H + 0.006))
    # avionics bay doors on the nose's sides, the nose gear's well and its doors underneath
    c.hatch(U(3.45), 0.39 * H, U(4.15), 0.61 * H)
    c.hatch(U(3.45), 0.20 * H, U(4.15), 0.345 * H)
    c.hatch(U(6.1), 0.22 * H, U(6.85), 0.34 * H)
    c.hatch(U(7.1), 0.40 * H, U(7.5), 0.60 * H, r=0.05)
    # (the forward doors shut again behind the leg: a seam and its hinge line; open only at the leg)
    c.rect(U(3.75), -0.1, U(4.42), 0.125 * H, 0.014)
    c.dots((U(3.8), 0.14 * H), (U(4.4), 0.14 * H), 0.07)
    well = c.box(U(4.46), 0.0, U(5.5), 0.115 * H, soft=0.008)
    c.fill('#0a0a0b', 0.85, 0.0, well)
    c.rect(U(4.46), -0.1, U(5.5), 0.115 * H, 0.014)
    # static ports, a drain, the ejection seat's warning triangle under the sill (red, white edged)
    for d, f in ((4.55, 0.46), (4.62, 0.46), (4.55, 0.43)):
        c.dots((U(d), f * H), (U(d), f * H), 1.0, 0.012)
    tri_u, tri_v = U(5.75), 0.70 * H
    for k, (col, s) in enumerate((('#d9dad4', 0.11), ('#b01a12', 0.085))):
        m = np.clip((s - np.abs(c.U - tri_u) * 1.9 - (tri_v - c.V) - 0.02 * k) * c.s, 0, 1) * (c.V <= tri_v) * (c.V >= tri_v - s)
        c.fill(col, 0.5, 0.0, m)
    c.weather()


def paint_canopy(c):
    L, H = c.size
    c.fill('#17181b', 0.5)
    d0 = SH.CN_STATIONS[0]
    # the frames' fasteners; the fairing behind the glass with its seams
    c.dots((0.0, 0.03), (SH.CN_GLASS_END - d0, 0.03), 0.07)
    for d in (SH.CN_ARCH, SH.CN_REAR):
        c.dots(((d[0] + d[1]) / 2 - d0, 0.0), ((d[0] + d[1]) / 2 - d0, H), 0.07)
    fair = c.band(SH.CN_GLASS_END - d0, L, 'u')
    c.fill(BLACK, BLACK_ROUGH, 0.0, fair)
    c.line((SH.CN_GLASS_END - d0, 0), (SH.CN_GLASS_END - d0, H), 0.016)
    c.line((7.7 - d0, 0), (7.7 - d0, H))
    c.hatch(7.1 - d0, 0.3 * H, 7.55 - d0, 0.8 * H)
    c.weather(amount=0.6)


def chine(d):
    return SH.DK_W(d)


def paint_deck_top(c):
    L, H = c.size
    d0 = SH.DK_STATIONS[0]
    U = lambda d: d - d0
    frames = [8.3, 9.2, 10.0, 10.8, 11.6, 12.4, 13.3, 14.2, 15.1, 16.0, 16.9, 17.6, 18.4]
    longs = [0.45, 0.85, 1.22, 1.62, 1.88]
    c.cells([0] + [U(d) for d in frames] + [L], [0] + longs + [H], amount=0.08)
    c.grid([U(d) for d in frames], [], rivets=0.05)
    for v in longs:
        c.line((U(8.3), v), (L, v))
        c.dots((U(8.3), v + 0.03), (L, v + 0.03), 0.05)
    # the strake's edge member beside the cockpit
    pts = [(U(d), chine(d) - 0.07) for d in np.linspace(5.9, 8.3, 14)]
    c.path(pts)
    # the auxiliary intakes' doors on the back, behind the canopy: louvred, side by side
    c.louvres(U(10.55), 0.5, U(11.45), 0.82, 9, along='u')
    c.louvres(U(10.55), 0.88, U(11.45), 1.2, 9, along='u')
    # engine bay hatches
    c.hatch(U(12.55), 0.5, U(13.2), 1.15)
    c.hatch(U(13.45), 0.9, U(15.0), 1.56, r=0.04)
    c.hatch(U(15.25), 0.9, U(16.8), 1.56, r=0.04)
    c.hatch(U(14.3), 0.06, U(15.9), 0.4)
    c.hatch(U(11.8), 1.66, U(12.3), 1.84, fasteners=0.05)
    # refuelling and filler caps
    for d, v in ((12.0, 0.2), (16.4, 0.2)):
        c.rect(U(d) - 0.07, v - 0.07, U(d) + 0.07, v + 0.07, 0.01, r=0.065)
    # bare heat-resisting metal round the engines' ends
    hot = c.band(U(17.6), L, 'u', soft=0.01) * c.band(0.5, 1.94, 'v', soft=0.01)
    metal_finish(c, hot, U(17.6), L)
    c.weather()


def metal_finish(c, mask, u0, u1):
    """bare titanium / steel: grey, straw and blue where it gets hot (towards u1), dull soot at the end"""
    t = np.clip((c.U - u0) / max(1e-6, u1 - u0), 0, 1)
    col = lin(METAL)[None, None, :] * np.ones_like(c.base)
    straw, blue, soot = lin('#6f5a3c'), lin('#3f4458'), lin('#26231f')
    w1 = np.exp(-((t - 0.45) / 0.16) ** 2)[..., None]
    w2 = np.exp(-((t - 0.72) / 0.12) ** 2)[..., None]
    w3 = np.clip((t - 0.82) / 0.18, 0, 1)[..., None]
    col = col + (straw - col) * 0.55 * w1
    col = col + (blue - col) * 0.5 * w2
    col = col + (soot - col) * 0.75 * w3
    m = np.clip(mask, 0, 1)
    c.base += (col - c.base) * m[..., None]
    c.rough += (0.36 + 0.3 * w3[..., 0] - c.rough) * m
    c.metal += (1.0 - 0.5 * w3[..., 0] - c.metal) * m


def paint_deck_bottom(c):
    L, H = c.size
    d0 = SH.DK_STATIONS[0]
    U = lambda d: d - d0
    frames = [8.3, 9.4, 10.4, 11.2, 12.3, 13.4, 14.5, 15.6, 16.6, 17.6]
    c.cells([0] + [U(d) for d in frames] + [L], [0, 0.22, SH.TUNNEL, 1.2, H])
    c.grid([U(d) for d in frames], [], rivets=0.05, v_range=(0, SH.TUNNEL))
    # the weapon bay's doors under the belly: the middle seam and the hinge lines
    c.line((U(11.2), 0.004), (U(15.6), 0.004), 0.016)
    c.line((U(11.2), 0.38), (U(15.6), 0.38), 0.014)
    c.dots((U(11.2), 0.345), (U(15.6), 0.345), 0.06)
    c.hatch(U(16.0), 0.05, U(17.3), 0.33)
    pts = [(U(d), chine(d) - 0.07) for d in np.linspace(5.9, 8.3, 14)]
    c.path(pts)
    c.line((U(8.3), 1.9), (U(10.4), 1.9))
    c.weather()


def paint_beaver(c):
    L, H = c.size
    c.grid([0.65, 1.0], [0.25 * H, 0.75 * H], rivets=0.05)
    edge = c.band(L - 0.12, L, 'u')
    c.fill('#6b6660', 0.42, 1.0, edge)
    c.weather()


def paint_nacelle(c):
    L, H = c.size
    U = lambda d: d - 7.7
    out, keel, inb = 0.25 * H, 0.5 * H, 0.75 * H
    frames = [8.9, 9.6, 10.4, 11.3, 12.2, 13.1, 14.0, 15.0, 16.0, 17.0, 17.9, 18.6]
    longs = [0.12 * H, out, 0.38 * H, keel, 0.62 * H, inb, 0.88 * H]
    c.cells([0] + [U(d) for d in frames] + [L], [0] + longs + [H], amount=0.08)
    c.grid([U(d) for d in frames], [], rivets=0.05)
    for v in longs:
        c.line((U(9.0), v), (L, v))
        c.dots((U(9.0), v + 0.03), (L, v + 0.03), 0.05)
    # the louvres under the intake trunk (the engine's extra air on the ground)
    for k in range(3):
        v0 = keel - 0.33 + k * 0.24
        c.louvres(U(9.35), v0, U(10.05), v0 + 0.18, 8, along='u')
    # the main gear's well in the trunk's outer lower quarter: two doors closed over it, the leg's opening
    c.hatch(U(9.95), 0.29 * H, U(11.05), 0.455 * H, fasteners=0.0, width=0.016, r=0.03)
    c.line((U(9.95), 0.37 * H), (U(11.05), 0.37 * H), 0.014)
    c.fill('#09090a', 0.85, 0.0, c.box(U(11.08), 0.285 * H, U(11.62), 0.40 * H, soft=0.01))
    c.rect(U(11.08), 0.285 * H, U(11.62), 0.40 * H, 0.016, r=0.03)
    # engine doors underneath, the accessory hatches on the side
    c.hatch(U(13.3), 0.40 * H, U(15.1), 0.60 * H, r=0.05)
    c.hatch(U(15.3), 0.40 * H, U(17.0), 0.60 * H, r=0.05)
    c.hatch(U(12.3), 0.19 * H, U(13.0), 0.31 * H)
    c.hatch(U(14.2), 0.20 * H, U(14.8), 0.30 * H)
    for d in (12.6, 14.6, 16.4):
        c.rect(U(d) - 0.05, keel + 0.34, U(d) + 0.05, keel + 0.44, 0.01, r=0.045)
    # bare metal over the afterburner
    hot = c.band(U(17.35), L, 'u', soft=0.008)
    metal_finish(c, hot, U(17.35), L + 0.9)
    c.weather()


def paint_duct(c):
    L, H = c.size
    t = np.clip(c.U / 2.6, 0, 1)
    col = lin('#3b3e43')[None, None, :] * (1 - t)[..., None] ** 1.6 + lin('#050506')[None, None, :] * (1 - (1 - t) ** 1.6)[..., None]
    c.base[:] = col
    c.rough[:] = 0.55
    c.fill(BLACK, 0.42, 0.0, c.band(0, 0.06, 'u'))
    for u in (0.5, 1.2, 2.0):
        c.line((u, 0), (u, H), 0.01)


def paint_wing(c, upper):
    L, H = c.size
    x0 = 1.9
    X = lambda x: x - x0
    F = lambda f: f * H
    ribs = [2.6, 3.3, 4.0, 4.8, 5.6, 6.4, 7.2, 7.9]
    spars = [0.14, 0.32, 0.55, 0.74]
    c.cells([0] + [X(x) for x in ribs] + [L], [0] + [F(f) for f in spars] + [H], amount=0.06)
    # the leading-edge flap's hinge, two spars, the trailing-edge surfaces' hinge line
    c.line((X(3.1), F(0.14)), (X(8.05), F(0.14)), 0.014)
    for f in (0.32, 0.55):
        c.line((X(2.0), F(f)), (X(8.2), F(f)))
        c.dots((X(2.0), F(f) + 0.035), (X(8.2), F(f) + 0.035), 0.05)
    c.line((X(3.75), F(0.74)), (X(8.0), F(0.74)), 0.016)
    c.line((X(2.15), F(0.80)), (X(3.7), F(0.80)), 0.016)
    for x in ribs:
        c.line((X(x), F(0.14)), (X(x), F(0.74)))
        c.dots((X(x) + 0.03, F(0.14)), (X(x) + 0.03, F(0.74)), 0.05)
    # the surfaces' ends: flaperon / aileron, the flap's inner and outer end, the leading-edge flap's sections
    for x in (3.75, 5.9, 8.0):
        c.line((X(x), F(0.74)), (X(x), H), 0.016)
    for x in (2.15, 3.7):
        c.line((X(x), F(0.80)), (X(x), H), 0.016)
    for x in (3.1, 5.5, 8.05):
        c.line((X(x), 0), (X(x), F(0.14)), 0.014)
    # actuator fairings' hatches on the lower side, the stores stations
    if not upper:
        for x in (3.5, 4.7, 5.9, 7.0):
            c.hatch(X(x) - 0.09, F(0.36), X(x) + 0.09, F(0.52), fasteners=0.045)
        for x in (4.4, 6.6):
            c.hatch(X(x) - 0.1, F(0.6), X(x) + 0.1, F(0.73), fasteners=0.045)
    else:
        c.hatch(X(2.25), F(0.36), X(2.55), F(0.5))
        c.hatch(X(4.3), F(0.58), X(4.6), F(0.7), fasteners=0.045)
        c.hatch(X(6.5), F(0.58), X(6.8), F(0.7), fasteners=0.045)
    # the white leading edge of the forward-swept panel
    white = c.band(0, F(0.036), 'v', soft=0.004) * c.band(X(3.0), L, 'u', soft=0.05)
    c.weather(streak='v')
    c.fill(WHITE, 0.45, 0.0, white)
    c.line((X(3.0), F(0.036)), (L, F(0.036)), 0.008)


def paint_moving(c):
    L, H = c.size
    F = lambda f: f * H
    c.cells([0, L * 0.33, L * 0.66, L], [0, F(0.3), F(0.62), H], amount=0.06)
    c.line((0.0, F(0.3)), (L * 0.95, F(0.3)))
    c.line((0.0, F(0.62)), (L * 0.95, F(0.62)))
    c.dots((0.0, F(0.3) + 0.03), (L * 0.95, F(0.3) + 0.03), 0.05)
    for u in (L * 0.33, L * 0.66):
        c.line((u, F(0.06)), (u, F(0.95)))
    # the pivot's fitting at the root
    c.rect(0.02, F(0.42), 0.34, F(0.66), 0.012, r=0.05)
    c.dots((0.06, F(0.46)), (0.3, F(0.46)), 0.05)
    c.dots((0.06, F(0.62)), (0.3, F(0.62)), 0.05)
    white = c.band(0, F(0.05), 'v', soft=0.004)
    c.weather(streak='v')
    c.fill(WHITE, 0.45, 0.0, white)
    c.line((0, F(0.05)), (L, F(0.05)), 0.008)


def paint_fin(c):
    L, H = c.size
    b = SH.fin_span()
    S_ = lambda s: s + SH.FIN['below']
    F = lambda f: f * H
    ribs = [0.6, 1.3, 2.0, 2.7]
    c.cells([0] + [S_(s) for s in ribs] + [L], [0, F(0.3), F(0.70), H], amount=0.06)
    for s in ribs:
        c.line((S_(s), F(0.05)), (S_(s), F(0.70)))
        c.dots((S_(s) + 0.03, F(0.05)), (S_(s) + 0.03, F(0.70)), 0.05)
    c.line((S_(0.1), F(0.3)), (S_(b - 0.45), F(0.3)))
    # the rudder: hinge line, lower and upper end, its two actuator hatches
    c.line((S_(0.22), F(0.70)), (S_(b - 0.5), F(0.70)), 0.016)
    for s in (0.22, b - 0.5):
        c.line((S_(s), F(0.70)), (S_(s), H), 0.016)
    c.hatch(S_(0.7), F(0.56), S_(0.95), F(0.67), fasteners=0.045)
    c.hatch(S_(2.0), F(0.56), S_(2.25), F(0.67), fasteners=0.045)
    # the fin's root fairing
    c.line((S_(0.06), 0), (S_(0.06), H), 0.014)
    c.weather(streak='v')
    # white: the leading edge and the dielectric cap
    c.fill(WHITE, 0.45, 0.0, c.band(0, F(0.045), 'v', soft=0.004) * c.band(S_(0.12), L, 'u', soft=0.03))
    c.fill(WHITE, 0.5, 0.0, c.band(S_(b - 0.42), L, 'u', soft=0.004))
    c.line((S_(b - 0.42), 0), (S_(b - 0.42), H), 0.01)
    c.line((S_(0.12), F(0.045)), (S_(b - 0.42), F(0.045)), 0.008)


def paint_boom(c, side):
    L, H = c.size
    U = lambda d: d - 15.0
    frames = [16.4, 17.3, 18.2, 19.0, 19.6]
    c.cells([0] + [U(d) for d in frames] + [L], [0, 0.25 * H, 0.5 * H, 0.75 * H, H], amount=0.06)
    c.grid([U(d) for d in frames], [0.25 * H, 0.75 * H], rivets=0.05)
    c.hatch(U(17.5), 0.30 * H, U(18.0), 0.45 * H)
    if side == 'r':
        # the brake parachute's container
        c.hatch(U(20.5), 0.35 * H, U(21.45), 0.65 * H, r=0.06)
    c.weather()
    tip = U(SH.BOOM_TIP[side])
    c.fill(WHITE, 0.5, 0.0, c.band(tip, L, 'u', soft=0.004))
    c.line((tip, 0), (tip, H), 0.012)


def paint_nozzle_out(c):
    L, H = c.size
    c.fill(METAL, 0.36, 1.0)
    metal_finish(c, np.ones_like(c.rough), -0.9, L)
    n = 20
    for k in range(n):
        v = (k + 0.5) / n * H
        c.line((0.11, v), (L, v), 0.014)
        # every flap's stiffening rib
        c.dots((0.14, v + H / n / 2), (L - 0.05, v + H / n / 2), 0.09, 0.005)
    c.line((0.085, 0), (0.085, H), 0.02)
    c.line((0.55, 0), (0.55, H), 0.01)
    st = value_noise(c.h, c.w, 3, 60, c.rng) - 0.5
    c.base *= (1 + 0.3 * st)[..., None]
    c.rough += 0.12 * st


def paint_nozzle_in(c):
    L, H = c.size
    c.fill('#1a1816', 0.72, 0.6)
    t = np.clip(c.U / L, 0, 1)
    c.base *= (1.5 - 1.3 * t)[..., None]
    n = 20
    for k in range(n):
        v = (k + 0.5) / n * H
        c.line((0.0, v), (0.95, v), 0.014)
    st = value_noise(c.h, c.w, 3, 40, c.rng) - 0.5
    c.base *= (1 + 0.3 * st)[..., None]


def paint_tub(c):
    L, H = c.size
    c.fill(PIT, 0.72)
    c.fill('#22282b', 0.85, 0.0, c.band(0, 0.5, 'v'))
    # boxes and switch panels along the walls
    for k in range(6):
        u0 = 0.15 + k * 0.38
        c.fill('#101214', 0.6, 0.0, c.box(u0, 1.04, u0 + 0.3, 1.32))
        c.rect(u0, 1.04, u0 + 0.3, 1.32, 0.008)
        for j in range(3):
            c.dots((u0 + 0.05, 1.1 + j * 0.08), (u0 + 0.25, 1.1 + j * 0.08), 0.05, 0.008)
    c.line((0, 1.0), (L, 1.0), 0.01)
    c.weather(amount=0.6)


def paint_shield(c):
    c.fill('#0b0b0c', 0.95)


def paint_panel(c):
    """the instrument panel: three displays, the standby dials over them, key rows (nothing lit: a parked aircraft)"""
    L, H = c.size
    c.fill('#20262a', 0.7)
    cx = L / 2

    def screen(u0, v0, u1, v1):
        c.fill('#0a0b0c', 0.5, 0.0, c.box(u0 - 0.012, v0 - 0.012, u1 + 0.012, v1 + 0.012))
        c.fill('#0c1a14', 0.12, 0.0, c.box(u0, v0, u1, v1))
        for k in range(5):
            u = u0 + (u1 - u0) * (k + 0.5) / 5
            c.fill('#3b3f42', 0.6, 0.0, c.box(u - 0.006, v0 - 0.011, u + 0.006, v0 - 0.003))
            c.fill('#3b3f42', 0.6, 0.0, c.box(u - 0.006, v1 + 0.003, u + 0.006, v1 + 0.011))

    screen(cx - 0.085, 0.2, cx + 0.085, 0.42)
    screen(cx - 0.29, 0.22, cx - 0.13, 0.42)
    screen(cx + 0.13, 0.22, cx + 0.29, 0.42)
    for k, du in enumerate((-0.24, -0.14, 0.14, 0.24)):
        r = 0.034
        d = np.hypot(c.U - (cx + du), c.V - 0.52)
        c.fill('#050505', 0.3, 0.0, np.clip((r - d) * c.s + 0.5, 0, 1))
        c.fill('#8a8c8a', 0.5, 0.2, np.clip((0.004 - np.abs(d - r)) * c.s + 0.5, 0, 1))
        a = 0.6 + k * 1.1
        c._stamp(c.dot, (cx + du, 0.52), (cx + du + 0.026 * math.cos(a), 0.52 + 0.026 * math.sin(a)), 0.004)
    c.fill('#d8d8d0', 0.5, 0.0, c.dot)
    c.dot[:] = 0
    # key rows under the displays, the warning panel on top
    for row in range(2):
        for k in range(12):
            u = cx - 0.3 + k * 0.055
            c.fill('#44484b', 0.55, 0.0, c.box(u, 0.06 + row * 0.05, u + 0.03, 0.09 + row * 0.05))
    for k in range(8):
        u = cx - 0.11 + k * 0.028
        c.fill('#5a2a14' if k % 3 else '#5a5214', 0.5, 0.0, c.box(u, 0.47, u + 0.02, 0.5))


PAINTERS = {
    'forebody': paint_forebody, 'canopy': paint_canopy, 'deck_top': paint_deck_top, 'deck_bottom': paint_deck_bottom,
    'beaver': paint_beaver, 'nacelle': paint_nacelle, 'duct': paint_duct,
    'wing_a': lambda c: paint_wing(c, True), 'wing_b': lambda c: paint_wing(c, False),
    'canard_a': paint_moving, 'canard_b': paint_moving, 'stab_a': paint_moving, 'stab_b': paint_moving,
    'fin': paint_fin, 'boom_l': lambda c: paint_boom(c, 'l'), 'boom_r': lambda c: paint_boom(c, 'r'),
    'nozzle_out': paint_nozzle_out, 'nozzle_in': paint_nozzle_in, 'tub': paint_tub, 'shield': paint_shield, 'panel': paint_panel,
}


def paint_atlas(atlas, extra=None):
    """every sheet and swatch into the atlas' three pictures: (sRGB base, ORM, normal), each (n, n, 3), row 0 at the bottom"""
    n, pad = atlas.n, atlas.pad
    base = np.empty((n, n, 3), np.float32)
    base[:] = to_srgb(lin(BLACK))
    orm = np.empty((n, n, 3), np.float32)
    orm[:] = (1.0, BLACK_ROUGH, 0.0)
    nrm = np.empty((n, n, 3), np.float32)
    nrm[:] = (0.5, 0.5, 1.0)
    painters = dict(PAINTERS)
    painters.update(extra or {})
    for k, name in enumerate(sorted(atlas.sheets)):
        sheet = atlas.sheets[name]
        c = Canvas(sheet, 1000 + k)
        fn = painters.get(name)
        if fn:
            fn(c)
        else:
            c.weather()
        b, o, h = c.finish()
        nm = normal_from_height(h, 1.0 / sheet.scale)
        x0, y0, w, hh = sheet.px
        sl = (slice(y0 - pad, y0 + hh + pad), slice(x0 - pad, x0 + w + pad))
        p = ((pad, pad), (pad, pad), (0, 0))
        base[sl] = np.pad(b, p, mode='edge')
        orm[sl] = np.pad(o, p, mode='edge')
        nrm[sl] = np.pad(nm, p, mode='edge')
    for name, sw in atlas.swatches.items():
        x0, y0 = sw['px']
        base[y0:y0 + atlas.cell, x0:x0 + atlas.cell] = to_srgb(lin(sw['colour']))
        orm[y0:y0 + atlas.cell, x0:x0 + atlas.cell] = (1.0, sw['rough'], sw['metal'])
    return base, orm, nrm
