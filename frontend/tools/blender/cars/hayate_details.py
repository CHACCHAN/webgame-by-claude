"""
Details laid on the AE86 body: the slim grille and corner lamps under the bonnet's edge, the bumper lamps, grille and
number plates, the tail lamp band, the side stripes and shut lines, door handles and mirrors, window frames and
rubbers, the cowl and wipers, the tailpipe. Positions measured on the reference photos (hayate.py) or estimated.

All built for the left half (+x) where they are symmetric (mirrored by the caller) unless the name says otherwise.
"""
import math

from mathutils import Vector

import hayate_kit as K
import hayate_body as BD

GAP_W = 0.0045          # shut line width
GAP_LIFT = 0.0012


def _ray_x(bvh, y, z, x0=1.4):
    h = K.hit(bvh, (x0, y, z), (-1, 0, 0))
    return h


def _ray_z(bvh, x, y, front=True):
    s = 1 if front else -1
    h = K.hit(bvh, (x, y, s * 3.0), (0, 0, -s))
    return h


def patch(mesh, bvh, mat, u_range, v_range, along, side=1, nu=6, nv=3, lift=0.003, uv=True, uv_box=(0, 1, 0, 1)):
    """
    a rectangle laid on the body by rays: along 'z' (from the front/rear: u = x, v = y), 'x' (from the side: u = z,
    v = y); side = +1 from +z / +x, −1 from −z
    """
    u0, u1 = u_range
    v0, v1 = v_range
    pts = []
    for j in range(nv + 1):
        row = []
        for i in range(nu + 1):
            u = K.lerp(u0, u1, i / nu)
            v = K.lerp(v0, v1, j / nv)
            if along == 'z':
                h = K.hit(bvh, (u, v, side * 3.0), (0, 0, -side))
            else:
                h = K.hit(bvh, (side * 1.4, v, u), (-side, 0, 0))
            if h is None:
                row.append(None)
                continue
            p, n = h
            d = Vector((0, 0, -side)) if along == 'z' else Vector((-side, 0, 0))
            if n.dot(d) > 0:
                n = -n
            row.append(tuple(p + n * lift))
        pts.append(row)
    a, b, c, d_ = uv_box
    out = (0, 0, side) if along == 'z' else (side, 0, 0)
    for j in range(nv):
        for i in range(nu):
            q = [pts[j][i], pts[j][i + 1], pts[j + 1][i + 1], pts[j + 1][i]]
            if any(p is None for p in q):
                continue
            uvs = None
            if uv:
                uq = [(i, j), (i + 1, j), (i + 1, j + 1), (i, j + 1)]
                fu = (lambda t: K.lerp(a, b, t)) if not (along == 'x' and side > 0) and not (along == 'z' and side < 0) else (lambda t: K.lerp(b, a, t))
                uvs = [(K.lerp(a, b, ii / nu) if not (along == 'z' and side < 0) else K.lerp(b, a, ii / nu), K.lerp(c, d_, jj / nv)) for ii, jj in uq]
            mesh.face(q, mat, uvs=uvs, out=out)
    return pts


# ---------------------------------------------------------------- front


def nose(mesh, bvh):
    """slim grille between the pods, corner lamps on the fender corners"""
    # grille: a recessed black slot with five horizontal slats, x 0…0.352 (left half)
    zf = BD.Z_NOSE - 0.024
    y0, y1 = 0.712, 0.752
    xg = 0.352
    mesh.box('trim', -0.001, xg, y0 - 0.004, y0, zf - 0.03, zf + 0.004)
    mesh.box('trim', -0.001, xg, y1, y1 + 0.004, zf - 0.03, zf + 0.004)
    mesh.box('trim', xg, xg + 0.006, y0 - 0.004, y1 + 0.004, zf - 0.03, zf + 0.004)
    # back wall (dark) and the slats
    mesh.face([(0, y0, zf - 0.03), (xg, y0, zf - 0.03), (xg, y1, zf - 0.03), (0, y1, zf - 0.03)], 'interior', out=(0, 0, 1))
    for k in range(4):
        y = K.lerp(y0 + 0.007, y1 - 0.007, k / 3)
        mesh.box('trim', 0.0, xg, y - 0.0025, y + 0.0025, zf - 0.014, zf + 0.001, bevel=0.001, segments=1)
    # corner lamps: a lens wrapping the fender corner, smoked in front, amber on the side
    path = []
    # front part from x = 0.565 to the corner, then back along the side
    for k in range(9):
        x = K.lerp(0.585, 0.762, k / 8)
        path.append((x, 0.722, BD.Z_NOSE))
    for k in range(1, 7):
        a = math.radians(90 * k / 6)
        path.append((0.762 + 0.022 * math.sin(a), 0.722, BD.Z_NOSE - 0.03 * (1 - math.cos(a))))
    for k in range(1, 6):
        path.append((0.786, 0.722, BD.Z_NOSE - 0.03 - 0.10 * k / 5))
    # laid by nearest point on the body; u along the path stays in the texture's smoked part (a dark amber lens)
    K.lay_strip(mesh, bvh, path, 0.036, 'amber', lift=0.004, u_scale=1.45)


def bumper_front(mesh, bvh):
    """lamps and grille on the black face of the front bumper, the plate (right of centre on the real car)"""
    fpath, _ = BD.bumper_paths()

    def face_z(x, out=-0.010):
        # the bumper's black face z at x (left half, in front of the corner)
        for a, b in zip(fpath[:-1], fpath[1:]):
            if a[0] <= x <= b[0]:
                t = (x - a[0]) / max(1e-9, b[0] - a[0])
                return K.lerp(a[1], b[1], t) + out
        return fpath[-1][1] + out
    # amber turn lamp (inboard) and clear lamp (outboard): lenses proud of the face in a black bezel
    # lenses flush in the black face right under the white bar, split into cells so they follow its curve
    for x0, x1, mat in ((0.400, 0.560, 'amber'), (0.565, 0.705, 'headlight')):
        y0, y1 = 0.520, 0.585
        n = 4
        for c in range(n):
            xa, xb = K.lerp(x0, x1, c / n), K.lerp(x0, x1, (c + 1) / n)
            za, zb = face_z(xa, -0.003), face_z(xb, -0.003)
            ua, ub = c / n, (c + 1) / n
            if mat == 'amber':
                ua, ub = 0.6 + 0.4 * ua, 0.6 + 0.4 * ub
            mesh.face([(xa, y0, za), (xb, y0, zb), (xb, y1, zb), (xa, y1, za)], mat,
                      uvs=[(ua, 0), (ub, 0), (ub, 1), (ua, 1)], out=(0, 0, 1))
    # central grille: a recessed slot with four horizontal slats (x 0…0.385)
    y0, y1 = 0.506, 0.585
    xg = 0.385
    zc = face_z(0.0)
    mesh.face([(0.0, y0, zc - 0.03), (xg, y0, zc - 0.03), (xg, y1, zc - 0.03), (0.0, y1, zc - 0.03)], 'interior', out=(0, 0, 1))
    for (a, b) in (((0, y0), (xg, y0)), ((xg, y0), (xg, y1)), ((xg, y1), (0, y1))):
        mid = ((a[0] + b[0]) / 2 - xg / 2, (a[1] + b[1]) / 2 - (y0 + y1) / 2, 0)
        mesh.face([(a[0], a[1], face_z(a[0])), (b[0], b[1], face_z(b[0])), (b[0], b[1], zc - 0.03), (a[0], a[1], zc - 0.03)], 'trim',
                  out=(-mid[0], -mid[1], 0), smooth=False)
    for k in range(4):
        y = K.lerp(y0 + 0.016, y1 - 0.016, k / 3)
        mesh.box('trim', 0.0, xg, y - 0.005, y + 0.005, zc - 0.026, face_z(xg) - 0.004, bevel=0.002, segments=1)


def plate(mesh, centre, w, h, face, uv_box, mat='plate'):
    """a number plate: thin plate (texture) on a black holder; face: +1 front, −1 rear"""
    cx, cy, cz = centre
    hw, hh = w / 2, h / 2
    s = face
    mesh.box('trim', cx - hw - 0.01, cx + hw + 0.01, cy - hh - 0.01, cy + hh + 0.01, cz - 0.006, cz + 0.006)
    z = cz + s * 0.0065
    u0, u1, v0, v1 = uv_box
    q = [(cx - hw, cy - hh, z), (cx + hw, cy - hh, z), (cx + hw, cy + hh, z), (cx - hw, cy + hh, z)]
    uv = [(u0, v0), (u1, v0), (u1, v1), (u0, v1)]
    if s < 0:
        q = [q[1], q[0], q[3], q[2]]
        uv = [uv[0], uv[1], uv[2], uv[3]]
        uv = [(u0, v0), (u1, v0), (u1, v1), (u0, v1)]
    mesh.face(q, mat, uvs=uv, out=(0, 0, s))


def plates(mesh, bvh):
    """front plate on the bumper's black face (a little to the right of centre), rear plate in the tail garnish"""
    W, H = 0.33, 0.165
    for cx, cy, s in ((-0.08, 0.400, 1), (0.0, 0.645, -1)):
        zs = []
        for dx in (-W / 2, 0.0, W / 2):
            for dy in (-H / 2, H / 2):
                h = K.hit(bvh, (cx + dx, cy + dy, s * 3.0), (0, 0, -s))
                if h is not None:
                    zs.append(h[0].z if hasattr(h[0], 'z') else h[0][2])
        z = (max(zs) if s > 0 else min(zs)) + s * 0.010
        plate(mesh, (cx, cy, z), W, H, s, (0, 1, 0, 1))


# ---------------------------------------------------------------- rear

TAIL_Y = (0.572, 0.757)


def tail(mesh, bvh):
    """the full-width lamp band: red / smoked lamps outboard, a black garnish between them (left half)"""
    y0, y1 = TAIL_Y
    # garnish x 0 … 0.30 and the lamps 0.30 → the corner, wrapping 5 cm round the side
    patch(mesh, bvh, 'trim', (0.0, 0.302), (y0, y1), 'z', side=-1, nu=5, nv=3, lift=0.004, uv=False)
    # the black tail panel: full width, a straight top edge above the lamps
    patch(mesh, bvh, 'trim', (0.0, 0.775), (0.498, 0.800), 'z', side=-1, nu=14, nv=3, lift=0.0025, uv=False)
    pts, _ = BD.ring(BD.Z_TAIL)
    # lamp: path along the tail at mid-height, from x = 0.30 round the corner; ribbon across (vertical)
    path = []
    ym = (y0 + y1) / 2
    for k in range(13):
        x = K.lerp(0.302, 0.70, k / 12)
        path.append(BD.tail_warp((x, ym, BD.Z_TAIL)))
    zt = BD.tail_warp((0.70, ym, BD.Z_TAIL))[2]
    for k in range(1, 7):
        a = math.radians(90 * k / 6)
        path.append((0.70 + 0.065 * math.sin(a), ym, zt + 0.07 * (1 - math.cos(a))))
    path.append((0.768, ym, zt + 0.10))
    K.lay_strip(mesh, bvh, path, y1 - y0, 'taillight', lift=0.004, uv_v=(1.0, 0.0))
    # reverse lamp (clear) and turn lamp (amber) cells on the lens
    # lower row (as on the late model): red inboard, the clear reverse lamp, the smoked amber turn lamp outboard
    ys = (y0 + 0.010, y0 + 0.078)
    for x0, x1, mat in ((0.470, 0.555, 'reverse'), (0.575, 0.712, 'amber')):
        patch(mesh, bvh, mat, (x0, x1), ys, 'z', side=-1, nu=3, nv=1, lift=0.0065, uv=True, uv_box=(0.62, 1, 0.1, 0.9))


# ---------------------------------------------------------------- sides


def stripe(mesh, bvh):
    """the thin stripe in the black lower band (body colour), from the door's front edge to the rear arch"""
    zf, zr = 0.62, BD.ZR + BD.ARCH_R + 0.06
    y0, y1 = 0.405, 0.430
    path = [(0.9, (y0 + y1) / 2, K.lerp(zf, zr, k / 30)) for k in range(31)]
    K.lay_strip(mesh, bvh, path, y1 - y0, 'paint', lift=0.0015, direction=(-1, 0, 0))
    # slanted front end
    h0 = K.hit(bvh, (1.4, y0, zf - 0.02), (-1, 0, 0))
    h1 = K.hit(bvh, (1.4, y1, zf), (-1, 0, 0))
    h2 = K.hit(bvh, (1.4, y0, zf), (-1, 0, 0))
    if h0 and h1 and h2:
        mesh.face([tuple(h0[0] + Vector((0.0015, 0, 0))), tuple(h2[0] + Vector((0.0015, 0, 0))), tuple(h1[0] + Vector((0.0015, 0, 0)))],
                  'accent', out=(1, 0, 0))


def gaps(mesh, bvh):
    """shut lines: doors, hood, pop-up lids, hatch, fuel lid (right side only: see fuel_lid)"""
    def line(pts, d=None):
        K.lay_strip(mesh, bvh, pts, GAP_W, 'trim', lift=GAP_LIFT, direction=d)
    # door: front edge (just behind the front arch, leaning with the A-pillar foot), rear edge, bottom along the sill
    zf_top, zf_bot = BD.Z_COWL + 0.005, BD.ZF - BD.ARCH_R - 0.045
    door_front = [(0.9, K.lerp(0.905, 0.26, k / 16), K.lerp(zf_top, zf_bot, (k / 16) ** 2 * 0.0 + k / 16 * 0.0) + K.lerp(zf_top - zf_top, 0, 0))
                  for k in range(17)]
    door_front = [(0.9, K.lerp(0.905, 0.26, k / 16), K.lerp(0.700, 0.758, min(1.0, k / 4)) if k < 5 else 0.758) for k in range(17)]
    line(door_front, (-1, 0, 0))
    door_rear = [(0.9, K.lerp(0.925, 0.26, k / 16), -0.505 - 0.012 * k / 16) for k in range(17)]
    line(door_rear, (-1, 0, 0))
    sill = [(0.9, 0.262, K.lerp(0.758, -0.517, k / 20)) for k in range(21)]
    line(sill, (-1, 0, 0))
    # hood: along the fender (h8 row) from the cowl to the lid, and round the lids (inner and rear edges)
    hood = [(*BD.HULL('h8', z), z) for z in [K.lerp(BD.Z_COWL - 0.02, BD.Z_LID, k / 16) for k in range(17)]]
    line([(p[0], p[1] + 0.01, p[2]) for p in hood])
    lid = BD.lid_grid()
    rear = [p for p in (lid[j][-1] for j in range(len(lid)))]
    inner = [lid[-1][i] for i in range(len(lid[0]))]
    line([(p[0], p[1] + 0.01, p[2] - 0.002) for p in rear])
    line([(p[0] - 0.002, p[1] + 0.01, p[2]) for p in inner])
    # hood's rear edge at the cowl (under the windscreen base, mostly covered by the cowl panel)
    # hatch: across the tail just above the lamp band, and up beside the hatch glass
    yh = 0.802
    line([BD.tail_warp((K.lerp(0.0, 0.70, k / 14), yh, BD.Z_TAIL + 0.05)) for k in range(15)], (0, 0, 1))


def fuel_lid(mesh, bvh):
    """the fuel filler lid on the right rear quarter (−x), a rounded rectangle outline"""
    zc, yc, w, h, r = -1.78, 0.775, 0.135, 0.105, 0.015
    pts = []
    for (sx, sy, a0) in ((1, 1, 0), (-1, 1, 90), (-1, -1, 180), (1, -1, 270)):
        for k in range(4):
            a = math.radians(a0 + 90 * k / 3)
            pts.append((-1.0, yc + sy * (h / 2 - r) + r * math.sin(a), zc + sx * (w / 2 - r) + r * math.cos(a)))
    pts.append(pts[0])
    K.lay_strip(mesh, bvh, pts, GAP_W, 'trim', lift=GAP_LIFT, direction=(1, 0, 0))


def handle(mesh, bvh):
    """door handle: a black pull in a shallow recess at the door's rear top"""
    z0, z1, y = -0.43, -0.31, 0.80
    patch(mesh, bvh, 'trim', (z0, z1), (y - 0.017, y + 0.017), 'x', side=1, nu=3, nv=1, lift=0.0015, uv=False)
    h = K.hit(bvh, (1.4, y, (z0 + z1) / 2), (-1, 0, 0))
    if h:
        x = h[0].x
        mesh.box('trim', x, x + 0.012, y - 0.006, y + 0.012, z0 + 0.008, z1 - 0.008, bevel=0.003, segments=1)


def mirror(mesh):
    """door mirror at the window's front lower corner: a black housing on a short arm, glass facing back"""
    # base on the door (triangle sail), arm, housing
    tri = [(0.935, 0.66), (0.935, 0.50), (1.035, 0.60)]
    outer = [(0.752 - 0.007 * (y - 0.935) / 0.1, y, z) for y, z in tri]
    inner = [(0.722, y, z) for y, z in tri]
    mesh.face(outer, 'trim', out=(1, 0, 0))
    mesh.face(inner, 'trim', out=(-1, 0, 0))
    for k in range(3):
        a, b = k, (k + 1) % 3
        mid = Vector(((tri[a][0] + tri[b][0]) / 2 - 0.98, 0, (tri[a][1] + tri[b][1]) / 2 - 0.59))
        mesh.face([outer[a], outer[b], inner[b], inner[a]], 'trim', out=(0, mid.x, mid.z), smooth=False)
    mesh.box('trim', 0.752, 0.80, 0.955, 0.985, 0.545, 0.585, bevel=0.006, segments=1)
    cx, cy, cz = 0.865, 1.00, 0.565
    w, h, d = 0.150, 0.092, 0.075
    m = K.Mesh('mirror')
    m.box('trim', cx - w / 2, cx + w / 2, cy - h / 2, cy + h / 2, cz - d / 2, cz + d / 2, bevel=0.022, segments=3)
    # the housing leans back at the outer end
    m.warp(lambda p: (p[0], p[1], p[2] - 0.12 * (p[0] - 0.79) * (1 if p[2] > cz else 0.4)))
    mesh.merge(m)
    gz = cz - d / 2 - 0.0015 - 0.12 * (0.0)
    q = []
    for (sx, sy) in ((1, -1), (-1, -1), (-1, 1), (1, 1)):
        x = cx + sx * (w / 2 - 0.012)
        y = cy + sy * (h / 2 - 0.012)
        q.append((x, y, gz - 0.12 * (x - 0.79) * 0.4))
    mesh.face(q, 'chrome', out=(0, 0, -1))


# ---------------------------------------------------------------- glasshouse trim


def window_trim(mesh, bvh):
    """black frames: door window sash and quarter window surround, windscreen and hatch rubbers, belt mouldings"""
    rows, kinds, cols = BD.greenhouse_grid()
    k_of = [c[0] for c in cols]

    def idx(k):
        return [i for i, c in enumerate(cols) if c[0] == k] + ([i for i, c in enumerate(cols) if c[0] == k + 1][:1])

    j_g1, j_g2 = kinds.index('g1'), kinds.index('g2')
    j_edge = kinds.index('edge')
    j_top = len(rows) - 1

    def strip(pts, w=0.022, lift=0.0018):
        K.lay_strip(mesh, bvh, pts, w, 'trim', lift=lift)
    # side glass top & front edge (A-pillar outer edge, door frame), knots 0..2
    seq = [i for i, c in enumerate(cols) if c[0] <= 1] + [i for i, c in enumerate(cols) if c[0] == 2][:1]
    pts = [rows[j_g2][i] for i in seq]
    strip([tuple(Vector(p) + Vector((-0.004, -0.008, 0))) for p in pts], 0.024)
    # quarter window: top edge and the rear corner, knots 3..4
    seq = [i for i, c in enumerate(cols) if c[0] == 3] + [i for i, c in enumerate(cols) if c[0] == 4][:1]
    pts = [rows[j_g2][i] for i in seq]
    strip([tuple(Vector(p) + Vector((-0.004, -0.008, 0))) for p in pts], 0.024)
    i_c = [i for i, c in enumerate(cols) if c[0] == 4][0]
    strip([rows[j_g1][i_c], rows[j_g2][i_c]], 0.02)
    # belt mouldings: along g1 (door and quarter)
    seq = [i for i, c in enumerate(cols) if c[0] <= 4]
    strip([rows[j_g1][i] for i in seq], 0.016)
    # windscreen surround: the A-pillar inner edge (knots 0..1), the header, the cowl line
    seq = [i for i, c in enumerate(cols) if c[0] == 0] + [i for i, c in enumerate(cols) if c[0] == 1][:1]
    strip([rows[j_edge][i] for i in seq], 0.022)
    i1 = seq[-1]
    strip([rows[j][i1] for j in range(j_edge, j_top + 1)], 0.022)
    strip([rows[j][0] for j in range(j_edge, j_top + 1)], 0.03)
    # hatch glass surround: the side edges, the top edge, the base
    seq = [i for i, c in enumerate(cols) if c[0] == 4] + [len(cols) - 1]
    strip([rows[j_edge + 1][i] for i in seq], 0.026)
    ic = seq[0]
    strip([rows[j][ic] for j in range(j_edge + 1, j_top + 1)], 0.026)
    strip([rows[j][-1] for j in range(j_edge + 1, j_top + 1)], 0.03)
    return rows, kinds, cols


def cowl_and_wipers(mesh, bvh):
    """the black cowl panel in front of the windscreen, two wipers parked on it, two washer nozzles"""
    zc = BD.Z_COWL
    # cowl: a strip across the bonnet's rear edge
    path = [(x, BD.HULL('h10', zc + 0.03)[1], zc + 0.035) for x in [K.lerp(0.0, 0.70, k / 14) for k in range(15)]]
    K.lay_strip(mesh, bvh, path, 0.07, 'trim', lift=0.002)
    # wipers (left-hand parking: the driver's arm sweeps from the right): arm + blade along the glass base
    for px, length in ((0.30, 0.50), (-0.22, 0.46)):
        pivot = Vector((px, BD.HULL('h10', zc)[1] + 0.022, zc + 0.02))
        tip = Vector((px + length, pivot.y + 0.035, zc + 0.045))
        mesh.cylinder('trim', tuple(pivot), 0.012, 0.03, axis='y', segments=8)
        d = tip - pivot
        n = 10
        for k in range(n):
            a = pivot + d * (k / n)
            b = pivot + d * ((k + 1) / n)
            mesh.box('trim', min(a.x, b.x), max(a.x, b.x), a.y - 0.004, a.y + 0.006, a.z - 0.009, a.z + 0.009)
        # blade lies a little higher, along the glass
        b0 = pivot + d * 0.12 + Vector((0, 0.012, -0.012))
        b1 = tip + Vector((0.04, 0.018, -0.012))
        mesh.box('trim', min(b0.x, b1.x), max(b0.x, b1.x), b0.y, b0.y + 0.014, b0.z - 0.006, b0.z + 0.006)
    # washer nozzles on the bonnet
    for x in (0.26, -0.26):
        z = zc + 0.17
        y = BD.HULL('h9', z)[1] + 0.004
        mesh.box('trim', x - 0.012, x + 0.012, y - 0.004, y + 0.012, z - 0.012, z + 0.012, bevel=0.004, segments=1)


def exhaust(mesh):
    """single tailpipe under the rear bumper, left side (as on the photos of RHD cars); the mesh name has 'exhaust'"""
    x, y = 0.44, 0.255
    z0, z1 = BD.Z_RBUMP - 0.035, BD.Z_RBUMP + 0.35
    prof = [(z1, 0.022), (z0 + 0.03, 0.024), (z0, 0.0275), (z0 - 0.002, 0.024), (z0 + 0.04, 0.020)]
    m = K.Mesh('pipe')
    # lathe about x then turn onto z
    m.lathe([(a, r) for a, r in prof], 18, mats='chrome')
    m.warp(lambda p: (x + p[2], y + p[1], p[0]))
    mesh.merge(m)
    return (x, y, z0)
