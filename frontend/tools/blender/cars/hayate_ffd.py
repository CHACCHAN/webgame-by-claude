"""
A smooth free-form deformation (FFD) of the AE86's body, fitted to the reference photos' silhouettes
(tools/carfit + fitdata/hayate/ffd.json). The body is built from measured rows and sections first (hayate_body); this
field then moves every body vertex by a cubic B-spline displacement in the game frame, mirror-symmetric about x = 0,
so the details laid on the body (lamps, trim, glass) move with it and the surfaces stay smooth.

ffd.json: {"lo": [x, y, z], "hi": [x, y, z], "seg": [sx, sy, sz], "c": [[[dx, dy, dz] per control point]]}
(control points (sx + 3) x (sy + 3) x (sz + 3), index order x, y, z; only the half x >= 0 is free, the rest mirrors).
"""
import json
import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT = os.path.join(HERE, 'fitdata', 'hayate', 'ffd.json')


def _basis(t):
    """uniform cubic B-spline weights for local parameter t in [0, 1) (rows: points, cols: 4)"""
    t = np.asarray(t, float)
    t2, t3 = t * t, t * t * t
    return np.stack([(1 - t) ** 3, 3 * t3 - 6 * t2 + 4, -3 * t3 + 3 * t2 + 3 * t + 1, t3], -1) / 6.0


class Lattice:
    def __init__(self, lo=(-1.0, -0.1, -2.4), hi=(1.0, 1.5, 2.3), seg=(4, 4, 12)):
        self.lo = np.array(lo, float)
        self.hi = np.array(hi, float)
        self.seg = np.array(seg, int)
        self.n = self.seg + 3
        self.h = (self.hi - self.lo) / self.seg
        self.c = np.zeros((*self.n, 3))

    @classmethod
    def load(cls, path=DEFAULT):
        if not os.path.exists(path):
            return None
        d = json.load(open(path))
        L = cls(d['lo'], d['hi'], d['seg'])
        L.c = np.array(d['c'], float).reshape(*L.n, 3)
        return L

    def save(self, path):
        json.dump({'lo': self.lo.tolist(), 'hi': self.hi.tolist(), 'seg': self.seg.tolist(),
                   'c': np.round(self.c, 5).tolist()}, open(path, 'w'))

    def weights(self, P):
        """for points P (N, 3): control indices (N, 64) into the flat lattice and their weights (N, 64)"""
        P = np.asarray(P, float)
        u = (np.clip(P, self.lo, self.hi - 1e-9) - self.lo) / self.h
        i0 = np.floor(u).astype(int)
        t = u - i0
        bx, by, bz = _basis(t[:, 0]), _basis(t[:, 1]), _basis(t[:, 2])
        ii = i0[:, 0, None] + np.arange(4)[None]
        jj = i0[:, 1, None] + np.arange(4)[None]
        kk = i0[:, 2, None] + np.arange(4)[None]
        idx = (ii[:, :, None, None] * self.n[1] + jj[:, None, :, None]) * self.n[2] + kk[:, None, None, :]
        w = bx[:, :, None, None] * by[:, None, :, None] * bz[:, None, None, :]
        return idx.reshape(len(P), 64), w.reshape(len(P), 64)

    def displace(self, P):
        idx, w = self.weights(P)
        C = self.c.reshape(-1, 3)
        return (C[idx] * w[:, :, None]).sum(1)

    def symmetrize(self):
        """mirror the x >= 0 half onto x < 0 (x component negated); the centre column has dx = 0"""
        nx = self.n[0]
        for i in range(nx // 2):
            j = nx - 1 - i
            self.c[i] = self.c[j] * np.array([-1, 1, 1])
        if nx % 2:
            self.c[nx // 2, :, :, 0] = 0.0


def apply_to_objects(objs, lattice, frame_to_game, game_to_frame):
    """deform mesh objects in place: world vertex -> game frame -> + displacement -> back"""
    import bpy  # noqa: F401
    for o in objs:
        me = o.data
        n = len(me.vertices)
        if n == 0:
            continue
        co = np.empty(n * 3)
        me.vertices.foreach_get('co', co)
        co = co.reshape(n, 3)
        M = np.array(o.matrix_world)
        W = co @ M[:3, :3].T + M[:3, 3]
        G = frame_to_game(W)
        G2 = G + lattice.displace(G)
        W2 = game_to_frame(G2)
        Mi = np.linalg.inv(M)
        loc = W2 @ Mi[:3, :3].T + Mi[:3, 3]
        me.vertices.foreach_set('co', loc.ravel())
        me.update()


def apply_to_body(body, hinges, lattice=None):
    """the fitted field (fitdata/hayate/ffd.json unless a Lattice is given) on the body; None when there is none"""
    L = lattice if lattice is not None else Lattice.load()
    if L is None:
        return None
    deform_body(body, hinges, L.displace)
    return L


def _world_game(o):
    me = o.data
    co = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get('co', co)
    M = np.array(o.matrix_world)
    return blender_to_game(co.reshape(-1, 3) @ M[:3, :3].T + M[:3, 3])


def _set_world_game(o, G):
    Mi = np.linalg.inv(np.array(o.matrix_world))
    W = game_to_blender(G)
    o.data.vertices.foreach_set('co', (W @ Mi[:3, :3].T + Mi[:3, 3]).ravel())
    o.data.update()


def deform_body(body, hinges, disp):
    """move every mesh vertex under `body` by disp(G) (game frame, (N, 3) -> (N, 3)). The pop-up pods are deformed
    in their folded pose, so they stay flush with the bonnet, and their hinges move with the field."""
    import bpy
    from mathutils import Vector
    rot = {h.name: h.rotation_euler.x for h in hinges}
    for h in hinges:
        h.rotation_euler.x = float(h['popupClosed'])
    bpy.context.view_layer.update()
    pods = [o for h in hinges for o in h.children_recursive if o.type == 'MESH']
    others = [o for o in body.children_recursive if o.type == 'MESH' and o not in pods]
    folded = {o.name: _world_game(o) for o in pods}
    for o in others:
        if len(o.data.vertices):
            G = _world_game(o)
            _set_world_game(o, G + disp(G))
    for h in hinges:
        g = blender_to_game(np.array([h.matrix_world.translation]))
        h.location = h.location + Vector(game_to_blender(disp(g))[0])
    bpy.context.view_layer.update()
    for o in pods:
        G = folded[o.name]
        _set_world_game(o, G + disp(G))
    for h in hinges:
        h.rotation_euler.x = rot[h.name]
    bpy.context.view_layer.update()


def blender_to_game(W):
    return np.stack([W[:, 0], W[:, 2], -W[:, 1]], 1)


def game_to_blender(G):
    return np.stack([G[:, 0], -G[:, 2], G[:, 1]], 1)
