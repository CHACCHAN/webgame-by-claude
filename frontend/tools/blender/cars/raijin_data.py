"""
Figures shared by the Blender build (raijin.py) and the texture painter (raijin_textures.py, host Python + PIL):
lamp outlines and their projection frames, plate size. Pure Python (no bpy, no PIL).

Lamp outlines are drawn in a projection plane seen from outside the car's LEFT side (the right side is the mirror):
(w, v) in metres, w towards the car's side (outwards), v up, about the frame's origin. Measured on the Commons photos
(front: "2003 Subaru Impreza WRX Turbo" F5 WRX, "Subaru IMPREZA WRX STi (GDB) front"; rear: "Subaru IMPREZA WRX STi
(GDB) rear", "Nice plate on this Scooby"), scaled from the plate and the car's width.
"""
import math

# head lamp: frame origin (game frame), yaw (rad) of the viewer from straight ahead towards the side.
# The 2004 "tear-drop" unit: the top edge runs 8 mm under the bonnet's leading edge (the shell's belt line, computed in
# this frame), the outer end is narrow and wraps round the corner, the inner end is a round "tear" hanging down beside
# the grille. Inside: chrome bowl, the low-beam projector in the tear, the high-beam reflector, a small amber strip.
HEAD_FRAME = ((0.560, 0.655, 2.05), math.radians(22), 'front')
HEAD_SCALE = 1.0
HEAD_VSCALE = 1.0
HEAD_OUTLINE = [(-0.150, -0.146), (-0.104, -0.134), (-0.040, -0.108), (0.030, -0.090), (0.100, -0.075),
                (0.180, -0.062), (0.250, -0.052), (0.298, -0.040), (0.322, -0.018), (0.330, 0.012), (0.327, 0.046),
                (0.318, 0.078), (0.298, 0.097), (0.268, 0.104), (0.232, 0.106), (0.202, 0.104), (0.176, 0.097),
                (0.144, 0.088), (0.106, 0.079), (0.063, 0.069), (0.015, 0.061), (-0.039, 0.055), (-0.096, 0.050), (-0.158, 0.046), (-0.215, 0.044),
                (-0.243, 0.030), (-0.250, -0.010), (-0.244, -0.058), (-0.218, -0.114)]
HEAD_PROJECTOR = (-0.150, -0.052, 0.054)     # low beam projector in the tear: w, v, radius
HEAD_HIGH = (0.040, -0.012, 0.058)           # high beam reflector bowl
HEAD_POSITION = (0.205, 0.040, 0.016)        # position lamp bulb
HEAD_AMBER = [(0.226, -0.050), (0.298, -0.040), (0.322, -0.018), (0.330, 0.012), (0.318, 0.012), (0.296, -0.012),
              (0.262, -0.030)]                 # the indicator: a narrow strip along the outer end's bottom
HEAD_BOX = (-0.26, 0.345, -0.158, 0.105)     # texture area (w0, w1, v0, v1)

# tail lamp: a big, tall rounded unit wrapping round the corner; the trunk lid's shut line runs along its top and
# inner edge. Upper inner part clear (reverse lamp), the rest red with two round elements.
TAIL_FRAME = ((0.600, 0.800, -2.08), math.radians(32), 'rear')
TAIL_SCALE = 1.0
TAIL_OUTLINE = [(-0.212, 0.121), (-0.216, 0.065), (-0.21, 0.0), (-0.186, -0.054), (-0.132, -0.092), (-0.05, -0.111), (0.057, -0.115), (0.171, -0.105), (0.249, -0.079), (0.285, -0.038), (0.299, 0.022), (0.292, 0.073), (0.269, 0.108), (0.205, 0.127), (0.114, 0.141), (0.0, 0.149), (-0.1, 0.151), (-0.18, 0.148)]
TAIL_ROUND = (0.097, -0.013, 0.076)           # the outer round stop / tail element
TAIL_ROUND2 = (-0.105, -0.032, 0.056)         # the inner round element
TAIL_CLEAR = [(-0.2, 0.063), (-0.02, 0.069), (0.046, 0.084), (0.068, 0.138), (0.0, 0.143), (-0.1, 0.145), (-0.176, 0.141), (-0.204, 0.117)]   # the clear upper inner part (reverse lamp)
TAIL_BOX = (-0.23, 0.31, -0.125, 0.165)

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
