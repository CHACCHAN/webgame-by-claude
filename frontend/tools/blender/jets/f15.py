"""
The F-15 of TOUGE NOCTURNE: one airframe, four aircraft (f15j, f15j-dj, f15c, f15c-d). Our own model: the shape is
f15_shape.py (stations measured on photos with solved cameras and checked against the published dimensions), the
surface one atlas painted by f15_paint.py (camouflage, panel lines, stencils, invented numbers; no unit's emblem).

  blender --background --factory-startup --python f15.py -- --id f15c [--variant d] --out f15c.glb
          [--stage shape] [--dump tris.npz] [--render dir] [--views a,b] [--size 2048]

Contract (render/JetModel.ts): node `body`; `gear_nose` (hinge) → `steer_nose` (the nose wheel turns with it);
`gear_l` / `gear_r` (hinge) → `spin_l` / `spin_r`; `nozzles` (both, one mesh); `stab` (both tailplanes on their
pivot). Materials: `airframe` (the atlas; its emissive map holds the steady lamps), `glass`, `beacon`, `taxilight`.
"""
import argparse
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import bmesh  # noqa: E402
import bpy  # noqa: E402
import numpy as np  # noqa: E402

import jet_kit as K  # noqa: E402
import f15_shape as S  # noqa: E402

AIRCRAFT = {
    'f15c': {'asym': True, 'scheme': 'c', 'variants': {'': 1, 'd': 2}},
    'f15j': {'asym': False, 'scheme': 'j', 'variants': {'': 1, 'dj': 2}},
}

# zones → preview colours (the shape stage's renders; the paint replaces them all by the atlas)
ZONES = {
    'fus': ('#8a949c', 0.0, 0.55), 'nac': ('#8a949c', 0.0, 0.55), 'deck': ('#8a949c', 0.0, 0.55), 'radome': ('#767f87', 0.0, 0.5), 'cowl': ('#8a949c', 0.0, 0.55), 'lip': ('#70787f', 0.0, 0.5),
    'duct': ('#d8dad8', 0.0, 0.6), 'ductend': ('#101214', 0.0, 0.8), 'wing': ('#8f989f', 0.0, 0.55), 'stab': ('#8f989f', 0.0, 0.55),
    'fin': ('#8a949c', 0.0, 0.55), 'metal': ('#7b7168', 0.8, 0.42), 'frame': ('#5d656c', 0.0, 0.5), 'tub': ('#3a3d40', 0.0, 0.8),
    'coaming': ('#17191b', 0.0, 0.85), 'panel': ('#222527', 0.0, 0.7), 'seat': ('#2c2f31', 0.0, 0.7), 'cushion': ('#4b5340', 0.0, 0.9),
    'handle': ('#d8b21c', 0.0, 0.6), 'suit': ('#59614a', 0.0, 0.9), 'harness': ('#8e8f86', 0.0, 0.8), 'glove': ('#3f4034', 0.0, 0.8),
    'helmet': ('#c9ccca', 0.0, 0.35), 'visor': ('#15171a', 0.3, 0.12), 'mask': ('#3a3d3a', 0.0, 0.7), 'steel': ('#9a9c9c', 0.9, 0.35),
    'nozzle': ('#5a5550', 0.85, 0.45), 'nozzle_in': ('#2a2826', 0.6, 0.6), 'strut': ('#e6e7e4', 0.0, 0.45), 'chrome': ('#d0d2d2', 1.0, 0.15),
    'door': ('#e6e7e4', 0.0, 0.5), 'tyre': ('#161718', 0.0, 0.85), 'hub': ('#dfe0dd', 0.0, 0.5), 'brake': ('#4a4c4e', 0.7, 0.5),
}
KEEP = ('glass', 'beacon', 'taxilight')


def combine(name, parts):
    """several parts as one (their faces keep zone and shading)"""
    out = K.Part(name)
    for p in parts:
        vmap = {}
        for f in p.bm.faces:
            vs = []
            for v in f.verts:
                if v not in vmap:
                    vmap[v] = out.bm.verts.new(v.co)
                vs.append(vmap[v])
            try:
                nf = out.bm.faces.new(vs)
            except ValueError:
                continue
            nf.material_index = out.slot(p.slots[f.material_index])
            nf.smooth = f.smooth
        p.bm.free()
    return out


def build(aircraft, variant):
    cfg = AIRCRAFT[aircraft]
    seats = cfg['variants'][variant]
    K.clear_scene()
    mats = K.Materials()
    for n, (c, m, r) in ZONES.items():
        mats.add(n, c, m, r)
    mats.add('glass', '#20262b', 0.0, 0.06)
    mats.add('beacon', '#ff3020', 0.0, 0.4, emissive='#ff3020', strength=0.0)
    mats.add('taxilight', '#fff6e4', 0.0, 0.2)
    root = K.node(aircraft + ('-' + variant if variant else ''))
    body = K.node('body', root)
    fus, canopy = S.fuselage(seats)
    cowls, ducts = S.intakes()
    air = combine('airframe', [fus, canopy, S.canopy_frames(seats), S.cockpit(seats), cowls, ducts, S.nacelles(), S.slab(), S.wings(),
                               S.fins(cfg['asym']), S.details({'id': aircraft}), S.lamps()])
    objs = [air.build(body, mats, sharp=38.0, weld=False, name='airframe')]
    objs.append(S.nozzles().build(root, mats, sharp=40.0, weld=False, name='nozzles'))
    pivot = K.node('stab', root, origin=S.at(0, S.STAB_PIVOT[1], S.STAB_PIVOT[0]))
    objs.append(S.stabs().build(pivot, mats, sharp=38.0, weld=False, name='stab_m'))
    gn = K.node('gear_nose', root, origin=S.NOSE_HINGE)
    fixed, steer, lens = S.nose_gear()
    objs.append(combine('gear_nose_m', [fixed, lens]).build(gn, mats, sharp=40.0, weld=False, name='gear_nose_m'))
    sn = K.node('steer_nose', gn, origin=(0, S.STEER_Y, S.WB / 2))
    objs.append(steer.build(sn, mats, sharp=40.0, weld=False, name='steer_nose_m'))
    for s, side in ((1, 'l'), (-1, 'r')):
        g = K.node('gear_' + side, root, origin=(s * S.MAIN_HINGE[0], S.MAIN_HINGE[1], S.MAIN_HINGE[2]))
        leg, wh = S.main_gear(s)
        objs.append(leg.build(g, mats, sharp=40.0, weld=False, name=f'gear_{side}_m'))
        sp = K.node('spin_' + side, g, origin=(s * S.TRACK / 2, S.R_MAIN, -S.WB / 2))
        objs.append(wh.build(sp, mats, sharp=40.0, weld=False, name=f'spin_{side}_m'))
    bpy.context.view_layer.update()
    return root, objs, mats, cfg, seats


def dump(objs, path):
    """every triangle in the game frame, with its object and zone (for the checks outside Blender)"""
    P, O, Z, names, zones = [], [], [], [], []
    dg = bpy.context.evaluated_depsgraph_get()
    for k, o in enumerate(objs):
        names.append(o.name)
        me = o.data
        me.calc_loop_triangles()
        M = o.matrix_world
        co = np.array([K.G(M @ v.co) for v in me.vertices])
        for t in me.loop_triangles:
            P.append(co[list(t.vertices)])
            O.append(k)
            n = me.materials[t.material_index].name
            if n not in zones:
                zones.append(n)
            Z.append(zones.index(n))
    np.savez_compressed(path, P=np.array(P, np.float32), O=np.array(O, np.int16), Z=np.array(Z, np.int16), names=np.array(names), zones=np.array(zones))
    del dg


def main(default_id="f15c"):
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--id", default=default_id)
    ap.add_argument('--variant', default='')
    ap.add_argument('--out', default='')
    ap.add_argument('--stage', default='full', choices=('shape', 'full'))
    ap.add_argument('--dump', default='')
    ap.add_argument('--render', default='')
    ap.add_argument('--views', default='')
    ap.add_argument('--size', type=int, default=2048)
    ap.add_argument('--quick', action='store_true', help='workbench renders instead of Cycles')
    a = ap.parse_args(argv)
    variant = '' if a.variant in ('', 'base') else a.variant
    root, objs, mats, cfg, seats = build(a.id, variant)
    if a.dump:
        dump(objs, a.dump)
    if a.stage == 'full':
        import f15_paint
        f15_paint.paint(objs, mats, a.id, variant, seats, cfg, size=a.size, keep=KEEP,
                        workdir=os.path.join(os.path.dirname(os.path.abspath(a.out or a.render or '.')), 'tex-' + a.id + ('-' + variant if variant else '')))
    K.report(root)
    if a.out:
        os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
        K.export_glb(os.path.abspath(a.out), root)
        print('GLB', a.out)
    if a.render:
        import f15_scene
        views = [v for v in a.views.split(',') if v] or None
        f15_scene.render_all(root, a.render, views=views, quick=a.quick or a.stage == 'shape', seats=seats)


if __name__ == "__main__":
    main()
