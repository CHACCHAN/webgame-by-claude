"""The FD3S body's final shape correction, measured on photos: a free-form deformation (cubic uniform B-spline
lattices in game coordinates: x = left, y = up, z = forward) solved by the photo silhouette fit and stored in
fitdata/shiden/ffd.json. Applied to every mesh under the body empty (not the wheels), with the pop-up pods folded
shut so they keep matching their openings; each pod's hinge empty moves with the deformed hinge point.
SHIDEN_NOFFD=1 in the environment skips it (the fit's own undeformed base mesh)."""
import json
import os

import bpy
import numpy as np
from mathutils import Matrix, Vector

PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fitdata', 'shiden', 'ffd.json')


def _bspline_w(t):
    t2, t3 = t * t, t * t * t
    return np.stack([(1 - t) ** 3 / 6, (3 * t3 - 6 * t2 + 4) / 6, (-3 * t3 + 3 * t2 + 3 * t + 1) / 6, t3 / 6], -1)


def _lattice_apply(L, P):
    lo, hi, seg = np.array(L['lo'], float), np.array(L['hi'], float), np.array(L['seg'], int)
    n = seg + 3
    D = np.array(L['D'], float)
    u = np.clip((P - lo) / (hi - lo) * seg, 0, seg - 1e-9)
    b = np.floor(u).astype(int)
    t = u - b
    wx, wy, wz = _bspline_w(t[:, 0]), _bspline_w(t[:, 1]), _bspline_w(t[:, 2])
    I = b[:, 0, None] + np.arange(4)[None]
    J = b[:, 1, None] + np.arange(4)[None]
    K = b[:, 2, None] + np.arange(4)[None]
    idx = ((I[:, :, None, None] * n[1] + J[:, None, :, None]) * n[2] + K[:, None, None, :]).reshape(len(P), 64)
    w = (wx[:, :, None, None] * wy[:, None, :, None] * wz[:, None, None, :]).reshape(len(P), 64)
    w[~np.all((P >= lo) & (P <= hi), axis=1)] = 0.0
    return P + np.einsum('nk,nkc->nc', w, D[idx])


def _ends(op, P):
    """lengthen the overhangs to the official overall length (the photos cannot tell the length from the camera
    distance): beyond z0 (from the wheel centres outwards) a C1 ramp of width w, then a uniform stretch k"""
    P = P.copy()
    for z0, w, k in ((op['front'][0], op['front'][1], op['front'][2]), (-op['rear'][0], op['rear'][1], -op['rear'][2])):
        u = (P[:, 2] - z0) * np.sign(z0)
        u = np.maximum(u, 0.0)
        h = np.where(u < w, u * u / (2 * w), u - w / 2)
        P[:, 2] += k * h
    return P


def _ops(always):
    if (os.environ.get('SHIDEN_NOFFD') and not always) or not os.path.exists(PATH):
        return []
    with open(PATH) as f:
        j = json.load(f)
    return [('lattice', L) for L in j['lattices']] + [(o['op'], o) for o in j.get('post', [])]


def _deform(P, ops):
    for kind, o in ops:
        P = _lattice_apply(o, P) if kind == 'lattice' else _ends(o, P)
    return P


def lattices(always=False):
    """the stored lattices; none with SHIDEN_NOFFD unless always (parts placed in final coordinates use them to
    find their place on the undeformed body, so the fit's base mesh agrees with the build)"""
    if (os.environ.get('SHIDEN_NOFFD') and not always) or not os.path.exists(PATH):
        return []
    with open(PATH) as f:
        return json.load(f)['lattices']


def deform_game(P, always=True):
    return _deform(P, _ops(always))


def _to_game(co):
    return np.c_[co[:, 0], co[:, 2], -co[:, 1]]


def _to_blender(g):
    return np.c_[g[:, 0], -g[:, 2], g[:, 1]]


def apply(body):
    ops = _ops(False)
    if not ops:
        return

    def deform(P):
        return _deform(P, ops)

    pods = [o for o in body.children_recursive if o.type == 'EMPTY' and 'popupClosed' in o]
    opened = {o.name: o.rotation_euler[0] for o in pods}
    for o in pods:
        o.rotation_euler[0] = o['popupClosed']
    bpy.context.view_layer.update()
    meshes = [o for o in body.children_recursive if o.type == 'MESH']
    worlds = {}
    for o in meshes:
        if o.data.users > 1:
            o.data = o.data.copy()
        me = o.data
        co = np.empty(len(me.vertices) * 3)
        me.vertices.foreach_get('co', co)
        co = co.reshape(-1, 3)
        mw = np.array(o.matrix_world)
        worlds[o.name] = deform(_to_game(co @ mw[:3, :3].T + mw[:3, 3]))
    # hinges follow the deformed body
    for o in pods:
        h = np.array(o.matrix_world.translation)[None]
        o.matrix_world = Matrix.Translation(Vector(_to_blender(deform(_to_game(h)))[0])) @ \
            o.matrix_world.to_3x3().to_4x4()
    bpy.context.view_layer.update()
    for o in meshes:
        mi = np.array(o.matrix_world.inverted())
        W = _to_blender(worlds[o.name])
        loc = W @ mi[:3, :3].T + mi[:3, 3]
        o.data.vertices.foreach_set('co', loc.reshape(-1))
        o.data.update()
    for o in pods:
        o.rotation_euler[0] = opened[o.name]
    bpy.context.view_layer.update()
