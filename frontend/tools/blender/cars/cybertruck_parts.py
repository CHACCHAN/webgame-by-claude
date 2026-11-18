"""
The Cybertruck's pieces besides the stainless shell: lamps (front light bar lenses, low/high beam strips, tail light
bar), door mirrors, the single wiper, side markers, the T badge and a simple cabin (seen through the glass). Game frame
(cybertruck_shape); every piece is built for the left side and mirrored where the truck has two.
"""
import math

import cybertruck_shape as CS


def faces_to_part(part, faces, smooth=False, uv_for=None):
    """uv_for: {material: (u, v)}, one texture spot for every face of that material without its own UVs"""
    for f in faces:
        uvs = getattr(f, 'uvs', None)
        if not uvs and uv_for and f.mat in uv_for:
            uvs = [uv_for[f.mat]] * len(f.pts)
        part.face(f.pts, f.mat, smooth=smooth, uvs=uvs)


def mirrored(faces):
    res = []
    for f in faces:
        g = CS.Face([CS.mirror(p) for p in reversed(f.pts)], f.tag, f.mat)
        if getattr(f, 'uvs', None):
            g.uvs = list(reversed(f.uvs))
        res.append(g)
    return res


def convex(planes, mat):
    fs = CS.solid(planes)
    for f in fs:
        f.mat = mat
    return fs


def _meet(a, b, c):
    """the point on three planes (n, d)"""
    (n1, d1), (n2, d2), (n3, d3) = a, b, c
    det = CS.dot(n1, CS.cross(n2, n3))
    v = CS.add(CS.add(CS.mul(CS.cross(n2, n3), d1), CS.mul(CS.cross(n3, n1), d2)), CS.mul(CS.cross(n1, n2), d3))
    return CS.mul(v, 1.0 / det)


def lamp_outlines(P, S):
    """every lamp's outline in the game frame, as ordered polygons (the same vertex order as the tracings in
    fitdata/cybertruck/lamps.json): the front light bar (the chamfer between hood and face), the headlamp slits under
    the face, the tail light band, the lit corner blocks and the centre line of the tail light bar"""
    m = CS.mirror
    o = {}
    # front light bar: ends on the sides, kinks where the centre chamfer meets the corner chamfers
    Et = _meet(S.bar_k, S.hood, S.side)
    Kt = _meet(S.bar_k, S.bar_c, S.hood)
    Eb = _meet(S.bar_k, S.corner, S.side)
    Kb = _meet(S.bar_k, S.bar_c, S.front)
    o['bar'] = [Et, Kt, m(Kt), m(Et), m(Eb), m(Kb), Kb, Eb]
    # headlamp slits: just under the stainless face's lower edge, near the kinks
    zf = lambda y: (S.front[1] - S.front[0][1] * y) / S.front[0][2]
    y1 = P['y_ff'] - P['hl_gap']
    y0 = y1 - P['hl_h']
    xo, xi = P['hl_x1'], P['hl_x0']
    q = [(xo, y1, zf(y1)), (xi, y1, zf(y1)), (xi, y0, zf(y0)), (xo, y0, zf(y0))]
    o['hl_l'] = q
    o['hl_r'] = [m(p) for p in q]
    # tail: the black band across the tailgate's top, the lit corner blocks, the thin centre line
    T, tl = S.T, S.tg_tl
    zt = lambda y: T[2] + (T[1] - y) * tl          # on the tailgate plane (its foot leans forward)
    yt, yb = T[1], P['y_lb']
    sw = S.sw
    o['band'] = [(sw, yt, zt(yt)), (-sw, yt, zt(yt)), (-sw, yb, zt(yb)), (sw, yb, zt(yb))]
    x0 = sw - P['tl_kx']
    x1 = x0 - P['tl_kw']
    ya = yt - P['tl_kt']
    yc = ya - P['tl_kh']
    q = [(x0, ya, zt(ya)), (x1, ya, zt(ya)), (x1, yc, zt(yc)), (x0, yc, zt(yc))]
    o['tl_l'] = q
    o['tl_r'] = [m(p) for p in q]
    ym = yt - P['tl_cy']
    h = P['tl_ch'] / 2
    c = P['tl_cw']
    o['tl_c'] = [(c, ym + h, zt(ym + h)), (-c, ym + h, zt(ym + h)), (-c, ym - h, zt(ym - h)), (c, ym - h, zt(ym - h))]
    xl = sw - P['tk_w']
    o['tl_line'] = [(xl, ym + h, zt(ym + h)), (-xl, ym + h, zt(ym + h)), (-xl, ym - h, zt(ym - h)), (xl, ym - h, zt(ym - h))]
    return o


def _lens(pts, normal_sign_axis, sign, out, mat, uvs):
    """a lens face over the outline, standing `out` along the axis off the surface, facing outwards"""
    ax = normal_sign_axis
    q = [tuple(p[i] + (out * sign if i == ax else 0.0) for i in range(3)) for p in pts]
    f = CS.Face(q, 'lamp', mat)
    if f.normal()[ax] * sign < 0:
        f.pts.reverse()
        uvs = list(reversed(uvs))
    f.uvs = uvs
    return f


# texture layout (cybertruck_textures.py): headlight.png u < 0.5 the light bar, u > 0.5 a headlamp slit's cells;
# taillight.png u < 0.5 the light bar line (lit centre, dimmer outer parts), u > 0.5 a corner block
def lamps(P, S, lamp_spec=None):
    """lamp lenses (both sides): headlamp slits, the tail light line and corner blocks, side markers"""
    o = lamp_outlines(P, S)
    res = []
    for k in ('hl_l', 'hl_r'):
        q = o[k]
        u = [(1.0, 1.0), (0.5, 1.0), (0.5, 0.0), (1.0, 0.0)] if k == 'hl_l' else [(0.5, 1.0), (1.0, 1.0), (1.0, 0.0), (0.5, 0.0)]
        res.append(_lens(q, 2, 1, 0.003, 'headlight', u))
    q = o['tl_line']
    res.append(_lens(q, 2, -1, 0.003, 'taillight', [(0.0, 1.0), (0.5, 1.0), (0.5, 0.0), (0.0, 0.0)]))
    for k in ('tl_l', 'tl_r'):
        q = o[k]
        u = [(1.0, 1.0), (0.5, 1.0), (0.5, 0.0), (1.0, 0.0)]
        res.append(_lens(q, 2, -1, 0.004, 'taillight', u))
    # side markers: amber at the front bumper's side, red reflectors at the rear bumper's side (not lamp material: the
    # game takes the tail lamps' position from the taillight faces)
    def marker(z0, z1, y0, y1, x, mat):
        f = CS.Face([(x, y0, z0), (x, y0, z1), (x, y1, z1), (x, y1, z0)], 'marker', mat)
        if f.normal()[0] < 0:
            f.pts.reverse()
        f.uvs = [(0.75, 0.5)] * 4
        return [f]
    mk = marker(P['fb_z'] - 0.20, P['fb_z'] - 0.12, P['fb_top'] - 0.035, P['fb_top'] - 0.012, P['fb_side'] + 0.003, 'indicator')
    res += mk + mirrored(mk)
    # rear reflectors: on the side just under the stainless near the tail, and facing back on the black strip between
    # the tailgate's stainless and the bumper, near the corners (photos p150, p193)
    T, tl = S.T, S.tg_tl
    yr = P['y_tgb'] - 0.012
    mk = marker(T[2] + 0.20, T[2] + 0.31, yr - 0.018, yr, S.sw + 0.002, 'reflector')
    y0, y1 = 0.5 * (P['y_tgb'] + P['rb_top']) - 0.010, 0.5 * (P['y_tgb'] + P['rb_top']) + 0.010
    zt = lambda y: T[2] + (T[1] - y) * tl - 0.003
    f = CS.Face([(S.sw - 0.04, y0, zt(y0)), (S.sw - 0.16, y0, zt(y0)), (S.sw - 0.16, y1, zt(y1)), (S.sw - 0.04, y1, zt(y1))], 'marker', 'reflector')
    if f.normal()[2] > 0:
        f.pts.reverse()
    f.uvs = [(0.75, 0.5)] * 4
    mk.append(f)
    res += mk + mirrored(mk)
    return res


def seams(P, S, w=0.006):
    """the doors' shut lines: dark strips on the side from the beltline down over the lower facet to the door bottom
    (front door front edge, B pillar, rear door rear edge), left side"""
    res = []
    tl = math.tan(math.radians(P['lower']))
    for z in (P['z_sa'], P['z_sb'], P['z_sc']):
        ylc, ytop = S.ylc(z), S.yb(z) - 0.004
        xo = S.sw + 0.0015
        for zz0, zz1 in ((z - w / 2, z + w / 2),):
            f = CS.Face([(xo, ylc, zz0), (xo, ylc, zz1), (xo, ytop, zz1), (xo, ytop, zz0)], 'seam', 'trim')
            if f.normal()[0] < 0:
                f.pts.reverse()
            res.append(f)
            xb = S.sw - (ylc - P['y_db']) * tl + 0.0015
            g = CS.Face([(xb, P['y_db'], zz0), (xb, P['y_db'], zz1), (xo, ylc, zz1), (xo, ylc, zz0)], 'seam', 'trim')
            if g.normal()[0] < 0:
                g.pts.reverse()
            res.append(g)
    return res


def bumper_details(part, P, S):
    """front: the lower grille (dark slats in a recess) and the tow-hook covers; rear: the hitch receiver"""
    zf = P['fb_z']
    y0, y1 = P['fb_low'] + 0.006, P['fb_low'] + 0.072
    part.box('under', -0.56, 0.56, y0, y1, zf - 0.01, zf + 0.003)
    n = 5
    for k in range(n):
        y = y0 + (k + 0.5) * (y1 - y0) / n
        part.box('trim', -0.55, 0.55, y - 0.004, y + 0.004, zf - 0.01, zf + 0.008)
    for sx in (-1, 1):
        part.box('trim', sx * 0.72 - 0.04, sx * 0.72 + 0.04, y1 + 0.02, y1 + 0.07, zf - 0.01, zf + 0.004, bevel=0.006)
    # the hitch receiver under the lower block, its mouth a little behind the block's face (not past the bumper)
    zr = P['rb_z'] + P['rb_lz'] - 0.03
    part.box('under', -0.05, 0.05, P['rb_bot'] - 0.02, P['rb_bot'] + 0.06, zr, zr + 0.35)
    part.box('trim', -0.035, 0.035, P['rb_bot'] - 0.005, P['rb_bot'] + 0.045, zr - 0.004, zr + 0.01)


def badge(P, S):
    """the small T in a triangle on the tail band's centre (our own simple drawing)"""
    T = S.T
    tl = S.tg_tl
    yc = 0.5 * (P['y_lb'] + T[1])
    z = lambda y: T[2] + (T[1] - y) * tl - 0.003
    s = 0.035
    tri = CS.Face([(-s, yc - s * 0.6, z(yc)), (s, yc - s * 0.6, z(yc)), (0.0, yc + s * 0.75, z(yc))], 'badge', 'rim')
    if tri.normal()[2] > 0:
        tri.pts.reverse()
    return [tri]


def mirror_unit(P, S):
    """door mirror: an angular housing on a short arm from the door's front corner (left)"""
    z0, z1 = P.get('mir_z0', 0.86), P.get('mir_z1', 1.12)
    y0, y1 = P.get('mir_y0', 1.205), P.get('mir_y1', 1.375)
    x0, x1 = S.sw + 0.03, P.get('mir_x', 1.235)
    pl = [('m_in', CS.plane((-1, 0, 0), (x0, 0, 0))), ('m_out', CS.plane((1, 0, 0), (x1, 0, 0))),
          ('m_bot', CS.plane((0, -1, 0), (0, y0, 0))), ('m_top', CS.plane((0, 1, 0), (0, y1, 0))),
          ('m_back', CS.plane((0, 0, -1), (0, 0, z0))),
          ('m_front', CS.plane3((0, y0, z1), (1, y0, z1), (0, y1, z1 - 0.10), (0, 0, 1))),
          ('m_tip', CS.plane3((x1 - 0.05, 0, z1), (x1, 0, z1 - 0.06), (x1, 1, z1 - 0.06), (1, 0, 1)))]
    housing = convex(pl, 'trim')
    # the glass faces backwards
    g = [CS.Face([(x0 + 0.015, y0 + 0.015, z0 - 0.002), (x1 - 0.015, y0 + 0.015, z0 - 0.002), (x1 - 0.015, y1 - 0.015, z0 - 0.002),
                  (x0 + 0.015, y1 - 0.015, z0 - 0.002)], 'mglass', 'chrome')]
    if g[0].normal()[2] > 0:
        g[0].pts.reverse()
    xa = S.sw - 0.04
    arm = convex([('a_in', CS.plane((-1, 0, 0), (xa, 0, 0))), ('a_out', CS.plane((1, 0, 0), (x0 + 0.01, 0, 0))),
                  ('a_bot', CS.plane((0, -1, 0), (0, y0 + 0.01, 0))), ('a_top', CS.plane((0, 1, 0), (0, y0 + 0.055, 0))),
                  ('a_back', CS.plane((0, 0, -1), (0, 0, z0 + 0.10))), ('a_front', CS.plane((0, 0, 1), (0, 0, z0 + 0.20)))], 'trim')
    return housing + g + arm


def wiper(P, S):
    """the single long wiper, parked along the left A-pillar"""
    f = CS.features(P, S)
    a, b = f['wsb'], f['peak']
    d = CS.unit(CS.sub(b, a))
    n = S.ws[0]
    inward = CS.unit(CS.cross(n, d))
    if inward[0] > 0:
        inward = CS.mul(inward, -1)
    p0 = CS.add(CS.add(a, CS.mul(inward, 0.10)), CS.mul(n, 0.025))
    p1 = CS.add(p0, CS.mul(d, 1.25))
    return p0, p1


def vault_ribs(part, P, S):
    """the vault cover's slats: low ribs across the cover from the cab to the tailgate"""
    T = S.T
    z0, z1 = P['z_rg'] + 0.05, T[2] + 0.06
    n = int((z0 - z1) / 0.07)
    for k in range(n + 1):
        z = z0 - k * (z0 - z1) / n
        a = S.up(z, S.v_roof(z))
        x = a[0] - P['rail'] - 0.01
        y = P['ypk'] + (z - P['zpk']) * S.tan_r
        part.box('vault', -x, x, y - 0.004, y + 0.004, z - 0.006, z + 0.006)


def underbody(part, P, S):
    """the floor pan that closes the body from below; what hangs under it (battery case, drive units, shafts, arms)
    comes from the shared kit (cybertruck.finish)"""
    part.box('under', -0.80, 0.80, P['y_rk'] - 0.02, P['y_rk'] + 0.06, -1.55, 1.55, bevel=0.03, segments=2)


def cabin(part, P, S):
    """the cabin's tub: floor, dash, console, the screen, the cab's back wall; what stands in it comes from the
    shared kit (furnish)"""
    m = 'interior'
    part.box('c_carpet', -0.92, 0.92, 0.50, 0.56, -1.05, 1.75)                     # floor
    part.box('c_dash', -0.90, 0.90, 0.80, 1.10, 1.05, 1.75)                        # dash
    part.box('c_dash', -0.90, 0.90, 1.08, 1.13, 0.98, 1.30, bevel=0.01)            # dash top
    part.box('c_plastic', -0.12, 0.12, 0.56, 0.95, 0.20, 1.05, bevel=0.02)         # console
    part.box('trim', -0.22, 0.22, 1.12, 1.36, 0.98, 1.02, bevel=0.005)             # screen
    part.box(m, -0.95, 0.95, 0.56, 1.30, -1.12, -1.08)                              # cab back wall


def furnish(mesh):
    """car_common's furniture (left-hand drive): two front seats with the head rest in one piece, the rear bench
    for three against the cab's back wall, the wheel, the mirror under the windscreen's top (the glass runs from
    1.242 up at z 1.854 to 1.77 up at z 0.303). No instruments' hood, lever or hand brake: the truck has none"""
    import car_common as CC
    for x in (-0.43, 0.43):
        CC.seat(mesh, x, 0.56, 0.05, width=0.54, length=0.56, h=0.30, back=0.60, recline=14.0, headrest='bucket',
                bolster=0.8, cloth='c_leather', insert='c_plastic')
    CC.bench(mesh, -0.80, 0.80, 0.56, -0.95, length=0.55, h=0.28, back=0.58, recline=10.0, places=3, headrests=True,
             cloth='c_leather', insert='c_plastic')
    CC.steering_wheel(mesh, (0.43, 1.13, 0.90), tilt=22.0, R=0.180, column=0.20)
    CC.inside_mirror(mesh, 1.58, 0.60)
