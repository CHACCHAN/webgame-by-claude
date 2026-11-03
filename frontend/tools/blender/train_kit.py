"""
Building blocks for our own train models in Blender (bpy / bmesh, run by `blender --background --python <train>.py`).

Everything is written in the game's car frame (render/TrainModel.ts): metres, +x = the car's left, +y up (0 = rail
top / road), +z forward, origin halfway between the bogie centres. `B()` turns that into Blender's frame so the glTF
exporter (+Y up) gives the game's axes back: Blender (x, y, z) = game (x, -z, y).

A car is an empty named car0 / car1 / car2 (the nodes TrainModel looks for) with its parts as children:
- the body shell: a cross-section (`Section`) swept along the car, its ends rounded with a bevel; a cab end can be
  raked and bulged; paint zones by height (`Section.zone`) on the sides and the ends;
- decals: thin plates laid on the shell (windows, doors, masks, lamps), projected along x (sides) or z (ends) so they
  follow its curves;
- boxes and cylinders for the roof equipment, the underfloor and the bogies.
"""
import math

import bmesh
import bpy
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree


def B(x, y, z):
    """game car frame → Blender"""
    return Vector((x, -z, y))


def G(v):
    """Blender → game car frame"""
    return v.x, v.z, -v.y


def srgb(hex_colour):
    """'#rrggbb' → linear RGBA (Blender's colour inputs are linear)"""
    h = hex_colour.lstrip('#')
    out = []
    for i in (0, 2, 4):
        c = int(h[i:i + 2], 16) / 255
        out.append(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
    return (*out, 1.0)


def smoothstep(a, b, x):
    t = min(1.0, max(0.0, (x - a) / (b - a)))
    return t * t * (3 - 2 * t)


class Materials:
    """Principled materials by name (exported as glTF PBR; no textures, no transmission)."""

    def __init__(self):
        self.mats = {}

    def add(self, name, colour, metallic=0.0, roughness=0.5, emissive=None, strength=1.0):
        m = bpy.data.materials.new(name)
        m.use_nodes = True
        p = m.node_tree.nodes.get('Principled BSDF')
        p.inputs['Base Color'].default_value = srgb(colour)
        p.inputs['Metallic'].default_value = metallic
        p.inputs['Roughness'].default_value = roughness
        if emissive:
            p.inputs['Emission Color'].default_value = srgb(emissive)
            p.inputs['Emission Strength'].default_value = strength
        self.mats[name] = m
        return m

    def __getitem__(self, name):
        return self.mats[name]


class Part:
    """A mesh under construction (a bmesh with its own material slots)."""

    def __init__(self, name):
        self.name = name
        self.bm = bmesh.new()
        self.slots = []

    def slot(self, mat):
        if mat not in self.slots:
            self.slots.append(mat)
        return self.slots.index(mat)

    def face(self, pts, mat, smooth=False):
        """a face from game-frame points"""
        vs = [self.bm.verts.new(B(*p)) for p in pts]
        f = self.bm.faces.new(vs)
        f.material_index = self.slot(mat)
        f.smooth = smooth
        return f

    def box(self, mat, x0, x1, y0, y1, z0, z1, bevel=0.0, segments=2):
        """an axis-aligned box (game frame), optionally with rounded edges"""
        bm = bmesh.new()
        r = bmesh.ops.create_cube(bm, size=1.0)
        sx, sy, sz = x1 - x0, y1 - y0, z1 - z0
        cx, cy, cz = (x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2
        for v in r['verts']:
            gx, gy, gz = v.co.x * sx + cx, v.co.y * sy + cy, v.co.z * sz + cz
            v.co = B(gx, gy, gz)
        if bevel > 0:
            bmesh.ops.bevel(bm, geom=list(bm.edges), offset=min(bevel, sx / 2.01, sy / 2.01, sz / 2.01), segments=segments,
                            profile=0.5, affect='EDGES', clamp_overlap=True)
        self.merge(bm, mat, smooth=bevel > 0)

    def cylinder(self, mat, centre, radius, length, axis='x', segments=16, cap=True):
        """a cylinder along a game axis"""
        bm = bmesh.new()
        bmesh.ops.create_cone(bm, cap_ends=cap, cap_tris=False, segments=segments, radius1=radius, radius2=radius, depth=length)
        # create_cone runs along Blender z (= game y): turn it onto the wanted game axis
        rot = {'y': Matrix.Identity(4), 'x': Matrix.Rotation(math.pi / 2, 4, 'Y'), 'z': Matrix.Rotation(math.pi / 2, 4, 'X')}[axis]
        bmesh.ops.transform(bm, matrix=Matrix.Translation(B(*centre)) @ rot, verts=bm.verts)
        self.merge(bm, mat, smooth=True)

    def beam(self, mat, a, b, w, h):
        """a square beam from a to b (game frame), w × h across"""
        a, b = B(*a), B(*b)
        d = b - a
        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=1.0)
        bmesh.ops.scale(bm, vec=(w, d.length, h), verts=bm.verts)
        q = Vector((0, 1, 0)).rotation_difference(d.normalized())
        bmesh.ops.transform(bm, matrix=Matrix.Translation((a + b) / 2) @ q.to_matrix().to_4x4(), verts=bm.verts)
        self.merge(bm, mat)

    def merge(self, bm, mat, smooth=False):
        """append another bmesh's faces with one material"""
        idx = self.slot(mat)
        vmap = {}
        for v in bm.verts:
            vmap[v] = self.bm.verts.new(v.co)
        for f in bm.faces:
            nf = self.bm.faces.new([vmap[v] for v in f.verts])
            nf.material_index = idx
            nf.smooth = smooth
        bm.free()

    def build(self, parent, mats):
        mesh = bpy.data.meshes.new(self.name)
        bmesh.ops.remove_doubles(self.bm, verts=self.bm.verts, dist=1e-5)
        self.bm.normal_update()
        self.bm.to_mesh(mesh)
        self.bm.free()
        for m in self.slots:
            mesh.materials.append(mats[m])
        obj = bpy.data.objects.new(self.name, mesh)
        bpy.context.scene.collection.objects.link(obj)
        obj.parent = parent
        return obj


class Section:
    """
    Half cross-section of the body, from the bottom of the side up to the roof's centre line: [(x, y)], x ≥ 0
    decreasing to 0 at the top. `zone(y, ny)` names the paint at a height (ny: how much the face points up).
    """

    def __init__(self, half, zone):
        self.half = half
        self.zone = zone

    def ring(self):
        """the full section, right bottom (−x) over the roof to left bottom (+x)"""
        left = self.half
        right = [(-x, y) for x, y in self.half]
        return right + list(reversed(left[:-1]))


class Shell:
    """
    The body: `section` swept from z = rear to z = front; each end is closed and rounded (`bevel` m), a cab end
    can lean back above `rake_from` (`rake` m per m of height) and bulge forward in the middle (`bulge` m).
    """

    def __init__(self, section, rear, front):
        self.section = section
        self.rear = rear
        self.front = front
        self.bvh = None

    def build(self, part, ends):
        """ends: {'front'|'rear': dict(bevel, segments, rake, rake_from, bulge)}"""
        bm = bmesh.new()
        ring = self.section.ring()
        n = len(ring)
        rings = {}
        for key, z in (('rear', self.rear), ('front', self.front)):
            rings[key] = [bm.verts.new(B(x, y, z)) for x, y in ring]
        # the sides and the roof
        for i in range(n - 1):
            bm.faces.new([rings['rear'][i], rings['rear'][i + 1], rings['front'][i + 1], rings['front'][i]])
        # the end caps: a ladder of quads across the section (pairs at the same height)
        half = len(self.section.half)
        for key in ('front', 'rear'):
            r = rings[key]
            for i in range(half - 1):
                a, b = r[i], r[n - 1 - i]
                c, d = r[n - 2 - i], r[i + 1]
                vs = [a, b, c, d] if c is not d else [a, b, c]
                if key == 'front':
                    vs.reverse()
                bm.faces.new(vs)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        bm.normal_update()
        # round the ends: bevel the edges between each cap and the sides
        for key, z in (('front', self.front), ('rear', self.rear)):
            opt = ends[key]
            edges = []
            for e in bm.edges:
                if not all(abs(G(v.co)[2] - z) < 1e-6 for v in e.verts) or len(e.link_faces) != 2:
                    continue
                if any(any(abs(G(v.co)[2] - z) > 1e-6 for v in f.verts) for f in e.link_faces):
                    edges.append(e)
            bmesh.ops.bevel(bm, geom=edges, offset=opt['bevel'], segments=opt['segments'], profile=0.5, affect='EDGES',
                            clamp_overlap=True)
        # lean back and bulge the cab ends
        hw = max(x for x, _ in self.section.half)
        for v in bm.verts:
            x, y, z = G(v.co)
            for key, sign, zend in (('front', 1, self.front), ('rear', -1, self.rear)):
                opt = ends[key]
                w = smoothstep(zend - sign * opt['bevel'] * 1.05, zend, z) if sign > 0 else smoothstep(zend + opt['bevel'] * 1.05, zend, z)
                if w <= 0:
                    continue
                dz = 0.0
                if opt.get('rake'):
                    dz -= max(0.0, y - opt['rake_from']) * opt['rake'] * w
                if opt.get('bulge'):
                    dz += opt['bulge'] * max(0.0, 1 - (x / hw) ** 2) * w
                v.co = B(x, y, z + sign * dz)
        bm.normal_update()
        # paint by height and slope
        for f in bm.faces:
            c = f.calc_center_median()
            _, y, _ = G(c)
            ny = f.normal.z
            f.material_index = part.slot(self.section.zone(y, ny))
            f.smooth = True
        self.bvh = BVHTree.FromBMesh(bm)
        # keep a copy for projecting decals, then hand the faces to the part
        idx_mats = list(part.slots)
        vmap = {}
        for v in bm.verts:
            vmap[v] = part.bm.verts.new(v.co)
        for f in bm.faces:
            nf = part.bm.faces.new([vmap[v] for v in f.verts])
            nf.material_index = f.material_index
            nf.smooth = True
        bm.free()
        return idx_mats

    def hit(self, origin, direction):
        """first hit on the shell of a ray (game frame) → (point, normal) in the game frame, or None"""
        loc, nrm, _, _ = self.bvh.ray_cast(B(*origin), B(*direction))
        if loc is None:
            return None
        return Vector(G(loc)), Vector(G(nrm))


def decal(part, shell, mat, outline, along, lift=0.004, grid=(6, 4), from_side=1):
    """
    A plate laid on the shell: `outline` is a rectangle (u0, u1, v0, v1) in the plane across the projection axis
    `along` ('x': u = z, v = y, seen from the side +x·from_side; 'z': u = x, v = y, seen from the end
    +z·from_side), split into a grid so it follows curves, `lift` m off the surface.
    """
    u0, u1, v0, v1 = outline
    nu, nv = grid
    pts = []
    for j in range(nv + 1):
        row = []
        for i in range(nu + 1):
            u = u0 + (u1 - u0) * i / nu
            v = v0 + (v1 - v0) * j / nv
            if along == 'x':
                origin, d = (from_side * 5.0, v, u), (-from_side, 0, 0)
            else:
                origin, d = (u, v, from_side * 30.0), (0, 0, -from_side)
            h = shell.hit(origin, d)
            if h is None:
                row.append(None)
                continue
            p, n = h
            if n.dot(Vector(d)) > 0:
                n = -n
            row.append(tuple(p + n * lift))
        pts.append(row)
    for j in range(nv):
        for i in range(nu):
            q = [pts[j][i], pts[j][i + 1], pts[j + 1][i + 1], pts[j + 1][i]]
            if any(p is None for p in q):
                continue
            # face outward, towards the side or end the decal is laid from (u runs against the view on +x and −z)
            if (along == 'x' and from_side > 0) or (along == 'z' and from_side < 0):
                q.reverse()
            part.face(q, mat, smooth=True)


def _laid(shell, u, v, along, from_side, lift):
    """the point (u, v) of a decal's plane laid on the shell, `lift` m off it (None where the ray misses)"""
    if along == 'x':
        origin, d = (from_side * 5.0, v, u), (-from_side, 0, 0)
    else:
        origin, d = (u, v, from_side * 30.0), (0, 0, -from_side)
    hit = shell.hit(origin, d)
    if hit is None:
        return None
    p, n = hit
    if n.dot(Vector(d)) > 0:
        n = -n
    return tuple(p + n * lift)


def rounded_rect(part, shell, mat, cx, cy, w, h, r, along, from_side=1, lift=0.004, segments=4, rings=4):
    """
    A rounded rectangle decal (lamp housings, masks): centre (cx = z or x, cy = y), size, corner radius; in
    concentric rings so a large one follows the shell's curves.
    """
    r = min(r, w / 2, h / 2)
    corners = [(cx + w / 2 - r, cy + h / 2 - r, 0), (cx - w / 2 + r, cy + h / 2 - r, 90), (cx - w / 2 + r, cy - h / 2 + r, 180), (cx + w / 2 - r, cy - h / 2 + r, 270)]
    outline = []
    for ox, oy, a0 in corners:
        for s in range(segments + 1):
            a = math.radians(a0 + 90 * s / segments)
            outline.append((ox + r * math.cos(a), oy + r * math.sin(a)))
    grid = [[_laid(shell, cx + (u - cx) * k / rings, cy + (v - cy) * k / rings, along, from_side, lift) for u, v in outline] for k in range(1, rings + 1)]
    c = _laid(shell, cx, cy, along, from_side, lift)
    # outward: u runs against the view on +x and −z
    flip = (along == 'x' and from_side > 0) or (along == 'z' and from_side < 0)
    n = len(outline)

    def put(pts):
        if any(p is None for p in pts):
            return
        part.face(list(reversed(pts)) if flip else pts, mat, smooth=True)

    for k in range(n):
        put([c, grid[0][k], grid[0][(k + 1) % n]])
        for j in range(rings - 1):
            put([grid[j][k], grid[j + 1][k], grid[j + 1][(k + 1) % n], grid[j][(k + 1) % n]])


def car_empty(name, z_offset=0.0):
    e = bpy.data.objects.new(name, None)
    bpy.context.scene.collection.objects.link(e)
    e.location = B(0, 0, z_offset)
    return e


def clear_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def export_glb(path, roots):
    """the cars (empties car0..car2 with their parts) to a GLB, +Y up"""
    bpy.ops.object.select_all(action='DESELECT')
    for r in roots:
        r.select_set(True)
        for c in r.children_recursive:
            c.select_set(True)
    bpy.ops.export_scene.gltf(filepath=path, export_format='GLB', use_selection=True, export_yup=True, export_apply=True,
                              export_materials='EXPORT', export_extras=False, export_cameras=False, export_lights=False)


def stage_render(path, cars, camera='front34', size=(1280, 720), samples=48):
    """a quick look: sky, ground, sun, a camera on the leading car"""
    scene = bpy.context.scene
    world = bpy.data.worlds.new('sky') if not scene.world else scene.world
    scene.world = world
    world.use_nodes = True
    nt = world.node_tree
    bg = nt.nodes.get('Background') or nt.nodes.new('ShaderNodeBackground')
    sky = nt.nodes.new('ShaderNodeTexSky')
    try:
        sky.sky_type = 'MULTIPLE_SCATTERING'
    except TypeError:
        pass
    sky.sun_elevation = math.radians(35)
    sky.sun_rotation = math.radians(150)
    nt.links.new(sky.outputs['Color'], bg.inputs['Color'])
    bg.inputs['Strength'].default_value = 0.09
    out = nt.nodes.get('World Output') or nt.nodes.new('ShaderNodeOutputWorld')
    nt.links.new(bg.outputs['Background'], out.inputs['Surface'])
    # ground
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=120)
    me = bpy.data.meshes.new('ground')
    bm.to_mesh(me)
    g = bpy.data.objects.new('ground', me)
    scene.collection.objects.link(g)
    gm = bpy.data.materials.new('ground')
    gm.use_nodes = True
    gm.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = srgb('#7d7b76')
    gm.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value = 0.9
    me.materials.append(gm)
    # sun
    sun = bpy.data.objects.new('sun', bpy.data.lights.new('sun', 'SUN'))
    sun.data.energy = 1.5
    sun.data.angle = math.radians(2)
    sun.rotation_euler = (math.radians(50), 0, math.radians(-35))
    scene.collection.objects.link(sun)
    cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam'))
    scene.collection.objects.link(cam)
    scene.camera = cam
    views = {
        # game frame: eye, target, lens
        'front34': ((6.5, 2.4, 17.5), (0, 1.9, 5.0), 40),
        'side': ((24.0, 2.2, -9.0), (0, 1.9, -9.0), 28),
        'front': ((0.0, 2.1, 21.0), (0, 1.9, 8.0), 50),
        'rear34': ((-6.0, 3.2, -52.0), (0, 1.8, -36.0), 40),
        'roof': ((7.5, 9.0, 10.0), (0, 2.5, -2.0), 32),
        'under': ((4.5, 0.6, 12.0), (0, 0.6, 5.0), 30),
    }
    eye, target, lens = views[camera]
    cam.location = B(*eye)
    d = B(*target) - B(*eye)
    cam.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    cam.data.lens = lens
    scene.render.engine = 'CYCLES'
    scene.cycles.samples = samples
    scene.cycles.use_denoising = True
    scene.cycles.device = 'CPU'
    scene.view_settings.view_transform = 'Standard'
    scene.view_settings.exposure = 0.0
    scene.render.resolution_x, scene.render.resolution_y = size
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)
