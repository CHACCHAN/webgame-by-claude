"""
The cockroach's skeleton and its scuttle cycle (game frame, real mm; see roach_geom).

Gait: the alternating tripod. Tripod A (left front, right middle, left hind) is on the ground from phase 0 to DUTY,
tripod B half a cycle later. A planted foot moves backwards at exactly STRIDE per cycle (the game plays the clip by
the distance covered), so it stays put on the road; a swinging foot lifts in an arc and reaches forward.

Each leg is solved analytically every frame: the tarsus lies on the ground (stance) or hangs (swing), the coxa
swings fore and aft with the foot, femur and tibia meet the ankle by two-bone IK with the knee up and out.
Bones: Y along the segment; legs Z = the flexor (ventral) side, body bones Z = up.
"""
import math

import bpy
import numpy as np
from mathutils import Matrix, Quaternion, Vector

import roach_anatomy as A
import roach_body as RB
from roach_geom import R_GB, B, frame, frame_matrix, rot, unit

UP = np.array((0.0, 1.0, 0.0))
MX = np.diag((-1.0, 1.0, 1.0))
THORAX_PIVOT = np.array((0.0, 4.9, -8.0))
SEGMENTS = ('coxa', 'femur', 'tibia', 'tarsus1', 'tarsus2')


def leg_bone(side, k, seg):
    return f'leg_{"L" if side > 0 else "R"}{k}_{seg}'


# ---------------------------------------------------------------- body motion

def body_pose(t):
    """thorax rotation and translation at cycle time t (0..1): a slight yaw / roll with each tripod, a bob per step"""
    w = 2 * math.pi * t
    yaw = math.radians(1.7) * math.sin(w - 0.5)
    roll = math.radians(1.2) * math.sin(w + 0.4)
    pitch = math.radians(0.5) * math.cos(2 * w + 0.6)
    R = rot(UP, yaw) @ rot((0, 0, 1), roll) @ rot((1, 0, 0), pitch)
    d = np.array((0.2 * math.sin(w + 0.2), 0.14 * math.cos(2 * w + 0.3), 0.08 * math.cos(2 * w)))
    return R, d


def apply_body(R, d, p):
    return THORAX_PIVOT + d + R @ (np.asarray(p, float) - THORAX_PIVOT)


# ---------------------------------------------------------------- legs

def ease(s):
    return s * s * s * (s * (s * 6 - 15) + 10)


class Leg:
    """a left leg's kinematics; right legs are solved mirrored and half a cycle later"""

    def __init__(self, k):
        self.k = k
        self.p = A.LEGS[k]
        p = self.p
        self.L1 = p['tarsi'][0]
        self.L2 = sum(p['tarsi'][1:])
        self.sweep = A.STRIDE * A.DUTY
        self.g = unit((p['heading'][0], 0.0, p['heading'][1]))
        self.r_t = p['tarsus_r'] + 0.26        # tarsus centreline height on the ground (the pads touch y = 0)
        self.warn = 0.0

    def foot(self, phase):
        """claw-tip target, tarsus directions (ta1, ta2), offset of the foot along z from its neutral spot"""
        p = self.p
        D = A.DUTY
        fx, fz = p['foot']
        phase %= 1.0
        if phase < D:
            u = phase / D
            dz = self.sweep * (0.5 - u)
            lift, droop, extra = 0.0, 0.0, 0.0
            s = None
        else:
            s = (phase - D) / (1 - D)
            dz = -self.sweep / 2 + self.sweep * ease(s)
            lift = p['lift'] * math.sin(math.pi * s) ** 1.3
            droop = math.radians(38) * math.sin(math.pi * min(1.0, s * 1.15)) ** 1.0
            extra = math.radians(18) * math.sin(math.pi * s)
        P = np.array((fx + (0.35 * math.sin(math.pi * s) if s is not None else 0.0), self.r_t + lift, fz + dz))
        beta = math.radians(p['ankle']) + extra
        g = self.g
        d2 = unit(g * math.cos(droop) - UP * math.sin(droop))
        d1 = unit(g * math.cos(beta) - UP * math.sin(beta))
        return P, d1, d2, dz

    def solve(self, phase, R, d):
        """armature-space frames (origin, X, Y, Z) of the five segments for a left leg"""
        p = self.p
        P, d1, d2, dz = self.foot(phase)
        Q = P - d2 * self.L2
        Ank = Q - d1 * self.L1
        H = apply_body(R, d, p['hip'])
        # coxa: swings fore / aft with the foot about the body's up axis
        alpha = p['swing'] * (dz / (self.sweep / 2))
        c0 = unit(p['coxa_dir'])
        cdir = R @ (rot(UP, -alpha) @ c0)
        bup = R @ UP
        T = H + cdir * p['coxa']
        fr = {'coxa': (H, *frame(cdir, -bup))}
        # femur + tibia: two-bone IK, knee towards the pole
        Lf, Lt = p['femur'], p['tibia']
        v = Ank - T
        dist = np.linalg.norm(v)
        lo, hi = abs(Lf - Lt) + 0.05, Lf + Lt - 0.03
        if dist > hi or dist < lo:
            self.warn = max(self.warn, (dist - hi) if dist > hi else (lo - dist))
            dist = min(max(dist, lo), hi)
        u = v / np.linalg.norm(v)
        pole = R @ unit(p['pole'])
        w = unit(pole - np.dot(pole, u) * u)
        ca = (Lf * Lf + dist * dist - Lt * Lt) / (2 * Lf * dist)
        sa = math.sqrt(max(0.0, 1 - ca * ca))
        K = T + Lf * (ca * u + sa * w)
        A_ = T + u * dist                      # the ankle actually reached
        Yf = unit(K - T)
        Yt = unit(A_ - K)
        # flexor sides in the leg's plane (well defined even with the leg straight)
        cb = (dist - Lf * ca) / Lt
        sb = Lf * sa / Lt
        Zf = unit(sa * u - ca * w)
        Zt = unit(-sb * u - cb * w)
        fr['femur'] = (T, np.cross(Yf, Zf), Yf, Zf)
        fr['tibia'] = (K, np.cross(Yt, Zt), Yt, Zt)
        # tarsus: from the ankle reached to the planted foot
        Y1 = unit(Q - A_)
        fr['tarsus1'] = (A_, *frame(Y1, -UP))
        fr['tarsus2'] = (Q, *frame(d2, -UP))
        # keep the X axes on the same (front) side for every segment of the leg
        for key in ('coxa', 'tarsus1', 'tarsus2'):
            o, X, Y, Z = fr[key]
            fr[key] = (o, X, Y, Z)
        return fr


LEGS = {k: Leg(k) for k in (1, 2, 3)}


def leg_phase(side, k, t):
    """phase of a leg at cycle time t: tripod A (L1, R2, L3) lands at phase 0, tripod B half a cycle later"""
    name = ('L' if side > 0 else 'R') + str(k)
    return (t + (0.0 if name in A.TRIPOD_A else 0.5)) % 1.0


def mirror_frame(fr):
    o, X, Y, Z = fr
    return (MX @ o, -(MX @ X), MX @ Y, MX @ Z)


def leg_frames(side, k, t, rest=False):
    leg = LEGS[k]
    R, d = (np.eye(3), np.zeros(3)) if rest else body_pose(t)
    phase = A.DUTY / 2 if rest else leg_phase(side, k, t)
    if side > 0:
        return leg.solve(phase, R, d)
    # right leg: solve the left leg in the mirrored world, mirror back
    Rm, dm = MX @ R @ MX, MX @ d
    fr = leg.solve(phase, Rm, dm)
    return {key: mirror_frame(v) for key, v in fr.items()}


# ---------------------------------------------------------------- the skeleton

def bone_specs():
    """[(name, parent, head, tail, z axis)] in the game frame (mm), rest pose"""
    specs = [('root', None, (0, 0, 0), (0, 0, 4.0), (0, 1, 0)),
             ('thorax', 'root', tuple(THORAX_PIVOT), tuple(THORAX_PIVOT + (0, 0, 4.0)), (0, 1, 0))]
    hf = RB.HF
    neck = hf.centre(0.12) - hf.Z * 0.4
    specs.append(('head', 'thorax', tuple(neck), tuple(neck + hf.Y * 3.5), tuple(hf.Z)))
    # the eyes' centre, between the compound eyes (the game puts its headlight eyes here)
    cL = RB.eye_frame(1)[0]
    cR = RB.eye_frame(-1)[0]
    ec = (cL + cR) / 2
    specs.append(('head_eyes', 'head', tuple(ec), tuple(ec + np.array((0, 0, 1.2))), (0, 1, 0)))
    for side in (1, -1):
        sd = 'L' if side > 0 else 'R'
        names = RB.ant_names(side)
        parent = 'head'
        for nm, (h, tl) in zip(names, RB.antenna_bone_frames(side)):
            specs.append((nm, parent, tuple(h), tuple(tl), (0, 1, 0)))
            parent = nm
        j = RB.max_palp_joints(side)
        specs.append((f'palp_{sd}_0', 'head', tuple(j[0]), tuple(j[2]), tuple(hf.Z)))
        specs.append((f'palp_{sd}_1', f'palp_{sd}_0', tuple(j[2]), tuple(j[5]), tuple(hf.Z)))
        j = RB.lab_palp_joints(side)
        specs.append((f'lpalp_{sd}', 'head', tuple(j[0]), tuple(j[3]), tuple(hf.Z)))
    specs.append(('abdomen', 'thorax', (0, 4.8, -11.0), (0, 4.8, -20.0), (0, 1, 0)))
    for side in (1, -1):
        sd = 'L' if side > 0 else 'R'
        j = RB.cercus_joints(side)
        specs.append((f'cercus_{sd}', 'abdomen', tuple(j[0]), tuple(j[-1]), (0, 1, 0)))
    for side in (1, -1):
        for k in (1, 2, 3):
            fr = leg_frames(side, k, 0.0, rest=True)
            parent = 'thorax'
            for seg in SEGMENTS:
                o, X, Y, Z = fr[seg]
                L = {'coxa': A.LEGS[k]['coxa'], 'femur': A.LEGS[k]['femur'], 'tibia': A.LEGS[k]['tibia'],
                     'tarsus1': LEGS[k].L1, 'tarsus2': LEGS[k].L2}[seg]
                nm = leg_bone(side, k, seg)
                specs.append((nm, parent, tuple(o), tuple(o + Y * L), tuple(Z)))
                parent = nm
    return specs


def build_armature(specs):
    arm_data = bpy.data.armatures.new('roach_rig')
    arm = bpy.data.objects.new('roach', arm_data)
    bpy.context.scene.collection.objects.link(arm)
    bpy.context.view_layer.objects.active = arm
    arm.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    eb = arm_data.edit_bones
    for name, parent, h, t, z in specs:
        b = eb.new(name)
        b.head = B(*h)
        b.tail = B(*t)
        b.align_roll(R_GB @ Vector(z))
        if parent:
            b.parent = eb[parent]
        b.use_connect = False
        b.use_deform = True
    bpy.ops.object.mode_set(mode='OBJECT')
    return arm


# ---------------------------------------------------------------- the cycle

def local_rot(axis, ang):
    """a 4×4 rotation about a bone-local axis ('X', 'Y', 'Z')"""
    return Matrix.Rotation(ang, 4, axis)


def body_tree_motion(name, t):
    """bone-local rotation (4×4) of the non-leg bones at cycle time t"""
    w = 2 * math.pi * t
    I = Matrix.Identity(4)
    if name == 'head':
        return local_rot('X', math.radians(2.2) * math.sin(2 * w + 1.1)) @ local_rot('Z', math.radians(1.5) * math.sin(w))
    if name.startswith('antenna_'):
        _, sd, i = name.split('_')
        i = int(i)
        side = 1 if sd == 'L' else -1
        ph = 0.0 if side > 0 else math.pi * 0.85
        # a wave running out along the whip: each bone lags the one before it
        amp = math.radians(7.0 if i == 0 else 4.2)
        sweep = amp * math.sin(w + ph - 0.75 * i)
        lift = math.radians(2.5 if i == 0 else 1.6) * math.sin(2 * w + ph - 0.6 * i + 0.4)
        return local_rot('X', lift) @ local_rot('Z', sweep * side * -1.0)
    if name.startswith('palp_'):
        _, sd, i = name.split('_')
        ph = 0.0 if sd == 'L' else 1.9
        tw = math.sin(3 * w + ph) ** 3                  # quick twitches
        return local_rot('X', math.radians(7 if i == '1' else 4) * tw + math.radians(3) * math.sin(2 * w + ph))
    if name.startswith('lpalp_'):
        ph = 0.5 if name.endswith('L') else 2.4
        return local_rot('X', math.radians(6) * math.sin(4 * w + ph) ** 3)
    if name.startswith('cercus_'):
        ph = 0.0 if name.endswith('L') else 2.1
        return local_rot('X', math.radians(4) * math.sin(w + ph)) @ local_rot('Z', math.radians(3) * math.sin(2 * w + ph))
    if name == 'abdomen':
        return local_rot('X', math.radians(0.35) * math.sin(2 * w + 0.8))
    return I


def to_bl(fr):
    o, X, Y, Z = fr
    return frame_matrix(o, X, Y, Z)


def pose_matrices(arm, t):
    """armature-space pose matrices of every bone at cycle time t"""
    bones = arm.data.bones
    rest = {b.name: b.matrix_local.copy() for b in bones}
    pose = {}
    R, d = body_pose(t)
    legs = {}
    for side in (1, -1):
        for k in (1, 2, 3):
            fr = leg_frames(side, k, t)
            for seg in SEGMENTS:
                legs[leg_bone(side, k, seg)] = to_bl(fr[seg])
    for b in bones:                       # parents come before children
        n = b.name
        if b.parent is None:
            pose[n] = rest[n]
            continue
        pn = b.parent.name
        if n == 'thorax':
            o = THORAX_PIVOT + d
            m = rest[n].to_3x3()
            Rb = R_GB @ Matrix(R.tolist()) @ R_GB.transposed()
            M = (Rb @ m).to_4x4()
            M.translation = B(*o)
            pose[n] = M
        elif n in legs:
            pose[n] = legs[n]
        else:
            pose[n] = pose[pn] @ (rest[pn].inverted() @ rest[n]) @ body_tree_motion(n, t)
    return rest, pose


def animate(arm, frames=A.FRAMES):
    """key the cycle on frames 0..frames (the last equal to the first)"""
    scene = bpy.context.scene
    scene.render.fps = frames
    scene.render.fps_base = 1.0
    scene.frame_start = 0
    scene.frame_end = frames
    action = bpy.data.actions.new('scuttle')
    arm.animation_data_create()
    arm.animation_data.action = action
    pbs = arm.pose.bones
    for pb in pbs:
        pb.rotation_mode = 'QUATERNION'
    prev = {}
    keys = []
    for f in range(frames):
        t = f / frames
        rest, pose = pose_matrices(arm, t)
        vals = {}
        for b in arm.data.bones:
            n = b.name
            if b.parent is None:
                basis = Matrix.Identity(4)
            else:
                pn = b.parent.name
                basis = (rest[pn].inverted() @ rest[n]).inverted() @ pose[pn].inverted() @ pose[n]
            loc, q, _ = basis.decompose()
            if n in prev and prev[n].dot(q) < 0:
                q = -q
            prev[n] = q
            vals[n] = (loc, q)
        keys.append(vals)
    keys.append(keys[0])
    for f, vals in enumerate(keys):
        for n, (loc, q) in vals.items():
            pb = pbs[n]
            pb.location = loc
            pb.rotation_quaternion = q
            pb.keyframe_insert('location', frame=f, group=n)
            pb.keyframe_insert('rotation_quaternion', frame=f, group=n)
    # the quaternion of the closing key must match the first one's sign as well as value (equal frames)
    for fc in _fcurves(action):
        for kp in fc.keyframe_points:
            kp.interpolation = 'LINEAR'
    scene.frame_set(0)
    return action


def _fcurves(action):
    if hasattr(action, 'fcurves') and len(getattr(action, 'fcurves', [])) > 0:
        return list(action.fcurves)
    out = []
    for layer in getattr(action, 'layers', []):
        for strip in layer.strips:
            for bag in strip.channelbags:
                out.extend(bag.fcurves)
    return out


def leg_warnings():
    return {k: LEGS[k].warn for k in LEGS}
