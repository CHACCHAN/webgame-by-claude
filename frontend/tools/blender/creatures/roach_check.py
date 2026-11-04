"""
Checks an exported cockroach GLB by importing it back into an empty Blender scene: the skin, the bone names, the
animation's frame count and duration, the materials and their textures (the metallic-roughness map's blue channel
must stay 1 so a metallic livery can turn metalness on), and how far the planted feet slide over the cycle when the
model travels STRIDE per cycle (sampled between the keys as well).
"""
import math

import bpy
import numpy as np

import roach_anatomy as A
from roach_geom import S

FEET = [f'leg_{s}{k}_tarsus2' for s in 'LR' for k in (1, 2, 3)]


def check(path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=path)
    arms = [o for o in bpy.context.scene.objects if o.type == 'ARMATURE']
    meshes = [o for o in bpy.context.scene.objects if o.type == 'MESH']
    rep = {'armatures': len(arms), 'meshes': len(meshes)}
    arm = arms[0]
    rep['bones'] = len(arm.data.bones)
    rep['bone_names'] = [b.name for b in arm.data.bones]
    skinned = [m.name for m in meshes if any(md.type == 'ARMATURE' and md.object == arm for md in m.modifiers)]
    rep['skinned_meshes'] = skinned
    rep['triangles'] = sum(sum(len(p.vertices) - 2 for p in m.data.polygons) for m in meshes)
    mats = {}
    for m in meshes:
        for mat in m.data.materials:
            if mat.name in mats:
                continue
            info = {'images': []}
            for n in mat.node_tree.nodes:
                if n.type == 'TEX_IMAGE' and n.image:
                    img = n.image
                    px = np.array(img.pixels[:], np.float32).reshape(-1, 4)
                    info['images'].append({'name': img.name, 'size': list(img.size),
                                           'mean_rgb': [round(float(v), 3) for v in px[:, :3].mean(axis=0)],
                                           'min_b': round(float(px[:, 2].min()), 3)})
            mats[mat.name] = info
    rep['materials'] = mats
    ad = arm.animation_data
    act = ad.action if ad else None
    if act is None and bpy.data.actions:
        act = bpy.data.actions[0]
        arm.animation_data_create()
        arm.animation_data.action = act
    rep['action'] = act.name if act else None
    fr = act.frame_range if act else (0, 0)
    fps = bpy.context.scene.render.fps / bpy.context.scene.render.fps_base
    rep['frame_range'] = [float(fr[0]), float(fr[1])]
    rep['fps'] = fps
    rep['duration_s'] = (fr[1] - fr[0]) / fps
    # foot slip: claw bases in the game frame (m), the model moving forward STRIDE per cycle
    sc = bpy.context.scene
    n = int(round(fr[1] - fr[0]))
    sub = 4
    tracks = {f: [] for f in FEET}
    for i in range(n * sub + 1):
        f = fr[0] + i / sub
        sc.frame_set(int(math.floor(f)), subframe=f - math.floor(f))
        for name in FEET:
            pb = arm.pose.bones[name]
            p = arm.matrix_world @ pb.tail
            tracks[name].append((i / (n * sub), p.x, p.z, -p.y))
    stride = A.STRIDE * S
    slip = {}
    for name, pts in tracks.items():
        pts = np.array(pts)
        ground = pts[:, 2] < pts[:, 2].min() + 0.002
        world_z = pts[:, 3] + pts[:, 0] * stride
        # contiguous runs on the ground
        runs, cur = [], []
        for i, g in enumerate(ground):
            if g:
                cur.append(i)
            elif cur:
                runs.append(cur)
                cur = []
        if cur:
            runs.append(cur)
        worst = max((float(np.ptp(world_z[r])) for r in runs if len(r) > 2), default=0.0)
        worst_x = max((float(np.ptp(pts[r, 1])) for r in runs if len(r) > 2), default=0.0)
        slip[name] = {'stance_samples': int(ground.sum()), 'slip_along_m': round(worst, 5),
                      'slip_across_m': round(worst_x, 5), 'speed_check': None}
        # speed of the planted foot relative to the body (should be −stride per cycle)
        r = max(runs, key=len)
        if len(r) > 2:
            v = (pts[r[-1], 3] - pts[r[0], 3]) / (pts[r[-1], 0] - pts[r[0], 0])
            slip[name]['speed_check'] = round(float(v / -stride), 4)
    rep['slip'] = slip
    # first / last key equal
    diffs = 0.0
    for fc in _fcurves(act):
        kp = fc.keyframe_points
        if len(kp) > 1:
            diffs = max(diffs, abs(kp[0].co[1] - kp[-1].co[1]))
    rep['first_last_max_diff'] = diffs
    return rep


def _fcurves(action):
    if hasattr(action, 'fcurves') and len(getattr(action, 'fcurves', [])) > 0:
        return list(action.fcurves)
    out = []
    for layer in getattr(action, 'layers', []):
        for strip in layer.strips:
            for bag in strip.channelbags:
                out.extend(bag.fcurves)
    return out
