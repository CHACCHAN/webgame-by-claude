"""
TOUGE NOCTURNE's cockroach, our own model: a giant American cockroach (ワモンゴキブリ, Periplaneta americana) built,
painted, rigged and animated by this script in Blender (bpy / bmesh / numpy, no other assets).

  ~/.local/bin/blender -t 4 --background --factory-startup --python frontend/tools/blender/creatures/roach.py -- \
      --out <file.glb> [--render <dir> --views top,side,... --samples N --size WxH] [--frames 0,0.25] [--check]

Output (see render/RoachModel.ts): one skinned mesh on one armature, head +Z, +Y up, feet on y = 0; built at the
game's scale (body 3.4 m from the head's front to the wing tips). One animation, a seamless in-place scuttle
(alternating tripod) whose planted feet move back 1.6 m per cycle. The foremost bone named head… (`head_eyes`)
sits between the compound eyes. Modules: roach_anatomy (proportions), roach_geom (mesh building), roach_body /
roach_legs (shells), roach_rig (skeleton, gait), roach_tex (textures), roach_stage (check renders).
"""
import sys

sys.dont_write_bytecode = True

import argparse
import json
import math
import os
import time

import bpy
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import roach_anatomy as A  # noqa: E402
import roach_body as RB  # noqa: E402
import roach_check as RC  # noqa: E402
import roach_geom as RGm  # noqa: E402
import roach_legs as RL  # noqa: E402
import roach_rig as RG  # noqa: E402
import roach_stage as ST  # noqa: E402
import roach_tex as TX  # noqa: E402


def parse():
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True)
    ap.add_argument('--render')
    ap.add_argument('--views', default='top,side,front34,below,head,leg')
    ap.add_argument('--samples', type=int, default=32)
    ap.add_argument('--size', default='1280x720')
    ap.add_argument('--frames', default='0', help='cycle times (0..1) to render the views at')
    ap.add_argument('--gait', action='store_true', help='render 8 frames of the cycle (top and side)')
    ap.add_argument('--tex', default='2048,2048,2048,1024', help='shell, body, legs, roughness atlas sizes')
    ap.add_argument('--image-format', default='WEBP')
    ap.add_argument('--no-export', action='store_true')
    ap.add_argument('--check', action='store_true', help='re-import the GLB and check it (after the renders)')
    return ap.parse_args(argv)


def build(args):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    t0 = time.time()
    specs = RG.bone_specs()
    arm = RG.build_armature(specs)
    names = [s[0] for s in specs]
    # shells
    parts = []
    wings = []
    for side in (1, -1):
        p, shape = RB.build_tegmen(side)
        parts.append(p)
        wings.append(shape)
    parts.append(RB.build_pronotum())
    parts.append(RB.build_thorax())
    parts.append(RB.build_abdomen())
    parts.append(RB.build_head())
    parts.append(RB.build_mouth())
    for side in (1, -1):
        parts.append(RB.build_eye(side))
        parts.append(RB.build_antenna(side))
        parts += RB.build_palps(side)
        parts.append(RB.build_cercus(side))
    parts += RL.build_legs()
    print(f'[roach] geometry {time.time() - t0:.1f}s', flush=True)
    sizes = [int(v) for v in args.tex.split(',')]
    tex_dir = os.path.join(os.path.dirname(os.path.abspath(args.out)), 'roach_tex')
    mats = TX.build_materials(tex_dir, wings, {'shell': sizes[0], 'body': sizes[1], 'legs': sizes[2], 'mr': sizes[3]})
    print(f'[roach] textures {time.time() - t0:.1f}s', flush=True)
    order = ['roach_shell', 'roach_body', 'roach_legs']
    obj = RGm.assemble('roach_body_mesh', parts, [mats[m] for m in order], arm, names)
    obj.data.set_sharp_from_angle(angle=math.radians(60))
    RG.animate(arm)
    print(f'[roach] rig + animation {time.time() - t0:.1f}s, leg reach warnings {RG.leg_warnings()}', flush=True)
    return arm, obj


def export(arm, obj, path, image_format):
    bpy.ops.object.select_all(action='DESELECT')
    arm.select_set(True)
    obj.select_set(True)
    bpy.context.view_layer.objects.active = arm
    kw = dict(filepath=path, export_format='GLB', use_selection=True, export_yup=True, export_apply=False,
              export_skins=True, export_animations=True, export_animation_mode='ACTIONS', export_force_sampling=True,
              export_frame_range=True, export_image_format=image_format, export_image_quality=90,
              export_materials='EXPORT', export_extras=False, export_cameras=False, export_lights=False,
              export_def_bones=False, export_optimize_animation_size=False, export_anim_single_armature=True,
              export_morph=False, export_tangents=False)
    while True:
        try:
            bpy.ops.export_scene.gltf(**kw)
            break
        except TypeError as e:
            msg = str(e)
            bad = [k for k in kw if f'"{k}"' in msg or f"'{k}'" in msg]
            if not bad:
                raise
            print('[roach] exporter has no', bad)
            for k in bad:
                kw.pop(k)


def stats(arm, obj):
    me = obj.data
    tris = sum(len(p.vertices) - 2 for p in me.polygons)
    return dict(triangles=tris, vertices=len(me.vertices), materials=len(me.materials), bones=len(arm.data.bones),
                frames=A.FRAMES, fps=bpy.context.scene.render.fps)


def foot_track(arm, samples_per_frame=4):
    """claw-base positions (game mm) of each leg over the cycle, from the evaluated armature"""
    sc = bpy.context.scene
    out = {}
    n = A.FRAMES * samples_per_frame
    for i in range(n + 1):
        f = i / samples_per_frame
        sc.frame_set(int(math.floor(f)), subframe=f - math.floor(f))
        for side in (1, -1):
            for k in (1, 2, 3):
                pb = arm.pose.bones[RG.leg_bone(side, k, 'tarsus2')]
                p = RGm.G(arm.matrix_world @ pb.tail)
                out.setdefault((side, k), []).append((f / A.FRAMES, *p))
    sc.frame_set(0)
    return out


def slip_report(arm):
    """how far the planted feet slide (should be 0) and how fast they move (should be −STRIDE per cycle)"""
    tr = foot_track(arm)
    rep = {}
    for (side, k), pts in tr.items():
        pts = np.array(pts)
        name = ('L' if side > 0 else 'R') + str(k)
        ph = np.array([RG.leg_phase(side, k, t) for t in pts[:, 0]])
        stance = ph < A.DUTY - 0.01
        st = pts[stance]
        # ground-relative motion: add the body's travel (the game moves the model forward STRIDE per cycle)
        world_z = st[:, 3] + st[:, 0] * A.STRIDE
        groups = []
        cur = [0]
        for i in range(1, len(st)):
            if st[i, 0] - st[i - 1, 0] > 1.5 / (A.FRAMES * 4):
                groups.append(cur)
                cur = []
            cur.append(i)
        groups.append(cur)
        slip_z = max((np.ptp(world_z[g]) for g in groups if len(g) > 1), default=0.0)
        slip_x = max((np.ptp(st[g, 1]) for g in groups if len(g) > 1), default=0.0)
        slip_y = max((np.ptp(st[g, 2]) for g in groups if len(g) > 1), default=0.0)
        rep[name] = dict(slip_z_mm=round(float(slip_z), 4), slip_x_mm=round(float(slip_x), 4),
                         slip_y_mm=round(float(slip_y), 4), ground_y_mm=round(float(st[:, 2].mean()), 3),
                         max_lift_mm=round(float(pts[:, 2].max() - st[:, 2].mean()), 2))
    return rep


def extents(arm, obj, t=0.0):
    """posed bounding box (game mm) at cycle time t, and the body length"""
    sc = bpy.context.scene
    sc.frame_set(int(round(t * A.FRAMES)))
    dg = bpy.context.evaluated_depsgraph_get()
    ev = obj.evaluated_get(dg)
    me = ev.to_mesh()
    co = np.array([RGm.G(obj.matrix_world @ v.co) for v in me.vertices])
    ev.to_mesh_clear()
    lo, hi = co.min(axis=0), co.max(axis=0)
    head = arm.pose.bones['head_eyes']
    hp = RGm.G(arm.matrix_world @ head.head)
    sc.frame_set(0)
    return dict(min=[round(float(v), 3) for v in lo], max=[round(float(v), 3) for v in hi],
                z_extent_mm=round(float(hi[2] - lo[2]), 3), head_eyes_mm=[round(float(v), 3) for v in hp])


def main():
    args = parse()
    arm, obj = build(args)
    out = os.path.abspath(args.out)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    st = stats(arm, obj)
    st['extent_t0'] = extents(arm, obj, 0.0)
    st['slip'] = slip_report(arm)
    print('[roach] stats', json.dumps(st, indent=1), flush=True)
    if not args.no_export:
        export(arm, obj, out, args.image_format)
        print(f'[roach] exported {out} {os.path.getsize(out) / 1e6:.2f} MB', flush=True)
    with open(os.path.splitext(out)[0] + '_stats.json', 'w') as f:
        json.dump(st, f, indent=1)
    if args.render:
        os.makedirs(args.render, exist_ok=True)
        ST.scene()
        w, h = (int(v) for v in args.size.split('x'))
        times = [float(v) for v in args.frames.split(',')]
        for t in times:
            bpy.context.scene.frame_set(int(round(t * A.FRAMES)))
            for v in [v for v in args.views.split(',') if v]:
                suffix = '' if len(times) == 1 else f'_t{t:.3f}'
                ST.render(v, os.path.join(args.render, f'{v}{suffix}.png'), (w, h), args.samples)
                print(f'[roach] rendered {v}{suffix}', flush=True)
        if args.gait:
            for i in range(8):
                f = i * A.FRAMES // 8
                bpy.context.scene.frame_set(f)
                for v in ('gait_top', 'gait_side'):
                    ST.render(v, os.path.join(args.render, f'{v}_{i}.png'), (640, 480), min(args.samples, 16))
            print('[roach] gait frames rendered', flush=True)
    if args.check and not args.no_export:
        rep = RC.check(out)
        with open(os.path.splitext(out)[0] + '_check.json', 'w') as f:
            json.dump(rep, f, indent=1)
        print('[roach] check', json.dumps({k: v for k, v in rep.items() if k != 'bone_names'}, indent=1), flush=True)


main()
