"""
Lamp lens textures for the bikes (deterministic, numpy + Pillow; our own drawings, no photo pixels):

  <python with numpy + Pillow> tools/blender/bikes/bike_textures.py [nsr250r ...]   -> tools/blender/textures/<id>/*.png

The lens itself is opaque in the game (no transmission), so the texture paints what the clear lens shows: the chrome
reflector behind it, the bulb and its shield, the lens's prism flutes and the dark housing round it. The game uses the
same image as the lamp's glow map at night (the bright parts light up). u runs from the lens's inner edge (0) to its
outer edge (1), v from its bottom (0) to its top (1).

ninjah2/headlight.png  the round LED projector (left square) and the clear position-lamp lenses (right strip)
ninjah2/taillight.png  the tail lamp: red-tinted lens over two rows of clear LED cells
ninjah2/disc.png       one tile of the brake discs' drilled steel ring (not a lamp: the ring's base colour)
hayabusa/disc.png      the same for the Hayabusa's discs (two staggered rows of smaller holes)
hayabusa/headlight.png the stacked head lamps behind one clear cover: two chrome multi-reflector bowls (the upper one
                       larger), each with its bulb shield, a chrome divider, the dark housing round them
hayabusa/taillight.png the tail lamp: red lens over two bulb reflectors, fine horizontal ribs
nsr250r/headlight.png  one rectangular MC21 head lamp: vertical prism flutes over a chrome reflector, the bulb shield
                       a little above the middle, the cowl's shadow along the top edge, a dark seal round the edge
"""
import os
import sys

import numpy as np
from PIL import Image

ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'textures')


def _save(bike, name, rgb):
    os.makedirs(os.path.join(ROOT, bike), exist_ok=True)
    im = Image.fromarray(np.clip(rgb * 255 + 0.5, 0, 255).astype(np.uint8), 'RGB')
    im.save(os.path.join(ROOT, bike, name), optimize=True)
    print('wrote', os.path.join(ROOT, bike, name), im.size)


def smooth(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


def nsr_headlight(w=768, h=512):
    v, u = np.mgrid[0:h, 0:w].astype(float)
    u = (u + 0.5) / w                      # 0 inner .. 1 outer
    v = 1.0 - (v + 0.5) / h                # 0 bottom .. 1 top
    aspect = 1.5                           # lens width / height
    x = (u - 0.47) * aspect                # in lens heights, about the reflector's axis
    y = v - 0.52
    r = np.sqrt(x * x + y * y)
    # chrome reflector: a bright ring round the bulb, falling off to the corners, brighter below (it mirrors the
    # sunlit road and the fairing)
    refl = 0.50 + 0.30 * np.exp(-((r - 0.24) / 0.11) ** 2) - 0.22 * smooth(0.35, 0.75, r) + 0.10 * smooth(0.1, -0.4, y)
    # the bulb shield: a dark cap with a chrome rim and a small highlight
    shield = smooth(0.075, 0.06, r)
    refl = refl * (1 - shield) + shield * (0.22 + 0.45 * np.exp(-(((x + 0.02) ** 2 + (y - 0.03) ** 2) / 0.0006)))
    refl += 0.35 * np.exp(-((r - 0.085) / 0.012) ** 2)
    # prism flutes: 18 vertical columns, each a small cylinder lens (light on one flank, dark line at its edge);
    # a horizontal break a third of the way up where the prism pattern changes
    cols = 18
    f = (u * cols) % 1.0
    # each flute smears what lies behind it sideways: mix in the column's row average
    ci = np.minimum((u * cols).astype(int), cols - 1)
    sm = np.zeros_like(refl)
    for c in range(cols):
        m = ci[0] == c
        sm[:, m] = refl[:, m].mean(axis=1, keepdims=True)
    refl = 0.35 * refl + 0.65 * sm
    flute = 0.88 + 0.22 * np.sin(np.pi * f) ** 2 - 0.20 * smooth(0.07, 0.0, f) - 0.10 * smooth(0.93, 1.0, f)
    flute -= 0.12 * np.exp(-((v - 0.33) / 0.012) ** 2)
    val = refl * flute
    # the cowl's shadow inside the housing along the top, a softer one along the bottom, and the dark seal
    val *= 0.28 + 0.72 * smooth(0.97, 0.76, v)
    val *= 0.70 + 0.30 * smooth(0.0, 0.12, v)
    edge = np.minimum(np.minimum(u, 1 - u) * aspect, np.minimum(v, 1 - v))
    val *= 0.25 + 0.75 * smooth(0.012, 0.035, edge)
    # overall level: the r01 lens reads at a median of ~0.36 (sRGB) in sunlight
    val = np.clip(val * 0.66, 0.03, 1.0)
    rgb = np.stack([val * 0.97, val * 0.985, val * 1.0], axis=-1)
    _save('nsr250r', 'headlight.png', rgb)


def h2_headlight(w=640, h=512):
    """ninjah2/headlight.png: left 512 x 512 = the round LED projector seen head-on (u 0..0.8 across the lens's
    bounding square): dark housing, a chrome ring, the lens with the projector's reflector, the LED and a soft
    highlight; right strip (u > 0.8) = the clear position-lamp lenses (light, faintly ribbed)"""
    v, u = np.mgrid[0:h, 0:w].astype(float)
    x = (u + 0.5) / h - 0.5          # lens square: x, y in -0.5 .. 0.5
    y = 0.5 - (v + 0.5) / h
    r = np.sqrt(x * x + y * y)
    val = np.full((h, w), 0.06)
    ring = smooth(0.43, 0.41, r) * smooth(0.36, 0.38, r)
    val += 0.70 * ring * (0.75 + 0.25 * np.cos(np.arctan2(y, x) - 2.2))
    lens = smooth(0.37, 0.355, r)
    inner = 0.16 + 0.30 * np.exp(-((r - 0.24) / 0.07) ** 2) + 0.10 * smooth(0.0, -0.3, y)
    inner += 0.65 * np.exp(-(r / 0.06) ** 2)                       # the LED and its lens focus
    inner += 0.35 * np.exp(-(((x + 0.14) ** 2 + (y - 0.16) ** 2) / 0.004))   # a soft highlight on the glass
    val = val * (1 - lens) + inner * lens
    # position lamps: clear ribbed lens over a white reflector
    pos = (u + 0.5) / w > 0.8
    rib = 0.80 + 0.10 * np.sin(v / h * np.pi * 40) ** 2
    val[pos] = rib[pos]
    val = np.clip(val, 0.02, 1.0)
    rgb = np.stack([val * 0.96, val * 0.98, val * 1.0], axis=-1)
    _save('ninjah2', 'headlight.png', rgb)


def h2_taillight(w=512, h=256):
    """ninjah2/taillight.png: the tail lamp's red-tinted lens over two rows of clear LED cells (they glow red at night),
    a dark seal round the edge; u from the bike's left (0) to its right (1), v from the lamp's front edge (0) to the
    back edge under the tip (1)"""
    v, u = np.mgrid[0:h, 0:w].astype(float)
    u = (u + 0.5) / w
    v = 1.0 - (v + 0.5) / h
    base = 0.16 + 0.05 * smooth(0.0, 1.0, v)
    cells = np.zeros_like(u)
    for row, (v0, v1) in enumerate(((0.22, 0.46), (0.54, 0.80))):
        n = 7 if row == 0 else 8
        for k in range(n):
            u0 = 0.08 + (0.84 * k + 0.06) / n
            u1 = 0.08 + (0.84 * (k + 1) - 0.06) / n
            du = np.minimum(u - u0, u1 - u) * w
            dv = np.minimum(v - v0, v1 - v) * h
            cells = np.maximum(cells, smooth(0.0, 4.0, np.minimum(du, dv)))
    val = base * (1 - cells) + cells * (0.62 + 0.25 * smooth(0.3, 0.9, v))
    edge = np.minimum(np.minimum(u, 1 - u) * 2.0, np.minimum(v, 1 - v))
    val *= 0.3 + 0.7 * smooth(0.02, 0.06, edge)
    r = np.clip(val * 1.0 + 0.10 * (1 - cells), 0, 1)
    g = np.clip(val * (0.18 + 0.55 * cells), 0, 1)
    b = np.clip(val * (0.20 + 0.55 * cells), 0, 1)
    _save('ninjah2', 'taillight.png', np.stack([r, g, b], axis=-1))


def _bowl(x, y, rx, ry, facets=10):
    """a chrome multi-reflector bowl seen through a clear lens: bright faceted ring round a dark bulb shield; returns
    (value, inside mask)"""
    r = np.sqrt((x / rx) ** 2 + (y / ry) ** 2)
    a = np.arctan2(y / ry, x / rx)
    face = 0.5 + 0.5 * np.cos(facets * a)                      # the facets catch the light in turn
    val = 0.42 + 0.30 * np.exp(-((r - 0.55) / 0.22) ** 2) * (0.7 + 0.3 * face) + 0.12 * smooth(0.2, -0.6, y / ry)
    val -= 0.10 * smooth(0.75, 1.0, r)
    shield = smooth(0.24, 0.20, r)
    val = val * (1 - shield) + shield * (0.20 + 0.50 * np.exp(-((x / rx + 0.06) ** 2 + (y / ry - 0.07) ** 2) / 0.004))
    val += 0.30 * np.exp(-((r - 0.235) / 0.03) ** 2)            # the shield's chrome rim
    inside = smooth(1.0, 0.96, r)
    return val, inside


def hb_headlight(w=384, h=512):
    """hayabusa/headlight.png: u from the lens's right edge (x = -0.08 m, 0) to its left (x = +0.08, 1), v from its
    bottom (y = 0.775, 0) to its top (y = 0.99, 1). Behind the clear cover the whole lamp is chrome reflector: the upper
    bowl (centre v 0.68) and the smaller lower one (v 0.25), each faceted with its bulb shield, set in a chrome body"""
    v, u = np.mgrid[0:h, 0:w].astype(float)
    xm = ((u + 0.5) / w - 0.5) * 0.16                 # metres across
    ym = (1.0 - (v + 0.5) / h) * 0.215 + 0.775        # metres up
    # the reflector body: horizontal facets, brighter low down (it mirrors the road and the sky's horizon)
    val = 0.40 + 0.10 * np.sin((ym - 0.775) / 0.215 * np.pi * 9) ** 2 + 0.08 * smooth(0.9, 0.78, ym)
    for cy, rx, ry in ((0.921, 0.07, 0.062), (0.829, 0.058, 0.05)):
        b, ins = _bowl(xm, ym - cy, rx, ry, facets=12)
        val = val * (1 - ins) + (b * 1.12) * ins
        r = np.sqrt((xm / rx) ** 2 + ((ym - cy) / ry) ** 2)
        val -= 0.12 * np.exp(-((r - 1.0) / 0.04) ** 2)       # the bowl's rim line
    val *= 0.90 + 0.10 * smooth(0.775, 0.99, ym)
    val = np.clip(val, 0.03, 1.0)
    rgb = np.stack([val * 0.97, val * 0.985, val * 1.0], axis=-1)
    _save('hayabusa', 'headlight.png', rgb)


def hb_taillight(w=512, h=256):
    """hayabusa/taillight.png: u from the bike's right (x = -0.11, 0) to its left (+0.11, 1), v from y 0.79 (0) to 0.875
    (1): a red lens over two bulb reflectors with fine horizontal ribs"""
    v, u = np.mgrid[0:h, 0:w].astype(float)
    u = (u + 0.5) / w
    v = 1.0 - (v + 0.5) / h
    val = 0.30 + 0.06 * smooth(0.0, 1.0, v)
    for cu in (0.30, 0.70):
        r = np.sqrt(((u - cu) * 2.6) ** 2 + ((v - 0.5) * 1.0) ** 2)
        val += 0.45 * np.exp(-(r / 0.30) ** 2) + 0.20 * np.exp(-(r / 0.07) ** 2)
    val *= 0.90 + 0.10 * np.sin(v * np.pi * 18) ** 2
    edge = np.minimum(np.minimum(u, 1 - u) * 3.0, np.minimum(v, 1 - v))
    val *= 0.35 + 0.65 * smooth(0.01, 0.08, edge)
    r = np.clip(val * 1.15 + 0.08, 0, 1)
    g = np.clip(val * 0.14, 0, 1)
    b = np.clip(val * 0.16, 0, 1)
    _save('hayabusa', 'taillight.png', np.stack([r, g, b], axis=-1))


def _disc(bike, holes, w=256, h=160, hole_r=2.5):
    """<bike>/disc.png: one tile of a brake disc's steel ring (the ring repeats it 12 times round): u round the ring,
    v from the ring's inner edge (0) to its outer edge (1); ~0.29 mm per pixel both ways (a 74 x 45 mm tile). Steel
    #8a8d90 with fine concentric grinding marks and drilled holes (each dark with a bright chamfer); the bands along
    both edges stay plain (the ring's edge faces sample them)."""
    v, u = np.mgrid[0:h, 0:w].astype(float)
    u = (u + 0.5) / w
    v = 1.0 - (v + 0.5) / h
    um, vm = u * 74.0, v * 45.0                       # millimetres across the tile
    rng = np.random.default_rng(7)
    marks = np.interp(v, np.linspace(0, 1, 97), rng.normal(0.0, 1.0, 97))
    val = 1.0 + 0.035 * marks
    col = np.array([0.541, 0.553, 0.565])
    hole = np.zeros_like(u)
    rim = np.zeros_like(u)
    for hu, hv in holes:
        for du in (-1.0, 0.0, 1.0):                   # wrap round the tile's ends
            d = np.hypot(um - (hu + du) * 74.0, vm - hv * 45.0)
            hole = np.maximum(hole, smooth(hole_r + 0.5, hole_r - 0.2, d))
            rim = np.maximum(rim, smooth(hole_r + 1.4, hole_r + 0.7, d) * (1 - smooth(hole_r + 0.5, hole_r - 0.2, d)))
    shade = val * (1 - hole) * (1 + 0.28 * rim) + hole * 0.09
    rgb = np.clip(col[None, None, :] * shade[..., None], 0, 1)
    _save(bike, 'disc.png', rgb)


def h2_disc():
    """ninjah2/disc.png: per tile a diagonal line of three holes and a fourth by the outer edge (r01)"""
    _disc('ninjah2', [(0.17, 0.26), (0.43, 0.46), (0.69, 0.66), (0.93, 0.82)])


def hb_disc():
    """hayabusa/disc.png: per tile two staggered rows of small holes round the middle of the ring (r01)"""
    _disc('hayabusa', [(0.12, 0.36), (0.37, 0.64), (0.62, 0.36), (0.87, 0.64)], hole_r=2.2)


MAKERS = {'nsr250r': [nsr_headlight], 'ninjah2': [h2_headlight, h2_taillight, h2_disc],
          'hayabusa': [hb_headlight, hb_taillight, hb_disc]}

if __name__ == '__main__':
    for bike in (sys.argv[1:] or list(MAKERS)):
        for fn in MAKERS[bike]:
            fn()
