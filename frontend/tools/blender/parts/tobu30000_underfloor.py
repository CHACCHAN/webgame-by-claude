"""
Underfloor equipment of the Tobu 30000 series: the Tc cab cars (クハ31600 / 34400) and the M1 car (モハ32600: VVVF +
CP). A part module for the Blender model (train_kit.Part, the game's car frame, material prefix `tu_`). The boxes are
built with underfloor_n1000's helpers (lids, latches, grilles, louvres, tanks, the frame) and re-coloured.

  add_materials(m)
  underfloor(part, kind)    kind 'cab' (cab at +z) or 'middle'; -> triangles added

Equipment per ja.wikipedia 東武30000系電車: M1 carries the Hitachi IGBT VVVF inverter (VFI-HR1420B, 1C4M) and the air
compressor; the Tc cars carry no traction gear (brake control, tanks, battery and the train protection gear: est.).
Sizes and places are estimates read off the side photos (Commons "Tobu-30000 Tojo-Line Musashi-Ranzan.jpg",
"Tobu-Series30000 31612.jpg", the bogie photos of Rs1421): dark grey-brown boxes hanging to ≈ 0.35 m above the rail,
the inverter box long and in the middle of the car, the light grey CP unit on the M1 car.
"""
import train_kit as K
import underfloor_n1000 as UN

COLOURS = {
    'tu_body': ('#5e5149', 0.3, 0.64),
    'tu_lid': ('#6a5c53', 0.3, 0.58),
    'tu_light': ('#8f918d', 0.5, 0.45),
    'tu_steel': ('#303031', 0.6, 0.55),
    'tu_hw': ('#a4a7aa', 0.85, 0.32),
    'tu_dark': ('#141516', 0.2, 0.75),
}
X = UN.X


def add_materials(m):
    for name, (colour, metallic, rough) in COLOURS.items():
        if name not in m.mats:
            m.add(name, colour, metallic, rough)
    return 0


def _emit(part, tmp):
    """copy tmp's faces into part, uf_ materials renamed to tu_"""
    n = sum(len(f.verts) - 2 for f in tmp.bm.faces)
    vmap = {v: part.bm.verts.new(v.co.copy()) for v in tmp.bm.verts}
    for f in tmp.bm.faces:
        nf = part.bm.faces.new([vmap[v] for v in f.verts])
        nf.material_index = part.slot(tmp.slots[f.material_index].replace('uf_', 'tu_'))
        nf.smooth = f.smooth
    tmp.bm.free()
    return n


def _cab_car(p):
    B, L = UN._box, UN._lid
    # brake control unit (right) and the battery box (left, light grey) ahead of the middle
    B(p, 'uf_body', -X, -0.05, 0.45, UN.TOP, 2.30, 3.90, c=0.010)
    L(p, -1, -X, 2.36, 3.10, 0.50, 0.85, plates=1)
    L(p, -1, -X, 3.16, 3.84, 0.50, 0.85)
    UN._hangers(p, -1, -X, 2.30, 3.90, (2.4, 3.8))
    B(p, 'uf_light', 0.05, X, 0.42, UN.TOP, 1.60, 3.70, c=0.010)
    for z0, z1 in ((1.66, 2.33), (2.36, 3.03), (3.06, 3.64)):
        L(p, 1, X, z0, z1, 0.47, 0.85, mat='uf_light', levers=2)
    UN._hangers(p, 1, X, 1.60, 3.70, (1.7, 2.65, 3.6))
    # train protection / monitor boxes (right), cable box (left) in the middle
    B(p, 'uf_body', -X, -0.10, 0.50, UN.TOP, -1.10, 0.90, c=0.010)
    L(p, -1, -X, -1.04, -0.10, 0.55, 0.85, plates=2)
    L(p, -1, -X, -0.04, 0.84, 0.55, 0.85)
    UN._hangers(p, -1, -X, -1.10, 0.90, (-1.0, 0.0, 0.8))
    UN._cable_box(p, 1, 0.40, X, 0.55, UN.TOP, -0.60, 0.50, lids=2)
    # main reservoir across the car, air tanks along it
    UN._tank(p, (0.0, 0.62, 4.75), 0.21, 2.24, 'x', straps=(-0.33, 0.0, 0.33), n=16)
    UN._tank(p, (0.95, 0.60, -2.60), 0.17, 1.40, 'z', straps=(-0.3, 0.3))
    UN._tank(p, (0.55, 0.60, -2.60), 0.17, 1.40, 'z', straps=(-0.3, 0.3))
    UN._tank(p, (-0.80, 0.60, -2.90), 0.19, 1.60, 'z', straps=(-0.3, 0.3))
    UN._run(p, 'uf_steel', (0.75, 0.78, -1.9), [('z', 0.5), ('y', -0.12)], 0.013)
    UN._cable_box(p, -1, -X, -0.30, 0.52, UN.TOP, -4.70, -3.90, lids=2)
    UN._cable_box(p, 1, 0.50, X, 0.58, UN.TOP, -4.80, -4.10, lids=1)
    # beyond the bogies
    UN._cable_box(p, -1, -1.00, -0.50, 0.62, 0.86, 8.50, 8.85, lids=1)
    UN._cable_box(p, 1, 0.55, 1.00, 0.62, 0.86, -8.85, -8.50, lids=1)


def _m1(p):
    B, L = UN._box, UN._lid
    # VVVF inverter: one long box across the car, lids both sides, the cooling grille on the right
    z0, z1 = -1.40, 2.60
    B(p, 'uf_body', -X, X, UN.BOT, UN.TOP, z0, z1, c=0.012)
    UN._flange(p, -X, X, z0, z1)
    s, xf = -1, -X
    L(p, s, xf, -1.35, -0.10, 0.40, 0.84, plates=2)
    L(p, s, xf, -0.05, 0.85, 0.40, 0.84, plates=1)
    UN._grille(p, s, xf, 0.95, 2.05, 0.40, 0.84, divider=True)
    L(p, s, xf, 2.12, 2.55, 0.40, 0.84)
    UN._bars(p, s, xf, (-0.075, 0.90, 2.085), 0.40, 0.84)
    UN._hangers(p, s, xf, z0, z1, (-1.3, -0.08, 0.9, 2.08, 2.5))
    s, xf = 1, X
    L(p, s, xf, -1.35, -0.30, 0.40, 0.84, plates=1)
    UN._louvre(p, s, xf, -0.20, 1.10, 0.40, 0.84, n=12)
    L(p, s, xf, 1.20, 2.55, 0.40, 0.84, plates=1)
    UN._bars(p, s, xf, (-0.25, 1.15), 0.40, 0.84)
    UN._hangers(p, s, xf, z0, z1, (-1.3, -0.25, 1.15, 2.5))
    # filter reactor (right) and high-speed breaker (left) towards +z
    B(p, 'uf_body', -X, -0.10, 0.42, UN.TOP, 2.85, 4.20, c=0.010)
    L(p, -1, -X, 2.91, 4.14, 0.47, 0.85, plates=1)
    UN._hangers(p, -1, -X, 2.85, 4.20, (2.95, 4.1))
    B(p, 'uf_body', 0.10, X, 0.50, UN.TOP, 2.85, 3.85, c=0.010)
    L(p, 1, X, 2.91, 3.35, 0.55, 0.85, levers=4)
    L(p, 1, X, 3.40, 3.79, 0.55, 0.85, levers=2, pockets=False)
    UN._hangers(p, 1, X, 2.85, 3.85, (2.95, 3.75))
    # air compressor (screw type, light grey unit) on the left, tanks on the right, towards −z
    B(p, 'uf_light', 0.10, X, 0.40, UN.TOP, -4.40, -2.20, c=0.012)
    for a, b in ((-4.34, -3.32), (-3.26, -2.26)):
        L(p, 1, X, a, b, 0.62, 0.86, mat='uf_light', levers=2)
        L(p, 1, X, a, b, 0.44, 0.60, mat='uf_light', levers=2, pockets=False)
    UN._hangers(p, 1, X, -4.40, -2.20, (-4.3, -3.29, -2.3))
    UN._tank(p, (-0.95, 0.60, -3.30), 0.17, 1.50, 'z', straps=(-0.3, 0.3))
    UN._tank(p, (-0.55, 0.60, -3.30), 0.17, 1.50, 'z', straps=(-0.3, 0.3))
    UN._tank(p, (0.0, 0.62, -5.00), 0.20, 2.0, 'x', straps=(-0.33, 0.0, 0.33), n=16)
    UN._cable_box(p, -1, -X, -0.30, 0.52, UN.TOP, 4.40, 5.00, lids=1)
    UN._cable_box(p, -1, -X, -0.30, 0.52, UN.TOP, -2.00, -1.60, lids=1)
    for x in (-0.55, 0.55):
        UN._pipe(p, 'uf_dark', 'z', (x, 0.76, 2.73), 0.028, 0.26, n=8)


def underfloor(part, kind):
    tmp = K.Part('tu_tmp')
    if kind == 'cab':
        _cab_car(tmp)
        UN._frame(tmp, -9.0, 9.0)
    else:
        _m1(tmp)
        UN._frame(tmp, -9.6, 9.6)
    return _emit(part, tmp)
