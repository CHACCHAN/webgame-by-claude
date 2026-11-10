"""
lamps.py (Blender; the Supra): the lamps and openings against the outlines traced on the photos (lamps.json).

  back: a ray from each photo's solved camera through every traced point (silhouette points left out) onto the uncut,
        fitted, posed body; the hit is taken back through the pose, the FFD field and the nose stretch to the design
        frame, then into the frame the part is laid out in (supra_parts.OUTLINES: u, v of a 'surf' outline; for a
        'disc' the traced ellipse's centre, on the disc's plane, and its mean radius). Right-hand parts are mirrored
        to the left first. Writes {key: {photo_side: [[u, v], ...]}} (discs: [u, v, r]).
  ids:  the model's outlines as flat patches lifted off the body ('surf') and discs where the parts are ('disc'), one
        flat colour each (left / right apart), rendered from every solved camera: <out>/<photo>_lampsA.png (outlines),
        <out>/<photo>_lampsB.png (discs), <out>/<photo>_lampsC.png (outlines inside others: OVERLAID),
        <out>/<photo>_lampsW.png (the rear wing itself, the body black in front of it: key wing_C) and
        <out>/lamps_palette.json, for lampscore.py.

  blender.sh -t 8 -b --factory-startup --python lamps.py -- <back|ids> <fit.json> <lamps.json> <out> [--photos a,b]
      [--ffd lattice.json]
"""
import json, math, os, sys

sys.dont_write_bytecode = True
REPO_CARS = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..'))
sys.path.insert(0, REPO_CARS)

import bpy
import numpy as np
from mathutils import Matrix, Vector

import supra_kit as K
import supra_parts as P
import supra_details as DT
import supra_body as BD
import supra_ffd as FF

argv = sys.argv[sys.argv.index('--') + 1:]
mode, fitp, lampsp, out = argv[:4]
os.makedirs(out, exist_ok=True)
only = argv[argv.index('--photos') + 1].split(',') if '--photos' in argv else None
fit = json.load(open(fitp))
camdata = json.load(open(fit['cams']))
cams, poses = camdata['cams'], camdata.get('pose', {})
traces = json.load(open(lampsp))['photos']
names = [n for n in fit['photos'] if (only is None or n in only)]
lat = FF.Lattice.load(argv[argv.index('--ffd') + 1]) if '--ffd' in argv else FF.Lattice.load()

CAP = {}
_orig_build = DT.build
OVERLAID = {'ind'}      # outlines lying inside another one (the indicator in the corner opening): a pass of their own


def _proxies(body, mats, bvh):
    """flat patches / discs for every registered outline, left and right, one material each"""
    cols = {}
    rng = np.random.default_rng(3)
    for key, e in sorted(P.OUTLINES.items()):
        sides = ('C',) if key.endswith('_C') else ('L', 'R')
        for side in sides:
            name = f'lampid_{key}' if side == 'C' else f'lampid_{key}_{side}'
            m = bpy.data.materials.new(name)
            col = tuple(float(v) for v in rng.uniform(0.15, 1.0, 3))
            m.diffuse_color = col + (1.0,)
            cols[name] = col
            part = K.Part(name)
            if e[0] == 'surf':
                _, fr, outline = e
                P.surface_patch(part, bvh, K.resample(list(outline), 96, closed=True), fr, m, lift=0.008, n_rings=6)
            else:
                _, c, n, r = e
                DT._disc(part, m, Vector(c) + Vector(n) * 0.007, n, r, seg=40)   # over the domed lenses
            if side == 'R':
                whole = K.Part(name)
                whole.absorb(part, mirror=True)
                part.bm.free()
                part = whole
            ob = part.build(body, weld=0)
            ob['lampid'] = 'C' if key in OVERLAID else ('A' if e[0] == 'surf' else 'B')
    CAP['cols'] = cols


if not hasattr(DT, 'build_wing'):
    # the older layout (wing inside 'details', deformed with the body): build it as an object of its own
    _orig_wing = DT.wing

    def _wing(part, mats, bvh):
        wp = K.Part('wing')
        _orig_wing(wp, mats, bvh)
        CAP['wingpart'] = wp
    DT.wing = _wing


def _patched(body, mats, bvh, bvh_cut, count):
    _orig_build(body, mats, bvh, bvh_cut, count)
    if 'wingpart' in CAP:
        CAP['wingpart'].build(body)
    CAP['bvh'] = bvh
    if mode == 'back':
        CAP['rayshell'] = BD.shell('rayshell', mats).build(body, weld=0)
    else:
        _proxies(body, mats, bvh)


DT.build = _patched
K.clear_scene()
mats = P.materials()
root = K.empty('supra')
P.build_all(root, mats, ffd=lat)
body = bpy.data.objects['body']
bpy.context.view_layer.update()
body_m0 = body.matrix_basis.copy()


def basis(yaw, pitch, roll):
    d = np.array([math.sin(yaw) * math.cos(pitch), math.sin(pitch), math.cos(yaw) * math.cos(pitch)])
    r = np.cross(d, [0, 1, 0])
    r /= np.linalg.norm(r)
    u = np.cross(r, d)
    c, s = math.cos(roll), math.sin(roll)
    return d, c * r + s * u, -s * r + c * u


def unpose(p, name):
    """posed game point / vector -> the body's rest frame (game)"""
    q = poses.get(name, {})
    dy, th = q.get('dy', 0.0), math.radians(q.get('pitch_deg', 0.0))
    c, s = math.cos(th), math.sin(th)

    def f(v, point=True):
        x, y, z = v
        if point:
            y -= dy
        return np.array([x, c * y - s * z, s * y + c * z])
    return f


def deform(G):
    G1 = G + P.nose_disp(G) if P.NOSE_EXT else G
    return G1 + lat.displace(G1)


def undeform(G2):
    G0 = G2.copy()
    for _ in range(30):
        G0 = G0 - (deform(G0) - G2)
    return G0


def frame_uv(e, G0):
    """design-frame point(s) -> the part's (u, v)"""
    if e[0] == 'surf':
        fr = e[1]
        c, e1, e2 = np.array(fr.c), np.array(fr.e1), np.array(fr.e2)
    else:
        return None
    return np.stack([(G0 - c) @ e1, (G0 - c) @ e2], 1)


if mode == 'back':
    from mathutils.bvhtree import BVHTree
    rs = CAP['rayshell']
    bvh = K.bvh_of(rs)
    res = {}
    for name in names:
        c = cams[name]
        C = np.array(c[:3], float)
        d, r, u = basis(*c[3:6])
        f, (W, H) = c[6], c[7]
        up = unpose(None, name)
        for key, tr in traces.get(name, {}).items():
            parts = key.split('_')
            side = parts[1]
            lk = parts[0] + ('_' + parts[2] if len(parts) > 2 else '') + ('_C' if side == 'C' else '')
            if lk not in P.OUTLINES:
                print('no outline for', key)
                continue
            e = P.OUTLINES[lk]

            def cast(px, py):
                dv = d + r * (px - W / 2) / f + u * (H / 2 - py) / f
                o = up(C)
                dd = up(dv, point=False)
                dd = dd / np.linalg.norm(dd)
                hit = bvh.ray_cast(K.B(*o), K.B(*dd) - K.B(0, 0, 0), 50.0)
                if hit[0] is None:
                    return None, None
                return np.array(K.G(hit[0])), dd
            if 'poly' in tr:
                pts = []
                for q in tr['poly']:
                    if len(q) > 2 and q[2]:
                        continue
                    h, _ = cast(q[0], q[1])
                    if h is not None:
                        pts.append(h)
                G0 = undeform(np.array(pts))
                if side == 'R':
                    G0[:, 0] *= -1
                uv = frame_uv(e, G0)
                res.setdefault(lk, {})[f'{name}_{side}'] = [[round(a, 4), round(b, 4)] for a, b in uv]
            else:
                cx, cy, rx, ry = tr['ell']
                cpos, nrm, rad = np.array(e[1]), np.array(e[2]), e[3]
                cdef = deform(cpos[None] * ([-1, 1, 1] if side == 'R' else [1, 1, 1]))[0]
                ndef = nrm * ([-1, 1, 1] if side == 'R' else [1, 1, 1])

                def on_plane(px, py):
                    dv = d + r * (px - W / 2) / f + u * (H / 2 - py) / f
                    o = up(C)
                    dd = up(dv, point=False)
                    t = (cdef - o) @ ndef / (dd @ ndef)
                    return o + dd * t
                ctr = on_plane(cx, cy)
                rim = [on_plane(cx + rx * math.cos(a), cy + ry * math.sin(a)) for a in np.linspace(0, 2 * math.pi, 16, endpoint=False)]
                rad_m = float(np.mean([np.linalg.norm(p - ctr) for p in rim]))
                G0 = undeform(ctr[None])[0]
                if side == 'R':
                    G0[0] *= -1
                # the disc centre's offset from the model's, in the head / tail lamp frame
                base = 'hl' if lk.startswith('hl') else 'tl'
                uv = frame_uv(P.OUTLINES[base], G0[None])[0]
                uv0 = frame_uv(P.OUTLINES[base], cpos[None])[0]
                res.setdefault(lk, {})[f'{name}_{side}'] = [round(float(uv[0]), 4), round(float(uv[1]), 4), round(rad_m, 4),
                                                           'model', round(float(uv0[0]), 4), round(float(uv0[1]), 4), round(rad, 4)]
    json.dump(res, open(os.path.join(out, 'back.json'), 'w'), indent=1)
    for k, v in res.items():
        for ph, pts in v.items():
            if isinstance(pts[0], list):
                a = np.array(pts)
                print(f'{k:8s} {ph:8s} u {a[:, 0].min():+.3f}..{a[:, 0].max():+.3f}  v {a[:, 1].min():+.3f}..{a[:, 1].max():+.3f}  n {len(a)}')
            else:
                print(f'{k:8s} {ph:8s} photo u {pts[0]:+.3f} v {pts[1]:+.3f} r {pts[2]:.3f}   model u {pts[4]:+.3f} v {pts[5]:+.3f} r {pts[6]:.3f}')
    sys.exit(0)

# ids
sc = bpy.context.scene
sc.render.engine = 'BLENDER_WORKBENCH'
sc.render.film_transparent = True
sc.view_settings.view_transform = 'Standard'
sc.display.render_aa = 'OFF'
sc.render.image_settings.file_format = 'PNG'
sc.render.image_settings.color_mode = 'RGBA'
sh = sc.display.shading
sh.light = 'FLAT'
sh.color_type = 'MATERIAL'
sh.show_object_outline = False
cam = bpy.data.objects.new('lampcam', bpy.data.cameras.new('lampcam'))
sc.collection.objects.link(cam)
sc.camera = cam
cam.data.clip_start = 0.05
cam.data.clip_end = 1000
cam.data.sensor_fit = 'HORIZONTAL'
cam.data.sensor_width = 36
for m in bpy.data.materials:
    if not m.name.startswith('lampid_'):
        m.diffuse_color = (0, 0, 0, 1)
wm = bpy.data.materials.new('lampid_wing_C')
wm.diffuse_color = (0.9, 0.35, 0.1, 1.0)
CAP['cols']['lampid_wing_C'] = (0.9, 0.35, 0.1)
wing_ob = bpy.data.objects.get('wing')
if wing_ob is not None:
    for sl in wing_ob.material_slots:
        sl.material = wm
proxies = [o for o in bpy.data.objects if 'lampid' in o.keys()]


def Bv(x, y, z):
    return Vector((x, -z, y))


def _srgb(c):
    return int(round(255 * (12.92 * c if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055)))


json.dump({k: [_srgb(v) for v in col] for k, col in CAP['cols'].items()}, open(os.path.join(out, 'lamps_palette.json'), 'w'))
for name in names:
    c = cams[name]
    W, H = c[7]
    d, r, u = basis(*c[3:6])
    M = Matrix((Bv(*r), Bv(*u), -Bv(*d))).transposed()
    cam.matrix_world = Matrix.Translation(Bv(*c[:3])) @ M.to_4x4()
    cam.data.lens = c[6] * 36 / W
    sc.render.resolution_x, sc.render.resolution_y = int(W), int(H)
    sc.render.resolution_percentage = 100
    q = poses.get(name, {})
    dy, th = q.get('dy', 0.0), math.radians(q.get('pitch_deg', 0.0))
    body.matrix_basis = Matrix.Translation(Bv(0, dy, 0)) @ Matrix.Rotation(-th, 4, "X") @ body_m0
    for tag in 'ABCW':
        if tag == 'W' and wing_ob is None:
            continue
        for o in proxies:
            o.hide_render = o['lampid'] != tag
        wm.diffuse_color = (0.9, 0.35, 0.1, 1.0) if tag == 'W' else (0, 0, 0, 1)
        sc.render.filepath = os.path.join(out, f'{name}_lamps{tag}.png')
        bpy.ops.render.render(write_still=True)
body.matrix_basis = body_m0
print('IDS done', names)
