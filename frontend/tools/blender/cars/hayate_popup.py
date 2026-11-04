"""
The AE86's pop-up headlamps: each pod (painted lid, black box, the rectangular 200 x 142 mm lamp) is built in its
folded position from the hull's own lid faces, then swung up about its hinge; the empty `popup_l` / `popup_r` sits on
the hinge axis and folds the pod flush into the bonnet when turned by its `popupClosed` angle about local +X
(CarVisual.useModelPods). Under each lid a dark recess so the bonnet shows no hole with the lamps up.
"""
import math

from mathutils import Matrix, Vector

import hayate_kit as K
import hayate_body as BD

CLOSED = 0.64           # rad: folded → raised turns the lamp face from 37° down to vertical (measured: 0.64 on photos)
FACE_H = 0.165          # height of the pod's front face (lamp 142 mm + bezel)
LAMP_W, LAMP_H = 0.200, 0.142
TUB_FLOOR = 0.585


def _hinge(lid):
    """hinge line: just below the lid's rear edge (y, z)"""
    rear = [row[-1] for row in lid]              # i = last is the rear column (z = Z_LID)
    y = min(p[1] for p in rear) - 0.030
    z = BD.Z_LID - 0.004
    return y, z


def _rot(p, a, hy, hz):
    return K.rot_x(p, a, (0.0, hy, hz))


def build(side=1):
    """(pod Mesh in the raised position relative to the hinge, tub Mesh, hinge position) for the left side (+x)"""
    lid = BD.lid_grid()                          # rows j: h7 (outer) → h9 (inner); i: front (Z_NOSE) → rear (Z_LID)
    hy, hz = _hinge(lid)
    nj, ni = len(lid), len(lid[0])
    # face direction in the folded state: from the lid's front edge down and back, so it is vertical when raised
    fd = (0.0, -math.cos(CLOSED), -math.sin(CLOSED))
    pod = K.Mesh('pod')
    # the lid (paint): the hull's faces, outward
    pod.grid(lid, 'paint')
    lid_front = [lid[j][0] for j in range(nj)]   # outer → inner along the front edge
    # the lid overhangs the lamp face: a short painted lip turns down, the face starts set back under it
    # closed, the lid shows a black front edge ~3 cm deep (part of the dark band across the nose)
    front = [(p[0], p[1] - 0.030, p[2] - 0.026) for p in lid_front]
    lip = [(p[0], p[1] - 0.004, p[2] - 0.002) for p in lid_front]
    pod.grid([lid_front, lip], 'paint')
    pod.grid([lip, front], 'trim')
    rear = [lid[j][-1] for j in range(nj)]
    outer = [lid[0][i] for i in range(ni)]       # front → rear
    inner = [lid[-1][i] for i in range(ni)]
    # box points: the front face's bottom edge, and the bottom's rear edge under the hinge
    fbot = [(p[0], p[1] + fd[1] * FACE_H, p[2] + fd[2] * FACE_H) for p in front]
    rbot = [(p[0], hy - 0.075, hz + 0.020) for p in rear]
    # front face (black bezel) between the lid's front edge and fbot: faces forward-down (folded)
    pod.grid([front, fbot], 'trim')
    # bottom: fbot → rbot
    pod.grid([fbot, rbot], 'trim')
    # back: rbot → the lid's rear edge
    pod.grid([rbot, rear], 'trim')

    # sides: strips under the outer / inner lid edges down to the bottom line (front → rear)
    for edge, j_end, out in ((outer, 0, (1, 0, 0)), (inner, nj - 1, (-1, 0, 0))):
        # the side outline: lid edge front → rear, then the back and the bottom
        L = [edge[0]]
        for p in edge[1:]:
            L.append(p)
        # matching bottom line points
        fb, rb = fbot[j_end], rbot[j_end]
        n = len(L)
        B = [(L[i][0], K.lerp(fb[1], rb[1], i / (n - 1)), K.lerp(fb[2], rb[2], i / (n - 1))) for i in range(n)]
        for i in range(n - 1):
            pod.face([L[i], L[i + 1], B[i + 1], B[i]], 'trim', out=out, smooth=False)
    # the lamp: a rectangle on the front face, slightly proud, with its bezel ring
    cx = (front[0][0] + front[-1][0]) / 2 + 0.008
    mid_top = Vector(front[nj // 2])
    nface = Vector((0.0, -math.sin(CLOSED), math.cos(CLOSED)))      # folded face normal (forward-down)
    down = Vector(fd)
    c = Vector((cx, mid_top.y, mid_top.z)) + down * (FACE_H * 0.56) + nface * 0.004
    xa = Vector((1, 0, 0))
    r = 0.012

    def rect(w, h, lift):
        pts = []
        for (sx, sy, a0) in ((1, 1, 0), (-1, 1, 90), (-1, -1, 180), (1, -1, 270)):
            for k in range(4):
                a = math.radians(a0 + 90 * k / 3)
                ox = sx * (w / 2 - r) + r * math.cos(a)
                oy = sy * (h / 2 - r) + r * math.sin(a)
                pts.append(tuple(c + xa * ox - down * oy + nface * lift))
        return pts
    outer_r = rect(LAMP_W + 0.016, LAMP_H + 0.016, 0.0)
    lens_r = rect(LAMP_W, LAMP_H, 0.006)
    n = len(outer_r)
    for k in range(n):
        pod.face([outer_r[k], outer_r[(k + 1) % n], lens_r[(k + 1) % n], lens_r[k]], 'chrome', out=tuple(nface), smooth=False)
    # the lens with UVs across it (the reflector / lens pattern texture)
    uv = []
    for p in lens_r:
        d = Vector(p) - c
        uv.append((0.5 + d.dot(xa) / LAMP_W, 0.5 - d.dot(down) / LAMP_H))
    pod.face(lens_r, 'popup_lens', uvs=uv, out=tuple(nface))

    # raise it: rotate by −CLOSED about the hinge, then make it relative to the hinge empty
    hinge = (cx, hy, hz)
    pod.warp(lambda p: _rot(p, -CLOSED, hy, hz))
    pod.warp(lambda p: (p[0] - hinge[0], p[1] - hinge[1], p[2] - hinge[2]))

    # the recess under the lid (in the body): walls from the hole's outline down to a floor
    tub = K.Mesh('tub')
    walls = [(outer, (-1, 0, 0)), (inner, (1, 0, 0)), (rear, (0, 0, 1))]
    def face_z(p, y):
        """z of the folded lamp face below the lid's front point p, at height y (plus clearance)"""
        return p[2] - 0.032 - math.tan(CLOSED) * (p[1] - 0.012 - y) + 0.010

    for edge, out in walls:
        lo = [(p[0], TUB_FLOOR, min(p[2], face_z(lid_front[0 if edge is outer else -1], TUB_FLOOR))) if p[2] > BD.Z_LID + 1e-6 else (p[0], TUB_FLOOR, p[2])
              for p in edge]
        for i in range(len(edge) - 1):
            tub.face([edge[i], edge[i + 1], lo[i + 1], lo[i]], 'interior', out=out, smooth=False)
    # front wall: just ahead of the folded face, facing back into the recess
    fw_top = [(p[0], p[1] - 0.006, p[2] - 0.004) for p in front]
    fw_lo = [(p[0], TUB_FLOOR, p[2] + fd[2] * (p[1] - TUB_FLOOR) / max(1e-6, -fd[1]) + 0.012) for p in front]
    for i in range(nj - 1):
        tub.face([fw_top[i], fw_top[i + 1], fw_lo[i + 1], fw_lo[i]], 'interior', out=(0, 0.3, -1), smooth=False)
    # floor
    xs = sorted([outer[-1][0], inner[-1][0]])
    tub.face([(xs[0], TUB_FLOOR, BD.Z_LID), (xs[1], TUB_FLOOR, BD.Z_LID), (xs[1], TUB_FLOOR, BD.Z_NOSE - 0.02), (xs[0], TUB_FLOOR, BD.Z_NOSE - 0.02)],
             'interior', out=(0, 1, 0), smooth=False)
    return pod, tub, hinge
