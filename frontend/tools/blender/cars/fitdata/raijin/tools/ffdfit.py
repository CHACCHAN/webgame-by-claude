"""
ffdfit.py (Blender; adapted from fitdata/s15/tools/ffdfit.py for the raijin): fit the body's FFD lattice, the photo cameras and the body pose per photo to the photo silhouettes.

  OPENBLAS_NUM_THREADS=4 blender.sh -t 4 -b --factory-startup --python ffdfit.py -- <fit.json> <ffd_in|-> <ffd_out>
      <cams_out> [--iters N] [--ls 20] [--l0 1] [--every 3] [--seg 6,6,16] [--nocam] [--noffd] [--photos a,b]

Each iteration: deform the body, render every camera's silhouette, take the model outline's signed distance to the
photo mask's outline (ignore zones skipped), cast a ray just inside each outline pixel to find the surface point that
makes it (body: deformable, posed; wheels: rigid, they anchor the cameras), linearise the outline shift in the image
normal direction with respect to the lattice, the camera (position, yaw, pitch, roll, log focal) and the body pose
(dy, pitch; fixed on the reference photo), and solve one damped Gauss-Newton step (Huber weights; lattice smooth,
small and mirror-symmetric). Residuals are in % of the car's bbox width; each photo has the same total weight.
"""
import json, math, os, sys, time

sys.dont_write_bytecode = True
REPO_CARS = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..'))
sys.path.insert(0, REPO_CARS)
sys.path.insert(0, os.environ.get('PYFIT', ''))   # where OpenCV / Pillow for Blender's Python live

import bpy
import numpy as np
import cv2
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

import raijin_ffd as FF

argv = sys.argv[sys.argv.index('--') + 1:]
fit = json.load(open(argv[0]))
ffd_in, ffd_out, cams_out = argv[1], argv[2], argv[3]


def opt(k, d):
    return type(d)(argv[argv.index(k) + 1]) if k in argv else d


ITERS = opt('--iters', 6)
LS = opt('--ls', 20.0)
L0 = opt('--l0', 1.0)
LC = opt('--lc', 1.0)
EVERY = opt('--every', 3)
HUBER = opt('--huber', 1.0)
STEP = opt('--step', 1.0)
SEG = tuple(int(v) for v in opt('--seg', '6,6,16').split(','))
NOCAM = '--nocam' in argv
NOFFD = '--noffd' in argv
NOPOSE = '--nopose' in argv
REF = opt("--ref", "")
FIXCAM = [x for x in opt("--fixcam", "").split(",") if x]
SDY = opt("--sdy", 0.05)
SPITCH = opt("--spitch", 0.01)               # body pitch prior (rad)
only = opt('--photos', '')
names = [n for n in fit['photos'] if not only or n in only.split(',')]
camdata = json.load(open(fit['cams']))
cams = {n: np.array(camdata['cams'][n][:7], float) for n in names}
for n in names:
    cams[n][6] = math.log(cams[n][6])
sizes = {n: camdata['cams'][n][7] for n in names}
pose = {n: np.array([camdata.get('pose', {}).get(n, {}).get('dy', 0.0),
                     math.radians(camdata.get('pose', {}).get(n, {}).get('pitch_deg', 0.0))]) for n in names}

# ---------------------------------------------------------------- build the car (undeformed)
import raijin
import raijin_kit as K
K.clear_scene()
root, mats, _ = raijin.build({'paint': '#9a9ea4', 'ffd': False})
body = bpy.data.objects['body']
pods = []
bpy.context.view_layer.update()


def under(o, anc):
    while o is not None:
        if o == anc:
            return True
        o = o.parent
    return False


pod_meshes = set(o for h in pods for o in h.children_recursive)
body_objs = [o for o in bpy.data.objects if o.type == 'MESH' and under(o, body)]      # pods folded: deformed in place
wheel_objs = [o for o in bpy.data.objects if o.type == 'MESH' and not under(o, body) and under(o, root)]
M0, V0 = {}, {}
for o in body_objs:
    me = o.data
    co = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get('co', co)
    M = np.array(o.matrix_world)
    M0[o.name] = M
    V0[o.name] = FF.blender_to_game(co.reshape(-1, 3) @ M[:3, :3].T + M[:3, 3])
hinge0 = {h.name: FF.blender_to_game(np.array([h.matrix_world.translation]))[0] for h in pods}
hinge_loc0 = {h.name: h.location.copy() for h in pods}

# rigid wheels (game frame) and the body's triangles
WV, WT = [], []
off = 0
for o in wheel_objs:
    me = o.data
    co = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get('co', co)
    M = np.array(o.matrix_world)
    WV.append(FF.blender_to_game(co.reshape(-1, 3) @ M[:3, :3].T + M[:3, 3]))
    me.calc_loop_triangles()
    t = np.empty(len(me.loop_triangles) * 3, int)
    me.loop_triangles.foreach_get('vertices', t)
    WT.append(t.reshape(-1, 3) + off)
    off += len(WV[-1])
WV, WT = np.concatenate(WV), np.concatenate(WT)
BT = []
off = 0
for o in body_objs:
    me = o.data
    me.calc_loop_triangles()
    t = np.empty(len(me.loop_triangles) * 3, int)
    me.loop_triangles.foreach_get('vertices', t)
    BT.append(t.reshape(-1, 3) + off)
    off += len(V0[o.name])
BT = np.concatenate(BT)
VB0 = np.concatenate([V0[o.name] for o in body_objs])
# parts the build keeps rigid (ffd_rigid: door mirrors) take the field's weights at their anchor, per side
WSRC = VB0.copy()
_s = 0
for o in body_objs:
    _n = len(V0[o.name])
    if 'ffd_rigid' in o:
        A = np.array(list(o['ffd_rigid']), float)
        seg = WSRC[_s:_s + _n]
        WSRC[_s:_s + _n] = np.where(seg[:, :1] >= 0, A[None], (A * np.array([-1, 1, 1]))[None])
        print('rigid', o.name, _n, 'verts at', np.round(A, 3).tolist())
    _s += _n
NB = len(VB0)
TRIS = np.concatenate([BT, WT + NB])
ISB = np.concatenate([np.ones(len(BT), bool), np.zeros(len(WT), bool)])
TRI_LIST = [tuple(t) for t in TRIS.tolist()]

L = FF.Lattice.load(ffd_in) if ffd_in != '-' else None
if L is None:
    L = FF.Lattice(lo=(-1.0, -0.1, -2.45), hi=(1.0, 1.45, 2.35), seg=SEG)
print('lattice', L.n, L.h, 'body verts', NB, 'tris', len(BT), 'wheel tris', len(WT))
NCP = int(np.prod(L.n))
WI, WW = L.weights(WSRC)

# lattice parameters: the half i >= centre; the centre column has no x offset
nx = L.n[0]
ic = nx // 2
FP = np.full(NCP * 3, -1, int)
FS = np.zeros(NCP * 3)
npar = 0
for i in range(ic, nx):
    for j in range(L.n[1]):
        for k in range(L.n[2]):
            for c in range(3):
                if i == ic and c == 0:
                    continue
                f = ((i * L.n[1] + j) * L.n[2] + k) * 3 + c
                FP[f], FS[f] = npar, 1.0
                npar += 1
for i in range(ic):
    for j in range(L.n[1]):
        for k in range(L.n[2]):
            for c in range(3):
                fm = (((nx - 1 - i) * L.n[1] + j) * L.n[2] + k) * 3 + c
                f = ((i * L.n[1] + j) * L.n[2] + k) * 3 + c
                if FP[fm] >= 0:
                    FP[f], FS[f] = FP[fm], (-1.0 if c == 0 else 1.0)
NL = npar
# catalogue pins: --length L (nose-to-tail), --width W (widest point), --height H (roof): the deformed shell's extreme
# rest vertices are held at the catalogue size, so the field puts the photos' misfit elsewhere
PINS = []


def _row(P_, comp, sg=1.0, row=None):
    row = np.zeros(npar) if row is None else row
    idx_, w_ = L.weights(P_[None])
    for k_, wv_ in zip(idx_[0], w_[0]):
        f_ = k_ * 3 + comp
        if FP[f_] >= 0:
            row[FP[f_]] += sg * wv_ * FS[f_]
    return row


_sh = [o for o in body_objs if o.name == 'body_shell'][0]
_V = V0[_sh.name]
LEN, WID, HGT = opt('--length', 0.0), opt('--width', 0.0), opt('--height', 0.0)
if LEN > 0:
    pn, pt = _V[np.argmax(_V[:, 2])], _V[np.argmin(_V[:, 2])]
    PINS.append(('length', _row(pt, 2, -1.0, _row(pn, 2)), LEN - (pn[2] - pt[2]), LEN))
    print('length pin: nose', np.round(pn, 3).tolist(), 'tail', np.round(pt, 3).tolist(), 'rest', round(pn[2] - pt[2], 4), 'target', LEN)
if WID > 0:
    pw = _V[np.argmax(_V[:, 0])]
    PINS.append(('width', _row(pw, 0, 2.0), WID - 2 * pw[0], WID))
    print('width pin at', np.round(pw, 3).tolist(), 'target', WID)
if HGT > 0:
    ph = _V[np.argmax(_V[:, 1])]
    PINS.append(('height', _row(ph, 1), HGT - ph[1], HGT))
    print('height pin at', np.round(ph, 3).tolist(), 'target', HGT)
CAM0 = {n: NL + 9 * q for q, n in enumerate(names)}
NPAR = NL + 9 * len(names)
print('params', NL, NPAR)


def lat_params():
    x = np.zeros(NL)
    C = L.c.reshape(-1)
    sel = (FP >= 0) & (FS > 0)
    x[FP[sel]] = C[sel]
    return x


def set_lat(x):
    C = np.where(FP >= 0, x[np.maximum(FP, 0)] * FS, 0.0)
    L.c = C.reshape(*L.n, 3)


def reg_normal():
    """sum over second differences (cm) of (row)^T (row), as a dense NL x NL matrix"""
    n = L.n
    rows_i, rows_v = [], []
    for ax in range(3):
        for i in range(n[0]):
            for j in range(n[1]):
                for k in range(n[2]):
                    a = [i, j, k]
                    if a[ax] == 0 or a[ax] == n[ax] - 1:
                        continue
                    for c in range(3):
                        ii, vv = [], []
                        for d, wv in ((-1, 1.0), (0, -2.0), (1, 1.0)):
                            b = list(a)
                            b[ax] += d
                            f = ((b[0] * n[1] + b[1]) * n[2] + b[2]) * 3 + c
                            ii.append(max(FP[f], 0))
                            vv.append(wv * FS[f] / 0.01 if FP[f] >= 0 else 0.0)
                        rows_i.append(ii)
                        rows_v.append(vv)
    I, V = np.array(rows_i), np.array(rows_v)
    A = np.zeros((NL, NL))
    np.add.at(A, (I[:, :, None], I[:, None, :]), V[:, :, None] * V[:, None, :])
    return A


RTR = reg_normal()


def deformed():
    C = L.c.reshape(-1, 3)
    return VB0 + (C[WI] * WW[:, :, None]).sum(1)


def apply_deform(VD):
    s = 0
    for o in body_objs:
        n = len(V0[o.name])
        Wb = FF.game_to_blender(VD[s:s + n])
        Mi = np.linalg.inv(M0[o.name])
        o.data.vertices.foreach_set('co', (Wb @ Mi[:3, :3].T + Mi[:3, 3]).ravel())
        o.data.update()
        s += n


# ---------------------------------------------------------------- render setup
sc = bpy.context.scene
sc.render.engine = 'BLENDER_WORKBENCH'
sc.render.film_transparent = True
sc.view_settings.view_transform = 'Standard'
sc.display.render_aa = 'OFF'
sc.render.image_settings.file_format = 'PNG'
sc.render.image_settings.color_mode = 'RGBA'
sh = sc.display.shading
sh.light = 'FLAT'
sh.color_type = 'SINGLE'
sh.single_color = (1, 1, 1)
sh.show_object_outline = False
cam = bpy.data.objects.new('silcam', bpy.data.cameras.new('silcam'))
sc.collection.objects.link(cam)
sc.camera = cam
cam.data.clip_start = 0.05
cam.data.clip_end = 1000
cam.data.sensor_fit = 'HORIZONTAL'
cam.data.sensor_width = 36
body_m0 = body.matrix_basis.copy()
TMP = os.environ.get('FFDTMP', os.path.join(os.getcwd(), 'ffdtmp'))   # scratch renders
os.makedirs(TMP, exist_ok=True)


def basis(yaw, pitch, roll):
    d = np.array([math.sin(yaw) * math.cos(pitch), math.sin(pitch), math.cos(yaw) * math.cos(pitch)])
    r = np.cross(d, [0, 1, 0])
    r /= np.linalg.norm(r)
    u = np.cross(r, d)
    c, s = math.cos(roll), math.sin(roll)
    return d, c * r + s * u, -s * r + c * u


def project(c, P, W, H):
    d, r, u = basis(*c[3:6])
    f = math.exp(c[6])
    Q = P - c[:3]
    z = Q @ d
    return np.stack([W / 2 + f * (Q @ r) / z, H / 2 - f * (Q @ u) / z], 1)


def Bv(v):
    return Vector((v[0], -v[2], v[1]))


# anchors: the bundle adjustment's image points with their 3D positions (wheel geometry, plates, body features;
# work/anchors.py). They tie each camera to the points while the silhouettes refine what the points leave open.
W_RIM = opt('--wrim', 100.0)
ANCH = json.load(open(fit['anchors'])) if fit.get('anchors') and W_RIM > 0 else {}
RIMS = {n: np.array(ANCH[n], float) if ANCH.get(n) else None for n in names}
print('anchors', {n: (0 if v is None else len(v)) for n, v in RIMS.items()}, 'weight', W_RIM)


# --bodyanchors: the body features (plates, emblems, lamp tips) ride on the body: their rest positions are the BA's
# points pulled back through the starting field, and the field moves them (and is pulled by them) during the fit
BODYANCH = '--bodyanchors' in argv
REST = {}
for n in names:
    if RIMS[n] is not None:
        Q = RIMS[n]
        R0 = Q[:, :3].copy()
        b = Q[:, 7] > 0
        if BODYANCH and b.any():
            q = R0[b].copy()
            for _ in range(25):
                q = R0[b] - L.displace(q)
            R0[b] = q
            if Q.shape[1] > 8:          # rigid groups: one shift for the group (from its centre)
                for gid in np.unique(Q[:, 8]):
                    sel = (Q[:, 8] == gid) & b
                    if gid > 0 and sel.any():
                        c0 = Q[sel, :3].mean(0)
                        q0 = c0.copy()
                        for _ in range(25):
                            q0 = c0 - L.displace(q0[None])[0]
                        R0[sel] = Q[sel, :3] - (c0 - q0)
        REST[n] = R0


def anchor_src(n):
    """where each body anchor samples the field: its own rest point, or its rigid group's centre (plates keep their size)"""
    Q = RIMS[n]
    src = REST[n].copy()
    if Q.shape[1] > 8:
        for gid in np.unique(Q[:, 8]):
            if gid > 0:
                sel = Q[:, 8] == gid
                src[sel] = REST[n][sel].mean(0)
    return src


def anchor_pts(n):
    """the anchors' current 3D positions (body frame, before the pose)"""
    Q = RIMS[n]
    P = Q[:, :3].copy()
    if BODYANCH:
        b = Q[:, 7] > 0
        P[b] = REST[n][b] + L.displace(anchor_src(n)[b])
    return P


def anchor_res(n, c, ps, bw, dP=None):
    Q = RIMS[n]
    W, H = sizes[n]
    P = anchor_pts(n)
    b = Q[:, 7] > 0
    if dP is not None:
        P = P + dP
    P[b] = posed(P[b], ps[0], ps[1])
    return ((project(c, P, W, H) - Q[:, 3:5]) * Q[:, 5:7] * 100.0 / bw).ravel()

masks = {}
for n in names:
    masks[n] = cv2.imread(fit['photos'][n]['mask'], cv2.IMREAD_GRAYSCALE)


def outline(m):
    m8 = m.astype(np.uint8)
    return (m8 - cv2.erode(m8, np.ones((3, 3), np.uint8))).astype(bool)


def render(n):
    c = cams[n]
    W, H = sizes[n]
    d, r, u = basis(*c[3:6])
    M = Matrix((Bv(r), Bv(u), -Bv(d))).transposed()
    cam.matrix_world = Matrix.Translation(Bv(c[:3])) @ M.to_4x4()
    cam.data.lens = math.exp(c[6]) * 36 / W
    sc.render.resolution_x, sc.render.resolution_y = int(W), int(H)
    sc.render.resolution_percentage = 100
    dy, th = pose[n]
    body.matrix_basis = Matrix.Translation(Bv((0, dy, 0))) @ Matrix.Rotation(-th, 4, "X") @ body_m0
    sc.render.filepath = os.path.join(TMP, f'{n}_sil.png')
    bpy.ops.render.render(write_still=True)
    body.matrix_basis = body_m0
    im = cv2.imread(sc.render.filepath, cv2.IMREAD_UNCHANGED)
    return im[:, :, 3] > 127


def posed(G, dy, th):
    c, s = math.cos(th), math.sin(th)
    return np.stack([G[:, 0], G[:, 1] * c + G[:, 2] * s + dy, G[:, 2] * c - G[:, 1] * s], 1)


def stats(n, R):
    Pm = masks[n]
    Pp = Pm > 192
    valid = (Pm < 64) | (Pm > 192)
    iou = (R & Pp & valid).sum() / max(1, ((R | Pp) & valid).sum())
    ys, xs = np.nonzero(R)
    bw = xs.max() - xs.min() + 1
    eR = outline(R) & valid
    eP = outline(Pp) & valid
    # distances to the whole photo outline (its uncertain stretches too: a model pixel just outside an ignore band
    # must not jump to a far valid stretch); sums over a fixed count so pixels entering / leaving the ignore bands
    # do not change the cost by themselves
    dtP = cv2.distanceTransform((~outline(Pp)).astype(np.uint8), cv2.DIST_L2, 5)
    py_, px_ = np.nonzero(eR)
    e = dtP[py_, px_] * np.where(Pp[py_, px_], -1.0, 1.0)
    dtR = cv2.distanceTransform((~outline(R)).astype(np.uint8), cv2.DIST_L2, 5)
    dp = dtR[eP] / bw * 100
    nref = max(1, int(eP.sum()))
    cost = (huber(e / bw * 100).sum() + huber(dp).sum()) / nref
    if '--probe' in argv:
        print(f'   {n} one-sided {huber(e / bw * 100).mean():.4f} back {huber(dp).mean():.4f} n {len(e)}')
    return iou, bw, py_, px_, e, float(cost)


def huber(x, k=1.0):
    a = np.abs(x)
    return np.where(a < k, 0.5 * a * a, k * (a - 0.5 * k))


def iteration(solve=True):
    VD = deformed()
    apply_deform(VD)
    report = {}
    A = np.zeros((NPAR, NPAR))
    g = np.zeros(NPAR)
    for n in names:
        c = cams[n]
        W, H = sizes[n]
        f = math.exp(c[6])
        d, r, u = basis(*c[3:6])
        R = render(n)
        iou, bw, py_, px_, e, cost = stats(n, R)
        rim_res = None
        if RIMS[n] is not None:
            rim_res = anchor_res(n, c, pose[n], bw)
            cost += 0.5 * W_RIM * float((rim_res ** 2).sum()) / 1000.0
        ea = np.abs(e) / bw * 100
        report[n] = (iou, float(ea.mean()), float(np.percentile(ea, 95)), cost)
        if not solve:
            continue
        s = 100.0 / bw                                   # pixels -> % of the car width
        Pm = masks[n]
        valid = (Pm < 64) | (Pm > 192)
        eP = outline(Pm > 192) & valid
        Rf = cv2.GaussianBlur(R.astype(np.float32), (0, 0), 2.0)
        gx = cv2.Sobel(Rf, cv2.CV_32F, 1, 0, ksize=3)[py_, px_]
        gy = cv2.Sobel(Rf, cv2.CV_32F, 0, 1, ksize=3)[py_, px_]
        nl = np.hypot(gx, gy) + 1e-9
        MX, MY = -gx / nl, -gy / nl                      # outward image normal of the model silhouette
        # forward rows: model outline pixel -> nearest photo outline (signed); back rows: photo outline pixel ->
        # nearest model outline pixel, distance along that pixel's normal
        fwd = np.arange(0, len(py_), EVERY)
        tgt_f = -e[fwd] * s
        eRall = np.zeros(R.shape, bool)
        eRall[py_, px_] = True
        idmap = np.full(R.shape, -1, int)
        idmap[py_, px_] = np.arange(len(py_))
        _, lab = cv2.distanceTransformWithLabels((~eRall).astype(np.uint8), cv2.DIST_L2, 5, labelType=cv2.DIST_LABEL_PIXEL)
        lab2k = np.full(lab.max() + 1, -1, int)
        lab2k[lab[py_, px_]] = np.arange(len(py_))
        qy, qx = np.nonzero(eP)
        qs = np.arange(0, len(qy), EVERY)
        qy, qx = qy[qs], qx[qs]
        kq = lab2k[lab[qy, qx]]
        okq = kq >= 0
        qy, qx, kq = qy[okq], qx[okq], kq[okq]
        tgt_b = ((qx - px_[kq]) * MX[kq] + (qy - py_[kq]) * MY[kq]) * s
        need = np.unique(np.concatenate([fwd, kq]))
        pos = np.full(len(py_), -1, int)
        pos[need] = np.arange(len(need))
        dy, th = pose[n]
        VP = np.concatenate([posed(VD, dy, th), WV])
        bvh = BVHTree.FromPolygons([Vector(v) for v in VP.tolist()], TRI_LIST, all_triangles=True)
        Cc = Vector(c[:3])
        hitp = np.zeros((len(need), 3))
        hitt = np.full(len(need), -1, int)
        for q, k in enumerate(need):
            uu, vv = px_[k] + 0.5 - 1.5 * MX[k], py_[k] + 0.5 - 1.5 * MY[k]
            ray = d + ((uu - W / 2) / f) * r - ((vv - H / 2) / f) * u
            loc, nrm, ti, dist = bvh.ray_cast(Cc, Vector(ray / np.linalg.norm(ray)))
            if loc is not None:
                hitp[q] = loc
                hitt[q] = ti
        hit = hitt >= 0
        p = hitp
        ti = np.maximum(hitt, 0)
        isb = ISB[ti] & hit
        mx, my = MX[need], MY[need]
        Q = p - c[:3]
        z = Q @ d
        z = np.where(np.abs(z) < 1e-6, 1e-6, z)
        Jx = f * (r[None] - ((Q @ r) / z)[:, None] * d[None]) / z[:, None]
        Jy = -f * (u[None] - ((Q @ u) / z)[:, None] * d[None]) / z[:, None]
        gpt = mx[:, None] * Jx + my[:, None] * Jy         # pixels per metre of point motion, along m
        Jn = np.zeros((len(need), NPAR))                  # d(outline shift along m, %) / d(params) per needed pixel
        if not NOCAM:
            x0 = project(c, p, W, H)
            for q, h in enumerate((1e-3, 1e-3, 1e-3, 1e-4, 1e-4, 1e-4, 1e-4)):
                c2 = c.copy()
                c2[q] += h
                dx = (project(c2, p, W, H) - x0) / h
                Jn[:, CAM0[n] + q] = (mx * dx[:, 0] + my * dx[:, 1]) * s
        bi = np.nonzero(isb)[0]
        if len(bi):
            a_, b_, c_ = TRIS[ti[bi]].T
            A_, B_, C_ = VP[a_], VP[b_], VP[c_]
            v0, v1, v2 = B_ - A_, C_ - A_, p[bi] - A_
            d00, d01, d11 = (v0 * v0).sum(1), (v0 * v1).sum(1), (v1 * v1).sum(1)
            d20, d21 = (v2 * v0).sum(1), (v2 * v1).sum(1)
            den = d00 * d11 - d01 * d01
            den = np.where(np.abs(den) < 1e-14, 1e-14, den)
            bb = (d11 * d20 - d01 * d21) / den
            cb = (d00 * d21 - d01 * d20) / den
            ab = 1 - bb - cb
            p0 = WSRC[a_] * ab[:, None] + WSRC[b_] * bb[:, None] + WSRC[c_] * cb[:, None]
            pd = VD[a_] * ab[:, None] + VD[b_] * bb[:, None] + VD[c_] * cb[:, None]
            cth, sth = math.cos(th), math.sin(th)
            Rth = np.array([[1, 0, 0], [0, cth, sth], [0, -sth, cth]])
            gb = gpt[bi] @ Rth                              # along m per metre of body-frame motion
            if not NOFFD:
                idx, w = L.weights(p0)
                fl = (idx[:, :, None] * 3 + np.arange(3)[None, None, :]).reshape(len(bi), -1)
                val = (w[:, :, None] * gb[:, None, :]).reshape(len(bi), -1) * s
                pp = FP[fl]
                ok = pp >= 0
                rr = np.repeat(bi[:, None], fl.shape[1], 1)
                np.add.at(Jn, (rr[ok], pp[ok]), (val * FS[fl])[ok])
            if not NOPOSE and n != REF:
                Jn[bi, CAM0[n] + 7] = gpt[bi, 1] * s
                dpth = np.stack([np.zeros(len(bi)), -pd[:, 1] * sth + pd[:, 2] * cth, -pd[:, 2] * sth - pd[:, 1] * cth], 1)
                Jn[bi, CAM0[n] + 8] = (gpt[bi] * dpth).sum(1) * s
        if '--fdtest' in argv:
            uy = np.zeros(NPAR)
            for f_ in range(NCP * 3):
                if f_ % 3 == 1 and FP[f_] >= 0:
                    uy[FP[f_]] = 0.01
            a1 = Jn[bi] @ uy
            a2 = Jn[bi, CAM0[n] + 7] * 0.01
            print(n, 'uniform +1cm y: lattice-pred mean', a1.mean(), 'pose-dy-pred mean', a2.mean(), 'corr', np.corrcoef(a1, a2)[0, 1],
                  'sum w', np.abs(WW.sum(1) - 1).max())
            ux = np.zeros(NPAR)
            print('  wsum at hits', L.weights(p0)[1].sum(1).min(), L.weights(p0)[1].sum(1).max())
        for rows, tgt in ((pos[fwd], tgt_f), (pos[kq], tgt_b)):
            okr = hit[rows]
            rows, tgt = rows[okr], tgt[okr]
            if not len(rows):
                continue
            hub = np.minimum(1.0, HUBER / np.maximum(np.abs(tgt), 1e-9))
            wrow = np.sqrt(hub * 1000.0 / len(rows))
            Jr = Jn[rows] * wrow[:, None]
            A += Jr.T @ Jr
            g += Jr.T @ (tgt * wrow)
        if rim_res is not None:
            Jm = np.zeros((len(rim_res), NPAR))
            for q, h in enumerate((1e-3, 1e-3, 1e-3, 1e-4, 1e-4, 1e-4, 1e-4, 1e-4, 1e-4)):
                if (q < 7 and NOCAM) or (q >= 7 and (NOPOSE or n == REF)):
                    continue
                c2, p2 = c.copy(), pose[n].copy()
                if q < 7:
                    c2[q] += h
                else:
                    p2[q - 7] += h
                Jm[:, CAM0[n] + q] = (anchor_res(n, c2, p2, bw) - rim_res) / h
            bq = np.nonzero(RIMS[n][:, 7] > 0)[0]
            if BODYANCH and not NOFFD and len(bq):
                idx_, w_ = L.weights(anchor_src(n)[bq])
                for comp in range(3):
                    dP = np.zeros((len(RIMS[n]), 3))
                    dP[bq, comp] = 1e-4
                    Jc = ((anchor_res(n, c, pose[n], bw, dP) - rim_res) / 1e-4).reshape(-1, 2)
                    f_ = idx_ * 3 + comp
                    ok_ = FP[f_] >= 0
                    for t in range(2):
                        rows = np.repeat((2 * bq + t)[:, None], 64, 1)
                        np.add.at(Jm, (rows[ok_], FP[f_][ok_]), (w_ * FS[f_] * Jc[bq, t][:, None])[ok_])
            Jm *= math.sqrt(W_RIM)
            A += Jm.T @ Jm
            g += Jm.T @ (-rim_res * math.sqrt(W_RIM))
        report[n] = report[n][:4] + (float(np.sqrt((rim_res ** 2).sum() / max(1, (RIMS[n][:, 5:7] > 0).sum())) * bw / 100) if rim_res is not None else 0.0,)
        if '--probe' in argv:
            print(n, 'fwd', len(fwd), 'back', len(kq), 'need', len(need), 'hit', int(hit.sum()), 'body', int(isb.sum()))
    return report, (A, g)


def solve(A, g, lam, lamL):
    A = A.copy()
    g = g.copy()
    xl = lat_params()
    if NOFFD:
        A[:NL, :NL] += np.eye(NL) * 1e6
    else:
        A[:NL, :NL] += LS * RTR + (L0 + lamL) * np.eye(NL) / 0.01 ** 2
        g[:NL] -= LS * RTR @ xl + L0 * xl / 0.01 ** 2
    if not NOFFD:
        for _, row, rb, _t in PINS:
            r_ = row @ xl - rb
            A[:NL, :NL] += 1e7 * np.outer(row, row)
            g[:NL] -= 1e7 * row * r_
    sig = np.array([0.02, 0.02, 0.02, 0.002, 0.002, 0.002, 0.005, 0.01, 0.002])
    for n in names:
        o = CAM0[n]
        A[o:o + 9, o:o + 9] += lam[n] * np.diag(1 / sig ** 2)
        if n == REF or NOPOSE:
            A[o + 7:o + 9, o + 7:o + 9] += np.eye(2) * 1e9
        else:
            # absolute prior on the body pose (ride height and pitch relative to the wheels)
            A[o + 7, o + 7] += 1 / SDY ** 2
            A[o + 8, o + 8] += 1 / SPITCH ** 2
            g[o + 7] -= pose[n][0] / SDY ** 2
            g[o + 8] -= pose[n][1] / SPITCH ** 2
        if NOCAM:
            A[o:o + 7, o:o + 7] += np.eye(7) * 1e9
        if n in FIXCAM:
            # a camera without rim anchors (q02) can trade itself against the body's shape: held where it is
            A[o:o + 9, o:o + 9] += np.eye(9) * 1e9
    return np.linalg.solve(A, g)


def objective(rep, n=None):
    """the solved objective in the normal equations' units: data (1000 x the per-photo cost) + priors"""
    ns = names if n is None else [n]
    tot = sum(1000.0 * rep[q][3] for q in ns)
    for q in ns:
        if q != REF and not NOPOSE:
            tot += 0.5 * (pose[q][0] / SDY) ** 2 + 0.5 * (pose[q][1] / SPITCH) ** 2
    if n is None and not NOFFD:
        xl = lat_params()
        tot += 0.5 * (LS * xl @ RTR @ xl + L0 * xl @ xl / 0.01 ** 2)
        for _, row, rb, _t in PINS:
            tot += 0.5 * 1e7 * (row @ xl - rb) ** 2
    return tot


def get_state():
    return lat_params(), {n: cams[n].copy() for n in names}, {n: pose[n].copy() for n in names}


def set_state(st, only=None):
    xl, cs, ps = st
    if only is None:
        set_lat(xl)
    for n in (names if only is None else only):
        cams[n] = cs[n].copy()
        pose[n] = ps[n].copy()


def fmt(rep):
    return '  '.join(f'{n} {v[0]:.4f}/{v[1]:.2f}/{v[2]:.2f}' + (f'/r{v[4]:.2f}' if len(v) > 4 else '') for n, v in rep.items())


t0 = time.time()
lam = {n: LC for n in names}
lamL = opt("--laml", 0.1)
rep, (A, g) = iteration()
print(f'start            {fmt(rep)}', flush=True)
if '--probe' in argv:
    st = get_state()
    dx = solve(A, g, lam, lamL)
    tot0 = sum(v[3] for v in rep.values())
    # predicted linear-model reduction of the weighted squared residual vs actual cost
    for sc_ in (0.1, 0.3, 1.0):
        for part in ('lat', 'both'):
            set_state(st)
            if part in ('lat', 'both'):
                set_lat(st[0] + sc_ * dx[:NL])
            if part in ('cam', 'both'):
                for n in names:
                    o = CAM0[n]
                    cams[n] = st[1][n] + sc_ * dx[o:o + 7]
                    pose[n] = st[2][n] + sc_ * dx[o + 7:o + 9]
            r2, _ = iteration(solve=False)
            import shutil
            for n in names:
                shutil.copy(os.path.join(TMP, f'{n}_sil.png'), os.path.join(TMP, f'{n}_sil_{sc_}_{part}.png'))
            tot = sum(v[3] for v in r2.values())
            print(f'scale {sc_:.1f} {part:4s} total {tot0:.4f}->{tot:.4f}', '  '.join(f'{n} {rep[n][3]:.3f}->{r2[n][3]:.3f}' for n in names), flush=True)
    set_state(st)
    sys.exit(0)
for it in range(ITERS):
    st = get_state()
    obj_prev = {n: objective(rep, n) for n in names}
    obj_prev['all'] = objective(rep)
    dx = solve(A, g, lam, lamL)
    set_lat(st[0] + dx[:NL])
    for n in names:
        o = CAM0[n]
        cams[n] = st[1][n] + dx[o:o + 7]
        pose[n] = st[2][n] + dx[o + 7:o + 9]
    rep2, (A2, g2) = iteration()
    if NOFFD:
        bad = [n for n in names if objective(rep2, n) > obj_prev[n]]
        good = [n for n in names if n not in bad]
        for n in bad:
            lam[n] *= 4
        for n in good:
            lam[n] = max(lam[n] * 0.5, 0.05)
        if bad:
            set_state(st, only=bad)
            rep2, (A2, g2) = iteration()
    else:
        c0 = obj_prev['all']
        c1 = objective(rep2)
        bad = names if c1 > c0 else []
        if bad:
            lamL *= 4
            for n in names:
                lam[n] *= 4
            set_state(st)
            rep2, (A2, g2) = iteration() if it == ITERS - 1 else (rep, (A, g))
        else:
            lamL = max(lamL * 0.5, 0.01)
            for n in names:
                lam[n] = max(lam[n] * 0.5, 0.05)
    rep, A, g = rep2, A2, g2
    print(f'iter {it} ({time.time() - t0:.0f}s) max|dc| {np.abs(dx[:NL]).max():.4f} rej {",".join(bad) or "-"}  {fmt(rep)}', flush=True)
print(f'final            {fmt(rep)}')
print('max |c|', np.abs(L.c).max())
for nm, row, rb, tg in PINS:
    print(nm, round(float(tg + row @ lat_params() - rb), 4))
L.save(ffd_out)
out = {'cams': {n: [*cams[n][:6].tolist(), math.exp(cams[n][6]), sizes[n]] for n in names},
       'pose': {n: {'dy': round(float(pose[n][0]), 4), 'pitch_deg': round(math.degrees(pose[n][1]), 3)} for n in names},
       'silhouette': {n: {'iou': round(float(v[0]), 4), 'mean_pct': round(v[1], 3), 'p95_pct': round(v[2], 3)} for n, v in rep.items()},
       'from': fit['cams']}
json.dump(out, open(cams_out, 'w'), indent=1)
for n in names:
    c = cams[n]
    print(n, 'cam', np.round(c[:3], 3).tolist(), 'yaw/pitch/roll', np.round(np.degrees(c[3:6]), 2).tolist(), 'f', round(math.exp(c[6]), 1),
          'pose dy', round(float(pose[n][0]), 4), 'pitch', round(math.degrees(pose[n][1]), 3))
