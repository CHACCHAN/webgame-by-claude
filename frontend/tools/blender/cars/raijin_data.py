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
HEAD_OUTLINE = [(-0.085, -0.082), (-0.040, -0.088), (0.020, -0.080), (0.100, -0.066), (0.170, -0.058), (0.225, -0.057),
                (0.258, -0.050), (0.273, -0.028), (0.279, 0.008), (0.280, 0.045), (0.276, 0.075), (0.264, 0.096),
                (0.240, 0.103), (0.190, 0.102), (0.120, 0.091), (0.050, 0.078), (-0.010, 0.066), (-0.060, 0.050),
                (-0.095, 0.030), (-0.115, 0.004), (-0.118, -0.030), (-0.108, -0.062)]
# measured (2026-11-10): the outline back-projected from a head-on and a 3/4 photo onto the body (fitdata/raijin);
# the inner end is the round projector, the outer end the taller, squarer part wrapping round the corner
HEAD_PROJECTOR = (-0.050, -0.016, 0.054)     # low beam projector in the round inner end: w, v, radius
HEAD_HIGH = (0.085, 0.004, 0.052)            # high beam reflector bowl
HEAD_POSITION = (0.246, 0.068, 0.014)        # position lamp bulb
HEAD_AMBER = [(0.218, 0.090), (0.246, 0.097), (0.263, 0.090), (0.273, 0.066), (0.276, 0.030), (0.272, 0.000),
              (0.258, -0.020), (0.240, -0.022), (0.226, 0.004), (0.218, 0.046)]   # the indicator: amber reflector, outer end
HEAD_BOX = (-0.130, 0.295, -0.100, 0.112)     # texture area (w0, w1, v0, v1)

# tail lamp: a big, tall rounded unit wrapping round the corner; the trunk lid's shut line runs along its top and
# inner edge. Measured on the rear 3/4 photo (back-projected onto the body): clear upper part (reverse and indicator),
# the round stop / tail element at the inner bottom, red elsewhere.
TAIL_FRAME = ((0.600, 0.800, -2.08), math.radians(32), 'rear')
TAIL_SCALE = 1.0
TAIL_OUTLINE = [(0.270, 0.108), (0.230, 0.135), (0.170, 0.158), (0.100, 0.165), (0.003, 0.150), (-0.072, 0.128),
                (-0.120, 0.104), (-0.163, 0.060), (-0.198, -0.003), (-0.218, -0.060), (-0.214, -0.084), (-0.153, -0.093),
                (-0.043, -0.089), (0.070, -0.080), (0.160, -0.080), (0.230, -0.090), (0.280, -0.098), (0.300, -0.070),
                (0.306, 0.000), (0.298, 0.065)]      # rear face from the rear 3/4 photo, the wrap round the corner from the side
TAIL_ROUND = None                             # (no outer element on the 2004 lamp)
TAIL_ROUND2 = (-0.139, -0.029, 0.058)         # the round stop / tail element at the inner bottom
TAIL_CLEAR = [(-0.150, 0.038), (-0.075, 0.040), (0.000, 0.046), (0.128, 0.062), (0.200, 0.052), (0.250, 0.070),
              (0.230, 0.120), (0.150, 0.146), (0.003, 0.134), (-0.072, 0.112), (-0.118, 0.086)]
TAIL_BULBS = [(-0.060, 0.086, 0.024), (0.040, 0.098, 0.024)]   # reverse lamp and indicator bowls in the clear part   # the clear upper part (reverse lamp, indicator)
TAIL_BOX = (-0.235, 0.315, -0.110, 0.180)

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
