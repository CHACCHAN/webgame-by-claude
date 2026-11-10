"""
Figures shared by the Blender build (raijin.py) and the texture painter (raijin_textures.py, host Python + PIL):
lamp outlines and their projection frames, plate size. Pure Python (no bpy, no PIL).

Lamp outlines are drawn in a projection plane seen from outside the car's LEFT side (the right side is the mirror):
(w, v) in metres, w towards the car's side (outwards), v up, about the frame's origin. Measured on the Commons photos
of fitdata/raijin/ref by back-projecting their outlines onto the fitted body from the solved cameras (head lamps: the
head-on r16 and the front 3/4 r02; tail lamps: the rear 3/4 r10 and the side r13).
"""
import math

# head lamp: frame origin (game frame), yaw (rad) of the viewer from straight ahead towards the side.
# The 2004 "tear-drop" unit: the top edge runs under the bonnet's leading edge, the inner end is round (the low-beam
# projector) beside the grille, the outer end taller and squarer, wrapping round the corner. Inside: chrome bowl, the
# projector, the high-beam reflector, the position bulb and the indicator's amber reflector in the outer end.
HEAD_FRAME = ((0.560, 0.655, 2.05), math.radians(22), 'front')
HEAD_SCALE = 1.0
HEAD_VSCALE = 1.0
# lamp review (2026-11-10, fitdata/raijin/lamps.json + tools/lampfit.py): the lens outlines traced on the head-on
# photo r16 (both lamps) and the front 3/4 r02, carried back through the solved cameras onto the body and averaged in
# this frame (r16 sits ~2 cm lower than r02 throughout: camera error, split evenly). The inner end was 3 cm too far
# inboard, the lower edge 1 cm too high.
HEAD_OUTLINE = [(-0.070, -0.072), (-0.034, -0.088), (0.012, -0.086), (0.060, -0.077), (0.120, -0.077), (0.180, -0.076),
                (0.225, -0.070), (0.259, -0.055), (0.281, -0.033), (0.292, 0.000), (0.296, 0.040), (0.290, 0.066),
                (0.272, 0.084), (0.240, 0.093), (0.190, 0.093), (0.120, 0.083), (0.060, 0.070), (0.000, 0.055),
                (-0.042, 0.038), (-0.074, 0.016), (-0.093, -0.010), (-0.095, -0.038), (-0.086, -0.059)]
# inside, measured the same way (r02, r16): the projector's ring in the round inner end, the high beam's chrome bowl
# in the middle, the position bulb in the top outer corner, the indicator's amber reflector low in the outer end (as
# the 3/4 views show it; head-on it shows as an amber streak along the top of the middle part)
HEAD_PROJECTOR = (-0.008, -0.022, 0.056)     # low beam projector: w, v, radius of its chrome ring
HEAD_HIGH = (0.118, 0.004, 0.056)            # high beam reflector bowl
HEAD_POSITION = (0.247, 0.074, 0.012)        # position lamp bulb
HEAD_AMBER = [(0.226, 0.052), (0.258, 0.058), (0.284, 0.056), (0.293, 0.030), (0.293, -0.014), (0.284, -0.045),
              (0.258, -0.054), (0.234, -0.048), (0.224, -0.012), (0.222, 0.026)]   # the indicator: amber reflector, outer end
HEAD_STREAK = [(0.020, 0.046), (0.090, 0.060), (0.170, 0.074), (0.215, 0.080), (0.212, 0.064), (0.150, 0.050),
               (0.080, 0.036), (0.030, 0.030)]                                     # the amber reflector's streak (head-on)
HEAD_BOX = (-0.110, 0.310, -0.100, 0.110)     # texture area (w0, w1, v0, v1)

# tail lamp: a big rounded unit wrapping round the corner; the trunk lid's shut line runs along its top and inner
# edge. Lamp review (2026-11-10): traced on the tail-on r17 (both lamps), the rear 3/4 r10 (the far lamp) and the side
# r13 (the wrap), carried back onto the body and averaged here: the lamp was 3.5 cm too tall and its slanted inner edge
# 3-4 cm too far in. Clear upper part (reverse and indicator bulbs) as a wedge under a red rim, thick at the outer end
# and running out to a point at the inner edge; red below; the round stop / tail element at the inner bottom.
TAIL_FRAME = ((0.600, 0.800, -2.08), math.radians(32), 'rear')
TAIL_SCALE = 1.0
TAIL_OUTLINE = [(0.272, 0.098), (0.235, 0.113), (0.180, 0.125), (0.120, 0.129), (0.060, 0.125), (0.010, 0.118),
                (-0.025, 0.110), (-0.055, 0.096), (-0.080, 0.077), (-0.100, 0.055), (-0.125, 0.025), (-0.150, 0.000),
                (-0.177, -0.032), (-0.204, -0.066), (-0.202, -0.088), (-0.150, -0.095), (-0.050, -0.095), (0.050, -0.097),
                (0.150, -0.100), (0.225, -0.098), (0.270, -0.082), (0.294, -0.050), (0.303, 0.000), (0.298, 0.055)]
TAIL_ROUND = None                             # (no outer element on the 2004 lamp)
TAIL_ROUND2 = (-0.098, -0.034, 0.054)         # the round stop / tail element at the inner bottom
TAIL_CLEAR = [(-0.088, 0.032), (-0.062, 0.068), (-0.030, 0.091), (0.010, 0.104), (0.080, 0.112), (0.170, 0.110),
              (0.240, 0.100), (0.278, 0.084), (0.286, 0.050), (0.240, 0.036), (0.150, 0.032), (0.050, 0.030),
              (-0.030, 0.029)]
TAIL_BULBS = [(-0.015, 0.078, 0.016), (-0.010, 0.049, 0.015), (0.100, 0.092, 0.016), (0.100, 0.056, 0.016)]
TAIL_BULB_AMBER = (False, False, True, True)  # reverse lamp bulbs (clear) inboard, the indicator's (amber) outboard
TAIL_BOX = (-0.225, 0.320, -0.115, 0.150)

PLATE = (0.330, 0.165)                        # Japanese medium plate
PLATE_TEXT = ('朧', '300', 'さ', '12-34')


def closed_spline(pts, per=4):
    """a smooth closed curve through pts (Catmull-Rom), `per` points per span"""
    n = len(pts)
    out = []
    for i in range(n):
        p0, p1, p2, p3 = pts[(i - 1) % n], pts[i], pts[(i + 1) % n], pts[(i + 2) % n]
        for k in range(per):
            t = k / per
            t2, t3 = t * t, t * t * t
            out.append(tuple(0.5 * ((2 * p1[j]) + (-p0[j] + p2[j]) * t + (2 * p0[j] - 5 * p1[j] + 4 * p2[j] - p3[j]) * t2
                                    + (-p0[j] + 3 * p1[j] - 3 * p2[j] + p3[j]) * t3) for j in range(2)))
    return out


def scaled(pts, k, kv=1.0):
    return [(w * k, v * k * kv) for w, v in pts]
