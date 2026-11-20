"""Blender check pictures for the game's tank models (not part of the GLB).

render_check(root, '/tmp/check', views=['front34_l', 'gear'], quick=True)
sheet('/tmp/check', '/tmp/check/contact.jpg')

VIEWS gives the PNG basenames in sheet order. traverse_min/max add combined
yaw and elevation checks. Coordinates below are Blender
metres: +X is vehicle left, -Y is forward, +Z is up (see TankModel.ts).
"""
import math
from contextlib import contextmanager
from pathlib import Path

import bpy
from mathutils import Matrix, Vector


SIZE = (1280, 720)
# View name: (direction from subject towards camera, sheet caption).
VIEWS = {
    'front': ((0, -1, .09), 'Front'),
    'front34_l': ((.85, -1, .48), 'Front quarter / left'),
    'front34_r': ((-.85, -1, .48), 'Front quarter / right'),
    'side': ((1, 0, .05), 'Left side'),
    'rear34': ((.85, 1, .48), 'Rear quarter'),
    'rear': ((0, 1, .09), 'Rear'),
    'traverse': ((.85, -1, .48), 'Traverse / 30 degrees left'),
    'elev_min': ((1, 0, 0), 'Elevation / minimum'),
    'elev_max': ((1, 0, 0), 'Elevation / maximum'),
    'traverse_min': ((1, -.35, .12), 'Traverse left / minimum elevation'),
    'traverse_max': ((1, -.35, .12), 'Traverse left / maximum elevation'),
    'gear': ((1, -.14, .09), 'Front running gear / left'),
    'top': ((0, 0, 1), 'Top'),
    'under': ((.86, .38, -.80), 'Belly / from below left'),
    'o_side': ((1, 0, 0), 'Outline / left side'),
    'o_top': ((0, 0, 1), 'Outline / top'),
    'o_front': ((0, -1, 0), 'Outline / front'),
}


@contextmanager
def _stage():
    # Separate scene: never render an unrelated mesh, export our apron, or
    # change the caller's camera, world, sequencer or render configuration.
    scene = bpy.data.scenes.new('Tank check')
    owned = [scene]

    def keep(block):
        owned.append(block)
        return block

    try:
        with bpy.context.temp_override(scene=scene, view_layer=scene.view_layers[0]):
            yield scene, keep
    finally:
        bpy.data.batch_remove(ids=owned)


def _object(sc, keep, data):
    obj = keep(bpy.data.objects.new(data.name, keep(data)))
    sc.collection.objects.link(obj)
    return obj


def _box(points):
    lo = Vector(tuple(min(p[i] for p in points) for i in range(3)))
    hi = Vector(tuple(max(p[i] for p in points) for i in range(3)))
    return lo, hi


def _corners(lo, hi):
    return [Vector((x, y, z)) for x in (lo.x, hi.x) for y in (lo.y, hi.y) for z in (lo.z, hi.z)]


def _bounds(meshes):
    graph = bpy.context.evaluated_depsgraph_get()
    evaluated = (mesh.evaluated_get(graph) for mesh in meshes)
    return [obj.matrix_world @ Vector(c) for obj in evaluated for c in obj.bound_box]


def _frame(cam, direction, points, ortho):
    # Fit in camera space, accounting for depth as well as aspect ratio; the
    # muzzle can be much closer to the eye than the centre of the hull.
    back = Vector(direction).normalized()
    up_hint = Vector((1, 0, 0)) if abs(back.z) > .95 else Vector((0, 0, 1))
    right = up_hint.cross(back).normalized()
    up = back.cross(right)
    basis = Matrix((right, up, back))
    local = [basis @ p for p in points]
    lo, hi = _box(local)
    center = (lo + hi) / 2
    aspect = SIZE[0] / SIZE[1]
    cam.data.type = 'ORTHO' if ortho else 'PERSP'
    width = max(.01, hi.x - lo.x, (hi.y - lo.y) * aspect) * 1.12
    cam.data.ortho_scale = width
    slope = cam.data.sensor_width / (2 * cam.data.lens)
    depth = max(p.z - center.z + 1.12 * max(abs(p.x - center.x), aspect * abs(p.y - center.y)) / slope
                for p in local)
    depth = max(depth, hi.z - center.z + .25)
    cam.location = basis.transposed() @ center + back * depth
    cam.rotation_euler = basis.transposed().to_euler()
    cam.data.clip_end = max(100, depth + (hi - lo).length * 2)


@contextmanager
def _poses(turret, gun):
    # Save the active representation before switching modes: Blender converts
    # rotations on a mode change, and an Euler round trip can lose full turns.
    saved = []
    try:
        for obj in (turret, gun):
            if obj is None:
                continue
            mode = obj.rotation_mode
            prop = {'QUATERNION': 'rotation_quaternion', 'AXIS_ANGLE': 'rotation_axis_angle'}.get(mode, 'rotation_euler')
            saved.append((obj, mode, prop, tuple(getattr(obj, prop))))
            obj.rotation_mode = 'QUATERNION'
        yield
    finally:
        for obj, mode, prop, value in saved:
            obj.rotation_mode = mode
            setattr(obj, prop, value)


def render_check(root, outdir, elev=(-7, 10), views=None, quick=False):
    """Write one 1280x720 PNG per selected view. elev is (min, max) in degrees."""
    names = list(VIEWS if views is None else (views.split(',') if isinstance(views, str) else views))
    for name in names:
        if name not in VIEWS:
            raise ValueError(f'Unknown tank view {name!r}; choose from {", ".join(VIEWS)}')
    if not names:
        return
    objects = [root, *root.children_recursive]
    nodes = {obj.name: obj for obj in objects}
    turret, gun = nodes.get('turret'), nodes.get('gun')
    for name, pivot in [('traverse', turret), ('elev_min', gun), ('elev_max', gun)]:
        if name in names and pivot is None:
            raise ValueError(f'{name} requires a {"turret" if name == "traverse" else "gun"} pivot under {root.name}')
    meshes = [o for o in objects if o.type == 'MESH' and not o.hide_render]
    if not meshes:
        raise ValueError(f'No renderable tank mesh under {root.name}')
    upper = set([turret, *turret.children_recursive]) if turret else set()
    hull = [m for m in meshes if m not in upper] or meshes
    directory = Path(outdir).resolve()
    directory.mkdir(parents=True, exist_ok=True)

    with _stage() as (sc, keep), _poses(turret, gun):
        for obj in objects:
            sc.collection.objects.link(obj)
        sc.render.engine = 'BLENDER_WORKBENCH' if quick else 'CYCLES'
        if not quick:
            sc.cycles.device = 'CPU'
            sc.cycles.samples = 32
        sc.render.resolution_x, sc.render.resolution_y = SIZE
        sc.render.resolution_percentage = 100
        sc.render.image_settings.file_format = 'PNG'
        sc.view_settings.view_transform = 'Standard'
        cam = _object(sc, keep, bpy.data.cameras.new('Check camera'))
        cam.data.sensor_fit = 'HORIZONTAL'
        cam.data.lens = 50
        sc.camera = cam
        sun = _object(sc, keep, bpy.data.lights.new('Check sun', 'SUN'))
        sun.data.energy, sun.data.angle = 2.2, math.radians(12)
        sc.world = keep(bpy.data.worlds.new('Check sky'))
        sc.world.use_nodes = True
        sky = sc.world.node_tree.nodes.get('Background')
        floor = _object(sc, keep, bpy.data.meshes.new('Check ground'))
        sc.view_layers[0].update()
        lo, hi = _box(_bounds(hull))
        r = 30 * max(1, (hi - lo).length)
        floor.location = ((hi.x + lo.x)/2, (hi.y + lo.y)/2, lo.z - .003)
        floor.data.from_pydata([(-r,-r,0), (r,-r,0), (r,r,0), (-r,r,0)], [], [(0,1,2,3)])
        mat = keep(bpy.data.materials.new('Check concrete'))
        mat.diffuse_color = (.27, .27, .26, 1)
        floor.data.materials.append(mat)
        ink = keep(bpy.data.materials.new('Outline black'))
        ink.use_nodes = True
        nt = ink.node_tree
        black = nt.nodes.new('ShaderNodeEmission')
        black.inputs['Color'].default_value = (0, 0, 0, 1)
        nt.links.new(black.outputs[0], nt.nodes.get('Material Output').inputs['Surface'])
        layer = sc.view_layers[0]
        # Compose with rest rotations, as TankModel.setAim does. In
        # particular a fitted bore need not be exactly horizontal at rest.
        turret_base=turret.matrix_basis.to_quaternion() if turret else None
        gun_base=gun.matrix_basis.to_quaternion() if gun else None
        for name in names:
            # Rotation about +Z carries -Y towards vehicle left; about -X lifts the nose.
            if turret:
                turret.rotation_quaternion = turret_base @ Matrix.Rotation(math.radians(30 if name.startswith('traverse') else 0), 3, 'Z').to_quaternion()
            if gun:
                pitch = elev[0] if name.endswith('_min') else elev[1] if name.endswith('_max') else 0
                gun.rotation_quaternion = gun_base @ Matrix.Rotation(math.radians(-pitch), 3, 'X').to_quaternion()
            layer.update()
            points = _bounds(meshes)
            if name == 'gear':
                # Use the hull rather than the gun tip to find the forward half.
                a, b = _box(_bounds(hull))
                span = b - a
                points = _corners(a + Vector((.85 * span.x, 0, 0)),
                                  a + Vector((span.x, .52 * span.y, .55 * span.z)))
            outline = name.startswith('o_')
            direction = VIEWS[name][0]
            _frame(cam, direction, points, outline)
            floor.hide_render = outline or name == 'under'
            if name == 'under':
                # Place and aim explicitly in Blender world space. No Euler
                # basis inherited from the preceding top shot, no floor in
                # either render engine. Log the setup alongside the image.
                a,b = _box(points); target = (a+b)*.5
                cam.location = target + Vector(direction).normalized()*((b-a).length*1.9)
                sightline = target - cam.location
                cam.rotation_euler = sightline.to_track_quat('-Z','Y').to_euler()
                if not (cam.location.z < lo.z and sightline.z > 0):
                    raise ValueError('underside camera not below vehicle')
                print(f'VIEW under cameraZ={cam.location.z:.3f} targetZ={target.z:.3f} floor=off')
            key = Vector(direction) + Vector((.35, -.45, -1 if name == 'under' else 1))
            sun.rotation_euler = (-key).to_track_quat('-Z', 'Y').to_euler()
            bg = (1, 1, 1) if outline else (.35, .4, .48)
            sky.inputs['Color'].default_value = (*bg, 1)
            sc.world.color = bg
            layer.material_override = ink if outline else None
            sh = sc.display.shading
            sh.background_type = 'WORLD'
            sh.light = 'FLAT' if outline else 'STUDIO'
            has_atlas = any(any(m.name == 'armor' for m in ob.data.materials) for ob in meshes)
            sh.color_type = 'SINGLE' if outline else ('TEXTURE' if has_atlas else 'MATERIAL')
            sh.single_color = (0, 0, 0)
            sh.show_cavity = sh.show_shadows = not outline
            sh.show_specular_highlight = not outline
            sc.render.filepath = str(directory / f'{name}.png')
            layer.update()
            bpy.ops.render.render(scene=sc.name, write_still=True)


def sheet(outdir, path):
    """Tile the known view PNGs present in outdir; Blender's VSE draws the captions and writes JPEG."""
    directory = Path(outdir).resolve()
    names = [name for name in VIEWS if (directory / f'{name}.png').is_file()]
    if not names:
        raise ValueError(f'No tank view PNGs in {directory}')
    target = Path(path).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    cols = min(4, math.ceil(math.sqrt(len(names))))
    rows = math.ceil(len(names) / cols)
    tile_w, photo_h, caption_h = 384, 216, 32
    tile_h = photo_h + caption_h
    w, h = cols * tile_w, rows * tile_h
    with _stage() as (sc, _):
        sc.render.resolution_x, sc.render.resolution_y = w, h
        sc.render.resolution_percentage = 100
        sc.view_settings.view_transform = 'Standard'
        sc.render.image_settings.file_format = 'JPEG'
        sc.render.image_settings.color_mode = 'RGB'
        sc.render.image_settings.quality = 90
        sc.render.use_file_extension = False
        editor = sc.sequence_editor_create()
        strips = editor.strips if hasattr(editor, 'strips') else editor.sequences
        for i, name in enumerate(names):
            row, col = divmod(i, cols)
            x = (col + .5) * tile_w
            bottom = (rows - row - 1) * tile_h
            image = strips.new_image(name, str(directory / f'{name}.png'), channel=1+i, frame_start=1)
            image.blend_type = 'ALPHA_OVER'
            scale = tile_w / SIZE[0]
            image.transform.scale_x = image.transform.scale_y = scale
            image.transform.offset_x = x - w/2
            image.transform.offset_y = bottom + caption_h + photo_h/2 - h/2
            text = strips.new_effect(f'{name} label', type='TEXT', channel=1+len(names)+i, frame_start=1, length=1)
            text.blend_type = 'ALPHA_OVER'
            text.text, text.font_size = VIEWS[name][1], 18
            if hasattr(text, 'anchor_x'):
                text.anchor_x, text.anchor_y = 'CENTER', 'CENTER'
            else:
                text.align_x, text.align_y = 'CENTER', 'CENTER'
            text.location = (x/w, (bottom + caption_h/2)/h)
        sc.render.filepath = str(target)
        bpy.ops.render.render(scene=sc.name, write_still=True)
