"""
What the AE86 model lacked against the photos (r03, r08, n06), added 2026-11: the rear wiper, the lamps beside the
rear plate, tow eyes, the sill's step, mud flaps behind the rear wheels, the roof antenna. Laid on the body's skin
(rays), so they move with the fitted field like the rest of the details.
"""
import math

from mathutils import Vector

import hayate_kit as K
import hayate_body as BD
import car_common as CC


def _down(bvh, x, z, lift=0.0):
    """the point of the skin under (x, z), lifted along its normal"""
    h = K.hit(bvh, (x, 2.0, z), (0, -1, 0))
    if h is None:
        return None
    p, n = h
    if n.y < 0:
        n = -n
    return p + n * lift, n


def sym(mesh, bvh):
    """left side parts (mirrored with the other details)"""
    # the sill's step between the wheels: a black moulding 3 cm proud of the body side (r03)
    mesh.box('accent', 0.768, 0.824, 0.166, 0.232, BD.ZR + 0.41, BD.ZF - 0.41, bevel=0.014, segments=2)
    # mud flap behind the rear wheel (r08): a rubber sheet hanging from the arch's rear edge
    z = BD.ZR - BD.ARCH_R - 0.035
    mesh.box('u_rubber', 0.615, 0.805, 0.150, 0.365, z - 0.005, z + 0.005, bevel=0.003, segments=1)
    # tow eye under the rear valance (r08: one a side) and under the nose
    for x, zz, y in ((0.31, BD.Z_RBUMP + 0.085, 0.262), (0.33, BD.Z_NOSE - 0.14, 0.262)):
        loop = [(x - 0.022, y + 0.03, zz), (x - 0.022, y - 0.022, zz), (x - 0.012, y - 0.036, zz), (x + 0.012, y - 0.036, zz),
                (x + 0.022, y - 0.022, zz), (x + 0.022, y + 0.03, zz)]
        CC.tube(mesh, 'u_black', loop, 0.0055, seg=6)
    # the lamp housing beside the rear plate (r08: a black block each side, lighting the plate)
    h = K.hit(bvh, (0.212, 0.594, -3.0), (0, 0, 1))
    if h is not None:
        zf = h[0].z
        mesh.box('trim', 0.186, 0.238, 0.556, 0.632, zf - 0.030, zf + 0.012, bevel=0.006, segments=1)
        # its clear window, towards the plate (a swatch of its own: `reverse` is the tail lamps' lens for the gate)
        mesh.box('lamp_window', 0.181, 0.187, 0.570, 0.618, zf - 0.024, zf + 0.004)


def asym(mesh, bvh):
    """parts on one side or on the centre line"""
    # ---- the rear wiper, parked along the hatch glass's lower edge (r08): pivot left of centre, blade to the right
    zw = BD.Z_GBOT + 0.075
    piv = _down(bvh, 0.16, zw - 0.035, 0.0)
    if piv is not None:
        p, n = piv
        mesh.cylinder('trim', tuple(p + n * 0.008), 0.016, 0.018, axis='y', segments=10)
        arm = [p + n * 0.016]
        for x in (0.10, 0.0, -0.10):
            q = _down(bvh, x, zw, 0.020 if x > -0.05 else 0.014)
            if q is not None:
                arm.append(q[0])
        CC.tube(mesh, 'trim', [tuple(a) for a in arm], [0.006, 0.005, 0.004, 0.0035][:len(arm)], seg=5)
        blade = []
        for k in range(9):
            q = _down(bvh, K.lerp(0.13, -0.33, k / 8), zw, 0.008)
            if q is not None:
                blade.append(tuple(q[0]))
        if len(blade) > 2:
            CC.tube(mesh, 'trim', blade, 0.0045, seg=4)
    # ---- the aerial's foot at the roof's rear edge (r08): a black stub two fingers high, no rod (the gate, 11-13:
    # the 13 cm rod of the first pass stood out of every outline, and r08 shows only the stub)
    a = _down(bvh, 0.0, BD.Z_CTOP + 0.045, 0.0)
    if a is not None:
        p, n = a
        mesh.cylinder('trim', tuple(p + Vector((0, 0.006, 0))), 0.012, 0.012, axis='y', segments=8, radius2=0.008)
        mesh.cylinder('trim', tuple(p + Vector((0, 0.019, -0.003))), 0.006, 0.016, axis='y', segments=8, radius2=0.005)
