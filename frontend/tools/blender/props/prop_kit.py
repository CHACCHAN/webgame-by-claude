"""
Building blocks for the roadside scenery props (street light, wind turbine, curve mirror, vending machine, torii,
stone lantern, bus shelter, traffic cone): Blender 5 (bpy / bmesh), run headless by the per-prop scripts.

Frame: everything is written in the game's frame (metres, +Y up, +Z = the prop's front, +X left); `M.build` turns it
into Blender's Z-up frame, so the glTF exporter with export_yup gives the game's axes back.
Blender (x, y, z) = game (x, -z, y).

`M` is a mesh under construction: primitives (box, cyl, loft, sweep, prism, ...) append closed shells, each with its
normals made to point outwards; `build` marks edges sharper than `sharp` degrees, smooths the rest and makes the object.
Materials: `material()` (Principled; base colour / emissive can be driven by an image, which the glTF exporter writes
as baseColorTexture / emissiveTexture). Images: `load_image` / numpy-painted `new_image`.
Rendering for checks: `render_glb` imports the written GLB into a clean scene (so the export is what is looked at).
"""
import math
import os
import shutil
import subprocess
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
G2B = Matrix(((1, 0, 0, 0), (0, 0, -1, 0), (0, 1, 0, 0), (0, 0, 0, 1)))


def B(x, y, z):
    """game → Blender"""
    return Vector((x, -z, y))


def srgb(hex_colour):
    h = hex_colour.lstrip('#')
    out = []
    for i in (0, 2, 4):
        c = int(h[i:i + 2], 16) / 255
        out.append(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
    return (*out, 1.0)


def clear_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)


# ---------------------------------------------------------------------------------------------------- materials

def material(name, colour='#808080', metallic=0.0, roughness=0.5, base_image=None, emit_image=None, emit_colour=None,
             emit_strength=1.0):
    """
    Principled material. `base_image` drives Base Color, `emit_image` the Emission Color (strength `emit_strength`);
    pass the same image for both when the texture also glows. `emit_colour` is a plain emissive colour.
    """
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    p = nt.nodes.get('Principled BSDF')
    p.inputs['Base Color'].default_value = srgb(colour)
    p.inputs['Metallic'].default_value = metallic
    p.inputs['Roughness'].default_value = roughness
    p.inputs['IOR'].default_value = 1.5  # the glTF default: no KHR_materials_ior
    nodes = {}
    for key, img in (('base', base_image), ('emit', emit_image)):
        if img is None:
            continue
        if img not in nodes:
            n = nt.nodes.new('ShaderNodeTexImage')
            n.image = img
            n.interpolation = 'Linear'
            n.extension = 'REPEAT'
            nodes[img] = n
        nt.links.new(nodes[img].outputs['Color'], p.inputs['Base Color' if key == 'base' else 'Emission Color'])
    if emit_image is not None or emit_colour:
        if emit_colour:
            p.inputs['Emission Color'].default_value = srgb(emit_colour)
        p.inputs['Emission Strength'].default_value = emit_strength
    return m


def load_image(path, srgb_colour=True):
    img = bpy.data.images.load(path)
    img.colorspace_settings.name = 'sRGB' if srgb_colour else 'Non-Color'
    return img


def save_image(name, rgba, path):
    """a numpy float array (h, w, 4), row 0 at the top, written as a PNG and loaded back from the file"""
    import numpy as np
    h, w = rgba.shape[:2]
    img = bpy.data.images.new(name, w, h, alpha=False)
    img.colorspace_settings.name = 'sRGB'
    px = np.ascontiguousarray(rgba[::-1].astype('float32')).ravel()  # Blender rows run bottom-up
    img.pixels.foreach_set(px)
    img.filepath_raw = path
    img.file_format = 'PNG'
    img.save()
    bpy.data.images.remove(img)
    return load_image(path)


def host_python():
    """the system python3 (with PIL) for the painted textures; None when there is none"""
    for c in ('/usr/bin/python3', shutil.which('python3')):
        if c and os.path.exists(c):
            try:
                if subprocess.run([c, '-I', '-c', 'import PIL'], capture_output=True).returncode == 0:
                    return c
            except OSError:
                pass
    return None


def paint(out_dir, names):
    """run props/paint.py (host python + PIL) for the given textures; returns the folder holding them"""
    d = os.path.join(out_dir, 'tex')
    os.makedirs(d, exist_ok=True)
    py = host_python()
    if py is None:
        raise SystemExit('paint: no python3 with PIL on this host')
    r = subprocess.run([py, '-I', os.path.join(HERE, 'paint.py'), d, *names], capture_output=True, text=True)
    if r.returncode:
        raise SystemExit('paint.py failed:\n' + r.stdout + r.stderr)
    return d


# ---------------------------------------------------------------------------------------------------- geometry

def bezier(p0, p1, p2, p3, n):
    out = []
    for i in range(n + 1):
        t = i / n
        u = 1 - t
        out.append(tuple(u ** 3 * a + 3 * u * u * t * b + 3 * u * t * t * c + t ** 3 * d for a, b, c, d in zip(p0, p1, p2, p3)))
    return out


def rounded_rect(cx, cz, w, d, r, n=4):
    """plan outline (x, z) of a rounded rectangle, counter-clockwise seen from +Y"""
    r = min(r, w / 2, d / 2)
    pts = []
    for ox, oz, a0 in ((w / 2 - r, d / 2 - r, 0), (-w / 2 + r, d / 2 - r, 90), (-w / 2 + r, -d / 2 + r, 180), (w / 2 - r, -d / 2 + r, 270)):
        for k in range(n + 1):
            a = math.radians(a0 + 90 * k / n)
            pts.append((cx + ox + r * math.cos(a), cz + oz + r * math.sin(a)))
    return pts


def circle_pts(cx, cz, r, n):
    return [(cx + r * math.cos(2 * math.pi * k / n), cz + r * math.sin(2 * math.pi * k / n)) for k in range(n)]


class M:
    """a mesh under construction, in the game frame"""

    def __init__(self, name):
        self.name = name
        self.bm = bmesh.new()
        self.slots = []
        self.stack = [Matrix.Identity(4)]
        self.uv_ctx = []      # [(fn(list of coords) -> list of (u, v), only material or None)]
        self.uv_done = set()

    # -- transforms: everything added inside `with m.at(matrix):` is moved by it
    def at(self, matrix):
        return _Xf(self, matrix)

    def slot(self, mat):
        if mat not in self.slots:
            self.slots.append(mat)
        return self.slots.index(mat)

    def uvmap(self, fn, only=None):
        """with m.uvmap(fn, only=material): faces added inside get their UVs from fn(corner positions) → [(u, v)]"""
        return _Uv(self, fn, only)

    def add(self, bm, mat, closed=True, flip=False, front=None):
        """
        append a bmesh (game frame) with one material; closed shells get their normals pointed outwards.
        front: another material for the faces looking straight to +Z.
        """
        bmesh.ops.transform(bm, matrix=self.stack[-1], verts=bm.verts)
        if closed:
            bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        elif flip:
            bmesh.ops.reverse_faces(bm, faces=bm.faces)
        bm.normal_update()
        idx = self.slot(mat)
        fidx = self.slot(front) if front is not None else None
        vmap = {v: self.bm.verts.new(v.co) for v in bm.verts}
        for f in bm.faces:
            nf = self.bm.faces.new([vmap[v] for v in f.verts])
            nf.material_index = fidx if (fidx is not None and f.normal.z > 0.99) else idx
            nf.smooth = True
            for fn, only in self.uv_ctx:
                if only is not None and self.slots[nf.material_index] is not only:
                    continue
                layer = self.bm.loops.layers.uv.verify()
                uvs = fn([lp.vert.co.copy() for lp in nf.loops])
                for lp, uv in zip(nf.loops, uvs):
                    lp[layer].uv = uv
                self.uv_done.add(nf)
        bm.free()

    def absorb(self, other):
        """append another M's faces (and free it)"""
        vmap = {v: self.bm.verts.new(v.co) for v in other.bm.verts}
        for f in other.bm.faces:
            nf = self.bm.faces.new([vmap[v] for v in f.verts])
            nf.material_index = self.slot(other.slots[f.material_index])
            nf.smooth = True
        other.bm.free()

    # -- primitives
    def box(self, mat, x0, x1, y0, y1, z0, z1, bevel=0.0, seg=2, front=None):
        bm = bmesh.new()
        r = bmesh.ops.create_cube(bm, size=1.0)
        sx, sy, sz = x1 - x0, y1 - y0, z1 - z0
        for v in r['verts']:
            v.co = Vector((v.co.x * sx + (x0 + x1) / 2, v.co.y * sy + (y0 + y1) / 2, v.co.z * sz + (z0 + z1) / 2))
        if bevel > 0:
            bmesh.ops.bevel(bm, geom=list(bm.edges), offset=min(bevel, sx / 2.01, sy / 2.01, sz / 2.01), segments=seg,
                            profile=0.5, affect='EDGES', clamp_overlap=True)
        self.add(bm, mat, front=front)

    def cyl(self, mat, a, b, r0, r1=None, seg=16, caps=(True, True)):
        """a (tapered) cylinder from point a (radius r0) to point b (radius r1)"""
        r1 = r0 if r1 is None else r1
        a, b = Vector(a), Vector(b)
        d = b - a
        bm = bmesh.new()
        bmesh.ops.create_cone(bm, cap_ends=False, cap_tris=False, segments=seg, radius1=r0, radius2=r1, depth=d.length)
        bm.faces.ensure_lookup_table()
        rot = Vector((0, 0, 1)).rotation_difference(d.normalized()).to_matrix().to_4x4()
        bmesh.ops.transform(bm, matrix=Matrix.Translation((a + b) / 2) @ rot, verts=bm.verts)
        # caps by hand (n-gons) so each can be left out
        dn = d.normalized()
        ring0 = [v for v in bm.verts if (v.co - a).dot(dn) < d.length * 0.5]
        ring1 = [v for v in bm.verts if (v.co - a).dot(dn) >= d.length * 0.5]
        for ring, want in ((ring0, caps[0]), (ring1, caps[1])):
            if want and len(ring) > 2:
                c = sum((v.co for v in ring), Vector()) / len(ring)
                ring.sort(key=lambda v: math.atan2(*(self._perp(d, v.co - c))))
                bm.faces.new(ring)
        self.add(bm, mat)

    @staticmethod
    def _perp(d, v):
        d = d.normalized()
        u = d.cross(Vector((0, 1, 0)))
        if u.length < 1e-4:
            u = d.cross(Vector((1, 0, 0)))
        u.normalize()
        w = d.cross(u)
        return v.dot(w), v.dot(u)

    def loft(self, mat, rings, cap0=True, cap1=True, close=True, loop=False):
        """a skin through rings of 3D points (same count each); the ends are closed with n-gons (loop: last ring joins the first, e.g. a torus)"""
        bm = bmesh.new()
        vr = [[bm.verts.new(Vector(p)) for p in ring] for ring in rings]
        n = len(rings[0])
        for i in range(len(rings) if loop else len(rings) - 1):
            i2 = (i + 1) % len(rings)
            for j in range(n if close else n - 1):
                k = (j + 1) % n
                bm.faces.new([vr[i][j], vr[i][k], vr[i2][k], vr[i2][j]])
        if cap0 and not loop:
            bm.faces.new(vr[0])
        if cap1 and not loop:
            bm.faces.new(vr[-1][::-1])
        self.add(bm, mat)

    def lathe(self, mat, profile, seg=16, cx=0.0, cz=0.0, y_of=None):
        """revolve [(radius, y), ...] (bottom to top) about the Y axis through (cx, cz); a radius 0 end is a point"""
        bm = bmesh.new()
        rings = []
        for r, y in profile:
            if r <= 1e-6:
                rings.append([bm.verts.new(Vector((cx, y, cz)))])
            else:
                rings.append([bm.verts.new(Vector((cx + r * math.cos(2 * math.pi * k / seg), y, cz + r * math.sin(2 * math.pi * k / seg)))) for k in range(seg)])
        for i in range(len(rings) - 1):
            a, b = rings[i], rings[i + 1]
            for k in range(seg):
                k2 = (k + 1) % seg
                if len(a) == 1 and len(b) == 1:
                    continue
                if len(a) == 1:
                    bm.faces.new([a[0], b[k2], b[k]])
                elif len(b) == 1:
                    bm.faces.new([a[k], a[k2], b[0]])
                else:
                    bm.faces.new([a[k], a[k2], b[k2], b[k]])
        for ring in (rings[0], rings[-1]):
            if len(ring) > 2:
                bm.faces.new(ring)
        self.add(bm, mat)

    def prism(self, mat, outline, y0, y1, scale0=1.0, scale1=1.0, cap0=True, cap1=True):
        """plan outline [(x, z)] extruded from y0 to y1, scaled about its centre by scale0 → scale1"""
        cx = sum(p[0] for p in outline) / len(outline)
        cz = sum(p[1] for p in outline) / len(outline)

        def ring(y, s):
            return [(cx + (x - cx) * s, y, cz + (z - cz) * s) for x, z in outline]

        self.loft(mat, [ring(y0, scale0), ring(y1, scale1)], cap0, cap1)

    def stack_rings(self, mat, outline, levels, cap0=True, cap1=True):
        """the outline at several heights: levels [(y, scale, dy_corner)] (scale about the centre)"""
        cx = sum(p[0] for p in outline) / len(outline)
        cz = sum(p[1] for p in outline) / len(outline)
        rings = [[(cx + (x - cx) * s, y, cz + (z - cz) * s) for x, z in outline] for y, s in levels]
        self.loft(mat, rings, cap0, cap1)

    def sweep(self, mat, path, section, up=(0, 1, 0), scales=None, cap0=True, cap1=True):
        """
        `section` [(a, b)] swept along the path points; a runs along `side` (= tangent × up), b along `up`'s
        perpendicular to the path. scales: optional per-point factor.
        """
        path = [Vector(p) for p in path]
        rings = []
        up = Vector(up)
        for i, p in enumerate(path):
            t = (path[min(i + 1, len(path) - 1)] - path[max(i - 1, 0)]).normalized()
            side = t.cross(up)
            if side.length < 1e-4:
                side = t.cross(Vector((1, 0, 0)))
            side.normalize()
            nrm = side.cross(t).normalized()
            s = scales[i] if scales else 1.0
            rings.append([tuple(p + side * a * s + nrm * b * s) for a, b in section])
        self.loft(mat, rings, cap0, cap1)

    def tube(self, mat, path, radius, seg=10, scales=None, cap0=True, cap1=True):
        self.sweep(mat, path, circle_pts(0, 0, radius, seg), scales=scales, cap0=cap0, cap1=cap1)

    def torus(self, mat, centre, major, minor, axis='z', seg=32, tube=8):
        """a ring of radius `major` (tube radius `minor`) around `centre`, its axis along game x / y / z"""
        rings = []
        for i in range(seg):
            a = 2 * math.pi * i / seg
            ca, sa = math.cos(a), math.sin(a)
            ring = []
            for j in range(tube):
                b = 2 * math.pi * j / tube
                rr = major + minor * math.cos(b)
                h = minor * math.sin(b)
                p = {'z': (rr * ca, rr * sa, h), 'y': (rr * ca, h, rr * sa), 'x': (h, rr * ca, rr * sa)}[axis]
                ring.append((centre[0] + p[0], centre[1] + p[1], centre[2] + p[2]))
            rings.append(ring)
        self.loft(mat, rings, loop=True)

    def quad(self, mat, pts, flip=False):
        """one flat quad / polygon (an open surface: the winding gives the normal; flip reverses it)"""
        bm = bmesh.new()
        bm.faces.new([bm.verts.new(Vector(p)) for p in pts])
        self.add(bm, mat, closed=False, flip=flip)

    # -- UVs
    def uv(self, mat, fn):
        """fn(position (game frame), face normal) → (u, v) for every corner of the faces with this material"""
        self.bm.normal_update()
        layer = self.bm.loops.layers.uv.verify()
        idx = self.slot(mat)
        for f in self.bm.faces:
            if f.material_index != idx or f in self.uv_done:
                continue
            for lp in f.loops:
                lp[layer].uv = fn(lp.vert.co, f.normal)

    def uv_box(self, mat, scale, offset=(0.0, 0.0)):
        """triplanar projection, `scale` texture repeats per metre"""
        def fn(p, n):
            ax, ay, az = abs(n.x), abs(n.y), abs(n.z)
            if ay >= ax and ay >= az:
                u, v = p.x, p.z
            elif ax >= az:
                u, v = p.z, p.y
            else:
                u, v = p.x, p.y
            return (u * scale + offset[0], v * scale + offset[1])
        self.uv(mat, fn)

    # -- finish
    def count(self):
        return sum(len(f.verts) - 2 for f in self.bm.faces)

    def build(self, sharp=38.0, origin=(0.0, 0.0, 0.0), recentre=None):
        """the object (linked to the scene), its origin at `origin` (game frame); edges sharper than `sharp`° stay hard"""
        bm = self.bm
        bm.normal_update()
        lim = math.radians(sharp)
        for e in bm.edges:
            e.smooth = not (len(e.link_faces) == 2 and e.calc_face_angle(0.0) > lim)
        if recentre:  # move the geometry so that the footprint centre (x, z) is the origin
            bmesh.ops.transform(bm, matrix=Matrix.Translation((-recentre[0], 0, -recentre[1])), verts=bm.verts)
        bmesh.ops.transform(bm, matrix=G2B @ Matrix.Translation((-origin[0], -origin[1], -origin[2])), verts=bm.verts)
        bm.normal_update()
        me = bpy.data.meshes.new(self.name)
        bm.to_mesh(me)
        n = self.count()
        bm.free()
        for m in self.slots:
            me.materials.append(m)
        ob = bpy.data.objects.new(self.name, me)
        bpy.context.scene.collection.objects.link(ob)
        ob.location = B(*origin)
        ob['tris'] = n
        return ob


class _Uv:
    def __init__(self, m, fn, only):
        self.m, self.item = m, (fn, only)

    def __enter__(self):
        self.m.uv_ctx.append(self.item)

    def __exit__(self, *a):
        self.m.uv_ctx.remove(self.item)


class _Xf:
    def __init__(self, m, matrix):
        self.m, self.matrix = m, matrix

    def __enter__(self):
        self.m.stack.append(self.m.stack[-1] @ self.matrix)

    def __exit__(self, *a):
        self.m.stack.pop()


def rot_y(a):
    return Matrix.Rotation(a, 4, 'Y')


def rot_x(a):
    return Matrix.Rotation(a, 4, 'X')


def rot_z(a):
    return Matrix.Rotation(a, 4, 'Z')


def move(x, y, z):
    return Matrix.Translation((x, y, z))


# ---------------------------------------------------------------------------------------------------- export / run

def export_glb(path, objects):
    bpy.ops.object.select_all(action='DESELECT')
    for o in objects:
        o.select_set(True)
    bpy.ops.export_scene.gltf(filepath=path, export_format='GLB', use_selection=True, export_yup=True, export_apply=True,
                              export_materials='EXPORT', export_extras=False, export_cameras=False, export_lights=False,
                              export_image_format='AUTO')


def parse_args():
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    out = render = None
    i = 0
    while i < len(argv):
        if argv[i] == '--out':
            out = argv[i + 1]
            i += 2
        elif argv[i] == '--render':
            render = argv[i + 1]
            i += 2
        else:
            i += 1
    if not out:
        raise SystemExit('usage: blender -t 4 --background --factory-startup --python <script> -- --out <dir> [--render <dir>]')
    os.makedirs(out, exist_ok=True)
    if render:
        os.makedirs(render, exist_ok=True)
    return out, render


class Spec:
    """one prop: output file name, build(out_dir) → objects, and the check views"""

    def __init__(self, glb, build, views):
        self.glb, self.build, self.views = glb, build, views


def run(spec, out=None, render=None):
    if out is None:
        out, render = parse_args()
    clear_scene()
    objs = spec.build(out)
    path = os.path.join(out, spec.glb)
    export_glb(path, objs)
    tris = sum(o['tris'] for o in objs)
    print(f'PROP {spec.glb}: {tris} triangles in {len(objs)} object(s), {os.path.getsize(path) / 1024:.0f} KiB')
    if render:
        stem = spec.glb[:-4]
        for v in spec.views:
            render_glb(path, os.path.join(render, f'{stem}_{v["name"]}.png'), **{k: x for k, x in v.items() if k != 'name'})
    return path


# ---------------------------------------------------------------------------------------------------- check renders

def render_glb(glb, out_png, eye, target, lens=40, night=False, size=(960, 720), samples=48, ground=14.0, lights=None):
    """import the GLB into a clean scene, add sky + sun + ground (or a night sky) and render it with Cycles"""
    clear_scene()
    bpy.ops.import_scene.gltf(filepath=glb)
    scene = bpy.context.scene
    world = bpy.data.worlds.new('sky')
    scene.world = world
    world.use_nodes = True
    nt = world.node_tree
    bg = nt.nodes.get('Background')
    if night:
        bg.inputs['Color'].default_value = (0.02, 0.03, 0.06, 1)
        bg.inputs['Strength'].default_value = 1.0
    else:
        sky = nt.nodes.new('ShaderNodeTexSky')
        sky.sun_elevation = math.radians(38)
        sky.sun_rotation = math.radians(150)
        sky.sun_disc = False
        nt.links.new(sky.outputs['Color'], bg.inputs['Color'])
        bg.inputs['Strength'].default_value = 0.55
    # ground
    if ground:
        bm = bmesh.new()
        bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=ground * 6)
        me = bpy.data.meshes.new('ground')
        bm.to_mesh(me)
        g = bpy.data.objects.new('ground', me)
        scene.collection.objects.link(g)
        gm = bpy.data.materials.new('ground')
        gm.use_nodes = True
        gp = gm.node_tree.nodes['Principled BSDF']
        gp.inputs['Base Color'].default_value = srgb('#4b4a46' if night else '#7d7b76')
        gp.inputs['Roughness'].default_value = 0.92
        me.materials.append(gm)
    sun = bpy.data.objects.new('sun', bpy.data.lights.new('sun', 'SUN'))
    sun.data.energy = 0.25 if night else 2.2
    sun.data.angle = math.radians(2)
    if night:
        sun.data.color = (0.6, 0.7, 1.0)
    sun.rotation_euler = (math.radians(52), 0, math.radians(-38))
    scene.collection.objects.link(sun)
    for (pos, power, colour) in (lights or []):
        lt = bpy.data.objects.new('lt', bpy.data.lights.new('lt', 'POINT'))
        lt.data.energy, lt.data.color = power, colour
        lt.location = B(*pos)
        scene.collection.objects.link(lt)
    cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam'))
    scene.collection.objects.link(cam)
    scene.camera = cam
    cam.location = B(*eye)
    cam.rotation_euler = (B(*target) - B(*eye)).to_track_quat('-Z', 'Y').to_euler()
    cam.data.lens = lens
    cam.data.clip_end = 1000
    scene.render.engine = 'CYCLES'
    scene.cycles.samples = min(samples, 48)
    scene.cycles.use_denoising = True
    scene.cycles.device = 'CPU'
    scene.render.threads_mode = 'FIXED'
    scene.render.threads = 4
    scene.view_settings.view_transform = 'AgX'
    scene.render.resolution_x, scene.render.resolution_y = min(size[0], 1280), min(size[1], 720)
    scene.render.filepath = out_png
    bpy.ops.render.render(write_still=True)
