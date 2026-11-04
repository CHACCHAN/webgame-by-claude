"""
The six legs (game frame, real mm). Each segment is built round its bone in the rest pose and weighted rigidly to it,
as an insect's exoskeleton is: the flat coxa, the femur (with the trochanter at its base and spines on its ventral
margins), the spiny tibia (rows of strong spines pointing towards the foot and a crown at its end), the basitarsus
and tarsomeres 2–5 with pale pads underneath, two claws and the arolium. Left legs are built, right legs mirrored.
"""
import math

import numpy as np

import roach_anatomy as A
import roach_rig as RG
from roach_geom import Part, cap_ts, end_profile, frame, unit
from roach_tex import LAYOUT, leg_rect


def spine(part, base, d, length, r0, side_dir, region, weight, n=4, curve=0.12):
    """a tapered, slightly curved spine from `base` (just inside the surface) along d"""
    d = unit(d)
    X, Y, Z = frame(d, side_dir)
    rows, vv = [], []
    for i, u in enumerate((0.0, 0.4, 0.78)):
        r = r0 * (1 - u) ** 0.9 + 0.012
        c = base + d * (length * u) + Z * (curve * length * u * u)
        th = np.arange(n) / n * 2 * math.pi
        rows.append(c + np.outer(r * np.cos(th), X) + np.outer(r * np.sin(th), Z))
        vv.append(u)
    tip = base + d * length + Z * (curve * length)
    part.loft(rows, region, weight, pole0=base - d * 0.05, pole1=tip, v_of=vv)


def seg_tube(part, fr, length, hx, hz, region, weight, t0=0.0, t1=1.0, cap0=0.12, cap1=0.1, n=12, n_mid=10,
             offset=None, bend=None, n_cap=3):
    """a leg segment: elliptic sections (half widths hx(t), hz(t) along X / Z) from t0·length to t1·length"""
    o, X, Y, Z = fr
    ts = cap_ts(n_mid, cap0, cap1, n_cap=n_cap)
    th = np.arange(n) / n * 2 * math.pi + math.pi / n
    rows = []
    for t in ts:
        e = end_profile(t, cap0, cap1)
        s = t0 + (t1 - t0) * t
        ox, oz = offset(s) if offset else (0.0, 0.0)
        c = o + Y * (s * length) + X * ox + Z * oz
        ax, az = hx(s) * e, hz(s) * e
        pts = c + np.outer(ax * np.cos(th), X) + np.outer(az * np.sin(th), Z)
        rows.append(pts)
    c0 = o + Y * (t0 * length)
    c1 = o + Y * (t1 * length)
    if offset:
        c0 = c0 + X * offset(t0)[0] + Z * offset(t0)[1]
        c1 = c1 + X * offset(t1)[0] + Z * offset(t1)[1]
    part.loft(rows, region, weight, pole0=c0, pole1=c1, v_of=ts)


def build_leg(k, fr):
    """one left leg from its rest frames → list of Parts (weighted to the left bones)"""
    p = A.LEGS[k]
    side = 1
    parts = []
    bn = lambda seg: RG.leg_bone(side, k, seg)
    sp_region = LAYOUT['spine']

    # ---- coxa: a broad flat plate lying against the body, narrowing to the trochanter
    part = Part(f'coxa_L{k}', 'roach_legs')
    o, X, Y, Z = fr['coxa']
    wb, wt = p['coxa_w']
    seg_tube(part, (o - Y * 0.5, X, Y, Z), p['coxa'] + 0.75,
             lambda s: wb + (wt - wb) * s ** 1.2, lambda s: p['coxa_t'] * (1 - 0.25 * s),
             leg_rect(k, 'coxa'), {bn('coxa'): 1.0}, cap0=0.18, cap1=0.16, n=12, n_mid=6,
             offset=lambda s: (0.25 * math.sin(math.pi * s), 0.0))
    parts.append(part)

    # ---- femur (trochanter at its base)
    part = Part(f'femur_L{k}', 'roach_legs')
    o, X, Y, Z = fr['femur']
    Lf = p['femur']
    rx, rz = p['femur_r']

    def fx(s):
        return rx * (0.62 + 0.38 * math.sin(math.pi * min(1.0, max(0.0, (s + 0.05) / 0.95))) ** 0.5) * (1 - 0.12 * s)

    def fz(s):
        return rz * (0.55 + 0.45 * math.sin(math.pi * min(1.0, max(0.0, (s + 0.02) / 0.9))) ** 0.6) * (1 - 0.18 * s)

    L0 = -0.45
    seg_tube(part, (o + Y * L0, X, Y, Z), Lf - L0 + 0.3, lambda s: fx(s), lambda s: fz(s), leg_rect(k, 'femur'),
             {bn('femur'): 1.0}, cap0=0.06, cap1=0.06, n=12, n_mid=10)
    # trochanter: a short lobe on the femur's base, angled to the coxa
    seg_tube(part, (o - Y * 0.35 + Z * 0.12, X, unit(Y - Z * 0.3), np.cross(X, unit(Y - Z * 0.3))), 1.6,
             lambda s: rx * 0.85, lambda s: rz * 0.75, leg_rect(k, 'femur', (0.0, 0.08)), {bn('femur'): 1.0},
             cap0=0.3, cap1=0.3, n=8, n_mid=2)
    # spines on the two ventral margins (+Z side), the front femur with a full comb
    n_a, n_p = p['femur_spines']
    s0, s1 = p['spine_len']
    for row, count, ang in ((0, n_a, math.radians(55)), (1, n_p, math.radians(-55))):
        for i in range(count):
            s = 0.42 + 0.48 * (i + 0.5) / count if count > 1 else 0.85
            th = math.pi / 2 + ang                   # around from +X towards +Z (ventral)
            radial = X * math.cos(th) + Z * math.sin(th)
            base = o + Y * (s * Lf) + X * (fx(s) * math.cos(th) * 0.85) + Z * (fz(s) * math.sin(th) * 0.85)
            ln = s0 * (0.45 + 0.4 * s) * (1.0 if k == 1 else 0.7)
            d = unit(radial * 0.62 + Y * 0.78)
            spine(part, base, d, ln, 0.1, Y, sp_region, {bn('femur'): 1.0})
    # the apical (genicular) spines either side of the knee
    for sgn in (1, -1):
        th = math.pi / 2 + sgn * math.radians(75)
        radial = X * math.cos(th) + Z * math.sin(th)
        base = o + Y * (0.95 * Lf) + radial * (rx * 0.6)
        spine(part, base, unit(radial * 0.4 + Y * 0.9), s0 * 0.7, 0.08, Y, sp_region, {bn('femur'): 1.0})
    parts.append(part)

    # ---- tibia: rounded, thickening towards the foot, rows of strong spines
    part = Part(f'tibia_L{k}', 'roach_legs')
    o, X, Y, Z = fr['tibia']
    Lt = p['tibia']
    r0, r1 = p['tibia_r']
    tx = lambda s: (r0 + (r1 - r0) * s) * 0.92
    tz = lambda s: (r0 + (r1 - r0) * s) * 1.06
    seg_tube(part, (o - Y * 0.3, X, Y, Z), Lt + 0.4, lambda s: tx(min(1, s)), lambda s: tz(min(1, s)),
             leg_rect(k, 'tibia'), {bn('tibia'): 1.0}, cap0=0.05, cap1=0.04, n=10, n_mid=10)
    rows = p['tibia_rows']
    per = p['tibia_spines']
    # rows round the tibia (θ from +X towards +Z), staggered; spines lean towards the foot
    row_angles = [math.radians(a) for a in ((25, 155, 215, 325) if rows == 4 else (35, 145, 270))]
    for ri, th in enumerate(row_angles):
        for i in range(per):
            s = 0.2 + 0.68 * (i + 0.5 * (ri % 2) + 0.25) / per
            radial = X * math.cos(th) + Z * math.sin(th)
            r = math.hypot(tx(s) * math.cos(th), tz(s) * math.sin(th))
            base = o + Y * (s * Lt) + radial * (r * 0.8)
            ln = (s0 + (s1 - s0) * s) * (0.85 + 0.15 * math.sin(7.3 * i + ri))
            d = unit(radial * 0.7 + Y * 0.71)
            spine(part, base, d, ln, 0.115, Y, sp_region, {bn('tibia'): 1.0})
    # the apical crown: a ring of long spurs at the end
    n_crown = 6 if k > 1 else 5
    for i in range(n_crown):
        th = 2 * math.pi * (i + 0.3) / n_crown
        radial = X * math.cos(th) + Z * math.sin(th)
        base = o + Y * (0.97 * Lt) + radial * (r1 * 0.75)
        spine(part, base, unit(radial * 0.5 + Y * 0.87), s1 * (0.75 + 0.25 * (i % 2)), 0.115, Y, sp_region,
              {bn('tibia'): 1.0})
    parts.append(part)

    # ---- tarsus: basitarsus (tarsus1) and tarsomeres 2–5 with claws (tarsus2)
    rt = p['tarsus_r']
    lens = p['tarsi']
    for seg, seglens, region in (('tarsus1', lens[:1], 'tarsus1'), ('tarsus2', lens[1:], 'tarsus2')):
        part = Part(f'{seg}_L{k}', 'roach_legs')
        o, X, Y, Z = fr[seg]
        total = sum(seglens)
        acc = 0.0
        for j, L in enumerate(seglens):
            last = seg == 'tarsus2' and j == len(seglens) - 1
            r_a = rt * (1 - 0.12 * (acc / total if total else 0)) * (0.9 if seg == 'tarsus2' else 1.0)
            rr = (lambda s, r_a=r_a, last=last: r_a * ((0.62 + 0.38 * s) if not last else (0.75 + 0.1 * math.sin(math.pi * s))))
            t_a, t_b = acc / total, (acc + L) / total
            reg = leg_rect(k, region, (t_a, t_b))
            seg_tube(part, (o + Y * (acc - 0.05), X, Y, Z), L + 0.12, rr, rr, reg, {bn(seg): 1.0},
                     cap0=0.1, cap1=0.12, n=8, n_mid=2, n_cap=2)
            # pulvillus: a pale pad under the end of tarsomeres 1–4
            if not last:
                pc = o + Y * (acc + L * 0.78) + Z * (rr(0.8) * 0.72)
                spine(part, pc - Y * L * 0.2, Y, L * 0.32, rr(0.8) * 0.5, Z, LAYOUT['pad'], {bn(seg): 1.0}, n=5,
                      curve=0.0)
            acc += L
        if seg == 'tarsus2':
            # two claws curving down from the tip and the arolium between them
            tipc = o + Y * total
            for sgn in (1, -1):
                base = tipc - Y * 0.12 + X * (sgn * rt * 0.35)
                d = unit(Y * 0.85 + X * (sgn * 0.42) + Z * 0.35)
                spine(part, base, d, 0.62, 0.075, Z, LAYOUT['claw'], {bn(seg): 1.0}, n=5, curve=0.45)
            spine(part, tipc - Y * 0.1 + Z * 0.05, unit(Y + Z * 0.6), 0.38, 0.12, Z, LAYOUT['pad'],
                  {bn(seg): 1.0}, n=6, curve=0.0)
        parts.append(part)
    return parts


def build_legs():
    """all six legs: the left ones built round their rest bones, the right ones mirrored"""
    parts = []
    for k in (1, 2, 3):
        fr = RG.leg_frames(1, k, 0.0, rest=True)
        left = build_leg(k, fr)
        parts += left
        wmap = {RG.leg_bone(1, k, s): RG.leg_bone(-1, k, s) for s in RG.SEGMENTS}
        parts += [p.mirrored(p.name.replace('_L', '_R'), wmap) for p in left]
    return parts
