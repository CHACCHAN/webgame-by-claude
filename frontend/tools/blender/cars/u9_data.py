"""
Measured placements of the U9's details, in the design frame (game axes, before the fitted deformation): outlines traced
on the Commons photos (fitdata/u9/traces.json, 1280-wide thumbnails) and carried onto the body by rays from the solved
cameras (fitdata/u9/tools/trace3d.py; fit: fitdata/u9/fit/). Left side (+x); the right side mirrors.

- HL          the head lamp's lens, c12 (head-on): one C round the body-coloured blade, from the upper arm's inner tip out
              along the top to the outer corner, down the outer side, in along the bottom to the lower arm's tip, and
              back along the blade's lower and upper edges
- HL_D        the lamp's projection direction (between the fender top it wraps onto and the nose)
- HL_OUTER    the light line runs just inside the lens's outer contour (HL[:HL_OUTER]): along the upper arm's top edge,
              down the outer side and along the lower arm's bottom (c32, lit)
- HL_BARS     the gate's light bars across the outer side and the lower arm (c32: ~18; spaced evenly between the outer
              contour and the blade, so their slant is estimated)
- FPAINT      the paint's lower edge at the nose, c12: outer corner -> centre (the black lower bumper, the corner
              intakes under the lamps' outer ends and the mouth below; the body-coloured blade under each lamp above)
- PLATE       the number plate (half width, bottom, top, z), c12; PLATE_R the rear one, c18
- HOODLINE    the hood's front shut line between the lamps' inner tips, c12
- BADGE_F, BADGE_R   the emblems' centres (y, z), c12 and c18 (the emblem itself is our own simple drawing)
- TL          the tail band, c18: centre top -> outer end -> centre bottom
- RPAINT      the carbon centre section under the band, c18: lamp's outer bottom -> down the inner curve -> along the
              diffuser's top edge
- DIFFUSER_TOP, FIN_X (strakes, c18), SPLIT_* (the splitter, c12 / c17: estimated from the photos' proportions)
"""
HL = [
    (0.328, 0.523, 2.436), (0.349, 0.530, 2.430), (0.427, 0.550, 2.406),
    (0.512, 0.581, 2.353), (0.596, 0.615, 2.269), (0.681, 0.650, 2.183),
    (0.765, 0.687, 2.099), (0.850, 0.717, 2.027), (0.908, 0.729, 1.945),
    (0.929, 0.678, 1.959), (0.949, 0.595, 2.006), (0.957, 0.509, 2.082),
    (0.949, 0.419, 2.153), (0.923, 0.369, 2.235), (0.880, 0.356, 2.335),
    (0.811, 0.348, 2.401), (0.705, 0.334, 2.430), (0.597, 0.330, 2.442),
    (0.535, 0.342, 2.446), (0.633, 0.378, 2.426), (0.719, 0.406, 2.402),
    (0.803, 0.440, 2.355), (0.859, 0.474, 2.292), (0.888, 0.514, 2.228),
    (0.886, 0.560, 2.186), (0.860, 0.583, 2.187), (0.735, 0.578, 2.252),
    (0.604, 0.560, 2.333), (0.472, 0.539, 2.401), (0.368, 0.522, 2.430),
]
HL_OUTER = 19                # HL[:19] is the outer contour (inner tip of the upper arm -> lower arm tip)
HL_BARS = [
    ((0.925, 0.641, 2.007), (0.883, 0.585, 2.152)),
    ((0.935, 0.604, 2.027), (0.896, 0.561, 2.162)),
    ((0.941, 0.568, 2.054), (0.898, 0.536, 2.184)),
    ((0.943, 0.535, 2.084), (0.896, 0.514, 2.207)),
    ((0.943, 0.502, 2.114), (0.887, 0.496, 2.232)),
    ((0.939, 0.468, 2.142), (0.878, 0.477, 2.256)),
    ((0.934, 0.435, 2.171), (0.864, 0.461, 2.279)),
    ((0.922, 0.410, 2.205), (0.847, 0.447, 2.303)),
    ((0.909, 0.388, 2.242), (0.829, 0.434, 2.326)),
    ((0.891, 0.376, 2.280), (0.808, 0.423, 2.347)),
    ((0.871, 0.370, 2.319), (0.785, 0.414, 2.366)),
    ((0.847, 0.364, 2.354), (0.760, 0.405, 2.384)),
    ((0.814, 0.359, 2.384), (0.733, 0.396, 2.400)),
    ((0.777, 0.354, 2.407), (0.704, 0.388, 2.410)),
    ((0.734, 0.347, 2.418), (0.674, 0.379, 2.419)),
    ((0.691, 0.341, 2.430), (0.643, 0.371, 2.427)),
    ((0.646, 0.338, 2.435), (0.613, 0.362, 2.432)),
    ((0.602, 0.335, 2.440), (0.582, 0.353, 2.438)),
]
FPAINT = [
    (-0.924, 0.360, 2.227), (-0.876, 0.352, 2.341), (-0.866, 0.319, 2.351),
    (-0.862, 0.271, 2.335), (-0.788, 0.269, 2.418), (-0.706, 0.269, 2.444),
    (-0.628, 0.279, 2.446), (-0.610, 0.308, 2.445), (-0.584, 0.341, 2.442),
    (-0.538, 0.368, 2.442), (-0.457, 0.391, 2.446), (-0.336, 0.406, 2.450),
    (-0.177, 0.415, 2.456), (0.000, 0.418, 2.466),
]
TL = [
    (0.000, 0.972, -2.500), (0.475, 0.950, -2.482), (0.783, 0.932, -2.479),
    (0.945, 0.914, -2.270), (0.973, 0.894, -2.084), (0.981, 0.856, -2.022),
    (0.978, 0.819, -2.102), (0.966, 0.800, -2.191), (0.772, 0.827, -2.480),
    (0.467, 0.844, -2.488), (0.064, 0.864, -2.498), (0.000, 0.866, -2.500),
]
RPAINT = [
    (0.904, 0.814, -2.391), (0.799, 0.776, -2.480), (0.620, 0.749, -2.484),
    (0.499, 0.721, -2.487), (0.414, 0.679, -2.490), (0.365, 0.636, -2.491),
    (0.340, 0.592, -2.491), (0.599, 0.586, -2.485), (0.784, 0.587, -2.480),
    (0.959, 0.538, -2.225),
]
PLATE = (0.270, 0.181, 0.329, 2.457)
PLATE_R = (0.271, 0.665, 0.794, -2.493)
BADGE_F = (0.527, 2.449)
BADGE_R = (0.912, -2.500)
HOODLINE = [
    (-0.344, 0.575, 2.410), (-0.173, 0.584, 2.421), (0.000, 0.577, 2.424),
    (0.173, 0.584, 2.421), (0.344, 0.575, 2.410),
]
SIDE = [
    (0.955, 0.311, -1.001), (0.956, 0.336, -0.812), (0.959, 0.370, -0.515),
    (0.959, 0.403, -0.135), (0.964, 0.565, -0.248), (0.929, 0.721, -0.376),
    (0.934, 0.693, -0.230), (0.962, 0.558, -0.081), (0.960, 0.420, 0.062),
    (0.953, 0.363, 0.428), (0.943, 0.291, 0.808), (0.923, 0.236, 1.130),
    (0.950, 0.150, 1.130), (0.950, 0.150, -1.001),
]
CHARLINE = [
    (0.980, 0.817, -2.088), (0.994, 0.785, -1.625), (0.976, 0.758, -1.133),
    (0.937, 0.746, -0.713), (0.927, 0.728, -0.388), (0.929, 0.707, 0.044),
    (0.948, 0.690, 0.516), (0.969, 0.673, 0.838),
]
DOOR_LINES = [
    [(0.744, 0.981, -0.581), (0.861, 0.873, -0.487), (0.928, 0.725, -0.380)],
    [(0.901, 0.834, 0.701), (0.942, 0.735, 0.652), (0.960, 0.669, 0.636), (0.986, 0.499, 0.719), (0.943, 0.292, 0.845)],
]
# fixed: estimated or read off the photos by hand (kept by tools/mkdata.py)
HL_D = (0.25, 0.60, 0.76)
HL_UV = (0.0, 0.0, 0.9, 0.9)
UV_WHITE = (0.975, 0.975)
FRONT_BLACK_BOTTOM = 0.10
DIFFUSER_TOP = 0.585
DIFFUSER_BOTTOM = 0.31
FIN_X = (0.07, 0.375, 0.74)
SPLIT_HALF = 0.97
SPLIT_Z = 2.52
SPLIT_SWEEP = 0.22
SPLIT_Y = 0.085
