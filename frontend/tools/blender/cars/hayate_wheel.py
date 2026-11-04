"""
The AE86 GT-APEX (late) wheel: 14 x 5.5J alloy with eight flat spokes tapering towards the polished lip and
triangular openings between them, a black centre with four lug nuts; 185/60R14 tyre (outer radius scaled to the
game's wheelRadius 0.30), ventilated disc and a single-piston caliper.

Built for the LEFT wheels (outer face +x) round the wheel centre (local origin); the right wheels are mirrored.
Measured on Commons "1986 Toyota Sprinter Trueno 3-door GT APEX.jpg" (Toyota museum car, stock wheels).
"""
import math

from mathutils import Matrix, Vector

import hayate_kit as K

R_OUT = 0.30            # tyre outer radius
R_RIM = 0.1778          # 14 in bead seat
R_FLANGE = 0.192        # rim flange (lip) outer radius
TYRE_W = 0.185
RIM_W = 0.140           # 5.5 in
FACE_X = 0.050          # the spoke face at the hub (offset outward from the tyre centre plane)
N_SPOKES = 8
SEG = 48                # around the tyre


def tyre(mesh):
    """lathe of the tyre section, inner bead → tread → outer bead; UV: u = around, v = across the profile"""
    h = TYRE_W / 2
    # (x, r): inner bead, sidewall, shoulder, tread with three grooves, mirrored
    half = [(-0.072, R_RIM + 0.006), (-0.084, 0.205), (-0.092, 0.235), (-0.091, 0.262), (-0.084, 0.284), (-0.072, 0.296),
            (-0.060, R_OUT), (-0.044, R_OUT), (-0.042, R_OUT - 0.007), (-0.034, R_OUT - 0.007), (-0.032, R_OUT), (-0.008, R_OUT),
            (-0.006, R_OUT - 0.007)]
    prof = half + [(-x, r) for x, r in reversed(half)]
    n = len(prof)
    # v along the profile by arc length
    L = [0.0]
    for a, b in zip(prof[:-1], prof[1:]):
        L.append(L[-1] + math.dist(a, b))
    vs = [l / L[-1] for l in L]
    mesh.lathe(prof, SEG, mats='tire', uv=lambda k, u: (u * 6.0, vs[k]))


def rim(mesh):
    """barrel, lip, the spoked face and the centre"""
    # barrel (seen through the openings): from the inner flange to just behind the face, facing the axle
    barrel = [(0.068, R_RIM - 0.004), (0.020, R_RIM - 0.006), (-0.040, R_RIM - 0.006), (-0.072, R_RIM - 0.002), (-0.074, R_FLANGE - 0.004)]
    mesh.lathe(barrel, 48, mats='rim')
    # polished lip on the outside: flange round-over
    lip = [(0.068, R_FLANGE + 0.003), (0.078, R_FLANGE + 0.001), (0.080, R_FLANGE - 0.006), (0.074, R_RIM + 0.004), (0.060, R_RIM + 0.002)]
    mesh.lathe(lip, 48, mats='chrome')
    # the face: polar grid per spoke sector
    r_hub, r_in, r_out, r_face = 0.058, 0.088, 0.163, R_RIM + 0.002

    def face_x(r):
        # a flat face, barely proud at the hub: proud at the hub, falling towards the lip
        return FACE_X + 0.003 * (1 - (r - r_hub) / (r_face - r_hub))

    sector = 2 * math.pi / N_SPOKES

    def spoke_half(r):
        """angular half width of a spoke at radius r: broad flat spokes, the openings narrow triangles near the rim"""
        if r <= r_in:
            return sector / 2
        t = (r - r_in) / (r_out - r_in)
        return sector / 2 - K.lerp(0.014, 0.150, t ** 0.85)

    radii = [r_hub, 0.066, 0.074, 0.081, r_in, 0.104, 0.120, 0.136, 0.150, r_out, 0.170, r_face]
    for k in range(N_SPOKES):
        a0 = k * sector
        rows = []
        for r in radii:
            hw = spoke_half(r)
            # columns: spoke centre → spoke edge → opening → next spoke edge → next spoke centre
            angs = [a0, a0 + hw * 0.5, a0 + hw]
            ob = a0 + sector - hw
            for q in range(1, 4):
                angs.append(K.lerp(a0 + hw, ob, q / 4))
            angs += [ob, a0 + sector - hw * 0.5, a0 + sector]
            x = face_x(r)
            rows.append([(x, r * math.cos(a), r * math.sin(a)) for a in angs])

        def mat(i, j):
            r0, r1 = radii[j], radii[j + 1]
            if 2 <= i <= 5 and r0 >= r_in - 1e-9 and r1 <= r_out + 1e-9:
                return None             # opening
            return 'rim'
        # i around (+angle), j outward: normal = d/di × d/dj; with x outward the sense needs flipping
        mesh.grid([[(p[0], p[1], p[2]) for p in row] for row in rows], mat, flip=True)
        # walls of the opening (into the wheel, 22 mm)
        j0, j1 = radii.index(r_in), radii.index(r_out)
        loop = [rows[j][2] for j in range(j0, j1 + 1)] + rows[j1][3:6] + [rows[j][6] for j in range(j1, j0 - 1, -1)] + list(reversed(rows[j0][3:6]))
        for a, b in zip(loop, loop[1:] + loop[:1]):
            a2 = (a[0] - 0.026, a[1], a[2])
            b2 = (b[0] - 0.026, b[1], b[2])
            mid = Vector(((a[1] + b[1]) / 2, (a[2] + b[2]) / 2))
            cen = Vector(((loop[0][1] + loop[len(loop) // 2][1]) / 2, (loop[0][2] + loop[len(loop) // 2][2]) / 2))
            d = (cen - mid)
            mesh.face([a, b, b2, a2], 'rim', out=(0.0, d.x, d.y), smooth=False)
    # the black centre with four lug nuts and a small cap
    cen = [(face_x(r_hub) + 0.001, r_hub), (face_x(r_hub) - 0.004, r_hub - 0.004), (face_x(r_hub) - 0.010, 0.050), (face_x(r_hub) - 0.010, 0.0)]
    mesh.lathe(cen, 32, mats='rim')
    for k in range(4):
        a = math.pi / 4 + k * math.pi / 2
        c = (face_x(r_hub) - 0.004, 0.0335 * math.cos(a), 0.0335 * math.sin(a))
        nut = [(0.0, 0.0), (0.016, 0.0), (0.016, 0.0105), (0.004, 0.0115), (0.0, 0.0115)]
        prof = [(c[0] + x, r) for x, r in reversed(nut)]
        m = K.Mesh('nut')
        m.lathe([(x, r) for x, r in prof], 6, mats='chrome', smooth=False)
        m.transform(Matrix.Translation(K.B(0, c[1], c[2])))
        mesh.merge(m)
    cap = [(face_x(r_hub) - 0.006, 0.020), (face_x(r_hub) + 0.004, 0.014), (face_x(r_hub) + 0.004, 0.0)]
    mesh.lathe(cap, 16, mats='chrome')


def disc(mesh, front=True):
    """ventilated disc (front 241 mm, rear 258 mm solid... both shown vented) and the hat"""
    rd = 0.122 if front else 0.129
    t = 0.020 if front else 0.010
    x0 = -0.020
    prof = [(x0 - t, 0.075), (x0 - t, rd), (x0, rd), (x0, 0.075), (x0 + 0.030, 0.070), (x0 + 0.030, 0.0)]
    mesh.lathe(prof, 40, mats='disc')


def caliper(mesh, front=True):
    """a single-piston floating caliper astride the disc's edge, behind the axle and a little above it"""
    rd = 0.122 if front else 0.129
    m = K.Mesh('cal')
    m.box('brake', -0.068, 0.010, rd - 0.045, rd + 0.016, -0.036, 0.036, bevel=0.010, segments=2)
    m.box('brake', -0.074, -0.040, rd - 0.030, rd + 0.004, -0.050, 0.050, bevel=0.008, segments=1)
    a = math.radians(-62)            # from straight up towards the rear
    m.warp(lambda p: K.rot_x(p, a))
    mesh.merge(m)


def wheel_meshes(front=True):
    """(spinning parts, caliper) as Meshes for a left wheel"""
    spin = K.Mesh('spin')
    tyre(spin)
    rim(spin)
    disc(spin, front)
    cal = K.Mesh('caliper')
    caliper(cal, front)
    return spin, cal
