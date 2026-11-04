"""
The FD3S body shell: the spline surface through shiden_shape's key grid, mirrored and welded, then split along
outlines: the wheel arches and the intake / plate openings are cut out, the glass gets its own faces, the
pop-up lids are lifted out (they go to the pods), and panel shut lines are laid on as thin dark ribbons.
"""
import math

import bmesh
import numpy as np

import shiden_shape as SH
from shiden_surf import B, G, Mesh, Shell, surface, smooth_outline, ribbon, resample, lay_on, patch

ARCH_R = (0.352, 0.356)     # front, rear wheel arch radius (the tyre is 0.31)


def dense_half():
    K = SH.key_grid()
    return surface(K, SH.steps_along(len(K)), SH.STEPS_ACROSS, ends_j=('line', 'line'),
                   ends_k=('mirror_x', 'mirror_x'))


def full_rings(P):
    """half grid (stations × M) → full rings (2M−2 × stations), left side bottom → top, then the right side down"""
    left = P                                      # x ≥ 0
    right = P[:, -2:0:-1].copy()
    right[..., 0] *= -1
    ring = np.concatenate([left, right], axis=1)  # stations × (2M − 2)
    return np.transpose(ring, (1, 0, 2))


def arch_outline(zc, r, side):
    pts = []
    for i in range(0, 41):
        a = math.pi * i / 40
        pts.append((zc + r * math.cos(a), SH.TYRE_R + r * math.sin(a)))
    pts += [(zc - r, -0.2), (zc + r, -0.2)]
    return pts


def _smooth(a, b, t):
    t = min(1.0, max(0.0, (t - a) / (b - a)))
    return t * t * (3 - 2 * t)


BONNET_C = SH.table({'c': [(0.50, 0.81), (0.65, 0.793), (1.0, 0.742), (1.4, 0.692), (1.7, 0.640), (1.9, 0.600),
                          (2.1, 0.565)]})['c']
BONNET_CROWN = 0.06          # y drops k·x² across the bonnet (1.2 cm at the lids' inner edge)


def nose_edge_z(x):
    """the bonnet's front edge (crease above the plate) in plan"""
    return 1.955 - 0.17 * (x / 0.47) ** 2


def bonnet_y(x, z):
    """the bonnet as one fair height field between the wing peaks: a gently crowned sheet falling to the nose,
    rising at its sides into the crests (r6) with a horizontal tangent there"""
    xp, crest = SH.X['r6'](z), SH.Y['r6'](z)
    base = lambda xx: BONNET_C(z) - BONNET_CROWN * xx * xx
    t = abs(x) / xp
    return base(x) + (crest - base(xp)) * _smooth(0.55, 1.0, t)


def bonnet(bm):
    """replace the shell's top between the wing crests, from the cowl to the nose edge, by bonnet_y (no ripple), and
    roll the nose down ahead of the edge so the crease above the plate is crisp"""
    bm.normal_update()
    for v in bm.verts:
        x, y, z = v.co.x, v.co.z, -v.co.y
        if z < 0.45 or y < 0.45:
            continue
        ax = abs(x)
        xp = SH.X['r6'](min(z, 1.95))
        if ax > xp:
            continue
        z0 = 0.62 - 0.153 * (min(ax, 0.688) / 0.688) ** 2
        wz = _smooth(z0, z0 + 0.10, z)
        if wz <= 0:
            continue
        ze = nose_edge_z(min(ax, 0.47))
        side = _smooth(0.42, 0.52, ax)
        if z <= ze or (side > 0 and z <= 1.80):
            w = wz * (1 - side * _smooth(1.72, 1.80, z))
            yf = bonnet_y(x, z)
            v.co.z = y + (yf - y) * w
        elif side < 1 and v.normal.z > 0.35:
            ye = bonnet_y(x, ze)
            ramp = ye - 0.9 * (z - ze)
            if ramp < y:
                v.co.z = y + (ramp - y) * (1 - side)


def build_shell(mats):
    P = dense_half()
    R = full_rings(P)
    mesh = Mesh('body_shell')
    mesh.grid(R, 'paint', closed_u=True)
    bm = mesh.bm
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    # make sure they point out: the roof's faces look up
    top = max(bm.faces, key=lambda f: f.calc_center_median().z)
    if top.normal.z < 0:
        for f in bm.faces:
            f.normal_flip()
    bonnet(bm)
    bm.normal_update()
    return mesh


# ---------------------------------------------------------------- outlines (game frame; see shiden_shape for the figures)


def windscreen_outline(inset=0.0):
    """plan (x, z): cowl at the bottom, header at the top, the A-pillars between (bundle: corners (0.688, z 0.407)
    and (0.534, z −0.02))"""
    pts = []
    xb, xt = 0.688 - inset * 1.2, 0.534 - inset
    for i in range(13):
        x = -xb + 2 * xb * i / 12
        pts.append((x, 0.56 - inset - 0.153 * (x / 0.688) ** 2))
    for i in range(13):
        x = xt - 2 * xt * i / 12
        pts.append((x, -0.02 + inset + 0.045 * (1 - (x / 0.534) ** 2)))
    return pts


def side_window_outline(inset=0.0):
    """side view (z, y): the door glass and the fixed quarter, one D-shaped opening"""
    ctrl = [(0.385, 0.832), (0.25, 0.94), (0.10, 1.05), (-0.02, 1.115), (-0.25, 1.135), (-0.5, 1.125), (-0.70, 1.10),
            (-0.80, 1.075), (-0.84, 1.025), (-0.835, 0.93), (-0.818, 0.856), (-0.5, 0.846), (0.0, 0.838), (0.3, 0.832)]
    pts = smooth_outline(ctrl, 6)
    if inset:
        c = np.mean(np.array(pts), axis=0)
        out = []
        for p in pts:
            d = np.array(p) - c
            n = np.linalg.norm(d)
            out.append(tuple(np.array(p) - d / n * inset))
        return out
    return pts


def hatch_outline(inset=0.0):
    """plan (x, z): the rear glass, wrapping down the sides"""
    ctrl = [(0.0, -0.872), (0.25, -0.878), (0.42, -0.905), (0.515, -0.975), (0.55, -1.10), (0.555, -1.30),
            (0.535, -1.47), (0.465, -1.585), (0.25, -1.632), (0.0, -1.638), (-0.25, -1.632), (-0.465, -1.585),
            (-0.535, -1.47), (-0.555, -1.30), (-0.55, -1.10), (-0.515, -0.975), (-0.42, -0.905), (-0.25, -0.878)]
    pts = smooth_outline(ctrl, 5)
    if inset:
        c = np.array([0.0, -1.25])
        return [tuple(np.array(p) - (np.array(p) - c) / np.linalg.norm(np.array(p) - c) * inset) for p in pts]
    return pts


def intake_outline():
    half = SH.INTAKE
    return [(x, y) for x, y in half] + [(-x, y) for x, y in reversed(half[1:-1])]


def plate_recess_outline():
    half = SH.REAR_RING
    return [(x, y) for x, y in half] + [(-x, y) for x, y in reversed(half[1:-1])]


def arch_liner(mesh, shell, zc, r, side, depth_x=0.40):
    """the wheelhouse: a strip from the arch's edge inwards, and a wall closing it"""
    path = []
    fy = 0.12
    for i in range(6):
        path.append((zc + r, fy + (SH.TYRE_R - fy) * i / 5))
    for i in range(1, 40):
        a = math.pi * i / 40
        path.append((zc + r * math.cos(a), SH.TYRE_R + r * math.sin(a)))
    for i in range(6):
        path.append((zc - r, SH.TYRE_R - (SH.TYRE_R - fy) * i / 5))
    rim = []
    for z, y in path:
        h = shell.hit((side * 3.0, y, z), (-side, 0, 0))
        x = h[0][0] if h is not None and abs(h[0][0]) > 0.5 else side * 0.84
        rim.append((x, y, z))
    inner = [(side * depth_x, y, z) for z, y in path]
    centre = (zc, SH.TYRE_R)
    for i in range(len(path) - 1):
        q = [rim[i], rim[i + 1], inner[i + 1], inner[i]]
        cz = (path[i][0] + path[i + 1][0]) / 2 - centre[0]
        cy = (path[i][1] + path[i + 1][1]) / 2 - centre[1]
        mesh.face(q, 'trim', out=(0, -cy, -cz))
    # the inner wall
    for i in range(len(path) - 1):
        mesh.face([inner[i], inner[i + 1], (side * depth_x, fy, zc)], 'trim', out=(side, 0, 0))


def band(mesh, shell, outer, inner, axis, side, mat='trim'):
    """a strip between two outlines of equal point count, laid on the shell (the black edge round a pane)"""
    a = lay_on(shell, outer, axis, side, 0.002)
    b = lay_on(shell, inner, axis, side, 0.003)
    n = len(a)
    d = [0.0, 0.0, 0.0]
    d[{'x': 0, 'y': 1, 'z': 2}[axis]] = side
    for k in range(n):
        k2 = (k + 1) % n
        q = [a[k], a[k2], b[k2], b[k]]
        if any(p is None for p in q):
            continue
        mesh.face([tuple(p) for p in q], mat, out=tuple(d))


def build(body, mats, counts, cuts=None):
    mesh = build_shell(mats)
    shell = Shell(mesh)
    # wheel arches
    for zc, r in ((SH.ZF, ARCH_R[0]), (SH.ZR, ARCH_R[1])):
        for side in (1, -1):
            shell.split(arch_outline(zc, r, side), 'x', side,
                        lambda f, c, n, s=side: c[0] * s > 0.45, delete=True)
    # openings: the main intake, the rear plate recess
    shell.split(intake_outline(), 'z', 1, lambda f, c, n: c[2] > 1.8 and n[2] > 0.2, delete=True)
    shell.split(plate_recess_outline(), 'z', -1, lambda f, c, n: c[2] < -1.9 and n[2] < -0.2, mat='trim')
    # glass: the shell is opened under each pane; the pane is laid on the untrimmed surface with a black band
    # (frit / seal) round it that hides the opening's ragged edge
    ws = lambda f, c, n: c[1] > 0.75 and -0.15 < c[2] < 0.7 and n[1] > 0.0
    panes = [(windscreen_outline, (0.0, 0.010, 0.022), 'y', 1, ws)]
    for side in (1, -1):
        sw = lambda f, c, n, s=side: c[0] * s > 0.35 and c[1] > 0.78 and -0.95 < c[2] < 0.5 and n[0] * s > 0.05
        panes.append((side_window_outline, (0.0, 0.009, 0.018), 'x', side, sw))
    hw = lambda f, c, n: c[1] > 0.8 and c[2] < -0.55 and n[1] > -0.2
    panes.append((hatch_outline, (0.0, 0.02, 0.04), 'y', 1, hw))
    glass = Mesh('glass')
    for fn, (i0, i1, i2), axis, side, sel in panes:
        shell.split(fn(i1) if i1 else fn(), axis, side, sel, delete=True)
        band(glass, shell, fn(i0) if i0 else fn(), fn(i2), axis, side)
        patch(glass, shell, fn(i2), axis, side, 'glass', lift=0.0035, rings=6)
    if cuts is not None:
        cuts(shell)
    for zc, r in ((SH.ZF, ARCH_R[0]), (SH.ZR, ARCH_R[1])):
        for side in (1, -1):
            arch_liner(mesh, shell, zc, r, side)
    counts['body'] = mesh.tris()
    mesh.build(body, mats, weld=1e-6)
    counts['glass'] = glass.tris()
    glass.build(body, mats, weld=1e-6)
    return shell
