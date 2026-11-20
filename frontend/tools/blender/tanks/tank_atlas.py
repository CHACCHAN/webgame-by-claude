"""Procedural tank skin for the game. All sampling (including marks) is in the
rest pose, in game metres: +X left, +Y up, +Z forward. No photo overlays.
Optional extensions: scheme['pattern']='type10' selects the two-tone finish;
paint_tank(..., markings=...) inks digits into the atlas. A marking can give
normal, right and width for orthogonal projection onto a sloped plate.
paint_tracks(..., metal_tint='#59564C') overrides the link steel swatch.
The lamps keep their shaders; the belts keep both their shaders and scrolling UVs.
"""
import os
import sys
from itertools import product
from pathlib import Path

import bpy
import numpy as np

# The shared atlas and colour conversion live alongside the jet builders.
_JETS = str(Path(__file__).resolve().parents[1] / 'jets')
if _JETS not in sys.path:
    sys.path.append(_JETS)
import jet_atlas as JA
import jet_kit as K


DEFAULT_SCHEME = dict(base='#51553a', green='#3b4a2e', brown='#6b5236', dust='#a59273',
                      dust_strength=0.18, scale=1.0, seed=10)
PLAIN = {  # sRGB, roughness, metallic
    'rubber': ('#292a27', 0.92, 0.0), 'steel': ('#646461', 0.55, 0.85),
    'recess': ('#252720', 0.94, 0.0), 'glass_dark': ('#192d30', 0.16, 0.25),
}
KEEP = ('headlight', 'taillight', 'track_l', 'track_r')


def _rgb(colour):
    return np.array(K.srgb(colour)[:3], np.float32)


def _step(a, b, x):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def _mix(a, b, weight):
    return a + (b - a) * weight[..., None]


def _save(workdir, prefix, base, orm, normal):
    os.makedirs(workdir, exist_ok=True)
    return {k: JA.save(arr, os.path.join(os.path.abspath(workdir), prefix + k + '.png'), k == 'base')
            for k, arr in [('base', base), ('orm', orm), ('normal', normal)]}


def _plate_edges(tris, paint_id):
    """Open or folded edges of painted facets, never a triangulation diagonal.
    Use geometric rather than vertex IDs: parts can have unwelded vertices.
    """
    points, _, _, zones, objects, _ = tris
    edges = {}
    for i in np.flatnonzero(zones == paint_id):
        a, b, c = points[i]
        n = np.cross(b - a, c - a)
        length = np.linalg.norm(n)
        if length < 1e-10:
            continue
        n /= length
        verts = [tuple(v) for v in points[i].round(5)]
        for a, b in zip(verts, verts[1:] + verts[:1]):
            key = (objects[i], *sorted((a, b)))
            if key not in edges:
                edges[key] = (n, True)
            else:
                first, _ = edges[key]
                edges[key] = (first, abs(first @ n) < 0.90)
    return [(a, b, 'edge', 0.018, -0.004, ob) for (ob, a, b), (_, sharp) in edges.items() if sharp]


def _relief(pos, obj, paint, features):
    """Sample nearby edge/mark segments, in spatial bins rather than testing
    every texel on the hull for every bolt. Padded texels get the same profile.
    """
    edge = np.zeros(len(pos), np.float32)
    detail = np.zeros_like(edge)
    ink = np.zeros_like(edge)
    ids = np.flatnonzero(paint)
    if not len(ids) or not features:
        return edge, ink
    cell = 0.35
    ijk = np.floor(pos[ids] / cell).astype(np.int32)
    lo = ijk.min(0)
    hi = ijk.max(0)
    dims = tuple(hi - lo + 1)
    keys = np.ravel_multi_index((ijk - lo).T, dims)
    order = np.argsort(keys)
    ids = ids[order]
    bins, starts = np.unique(keys[order], return_index=True)
    buckets = dict(zip(bins, np.split(ids, starts[1:])))
    for a, b, kind, r, h, oi in features:
        a, b = np.asarray(a, np.float32), np.asarray(b, np.float32)
        if r <= 0 or kind not in ('bolt', 'seam', 'edge'):
            raise ValueError(f'invalid relief feature: {kind}, radius={r}')
        d = b - a
        d2 = max(d @ d, 1e-12)
        low = np.maximum(lo, np.floor((np.minimum(a, b) - r) / cell).astype(int))
        high = np.minimum(hi, np.floor((np.maximum(a, b) + r) / cell).astype(int))
        for key in product(*(range(i, j + 1) for i, j in zip(low - lo, high - lo))):
            ix = buckets.get(np.ravel_multi_index(key, dims))
            if ix is None:
                continue
            if oi is not None:
                ix = ix[obj[ix] == oi]
            q = pos[ix] - a
            along = np.clip(np.einsum('ij,j->i', q, d) / d2, 0, 1)
            t = np.linalg.norm(q - along[:, None] * d, axis=1) / r
            if kind == 'edge':
                edge[ix] = np.minimum(edge[ix], h * np.maximum(1 - t, 0)**2)
            else:
                profile = 1 - _step(0.58 if kind == 'bolt' else 0.0, 1, t)
                detail[ix] += h * profile
                ink[ix] = np.maximum(ink[ix], 0.16 * profile if kind == 'seam' else 0.13 * 4 * profile * (1 - profile))
    return edge + detail, ink


# Rest-pose samples, not UV islands: neighbouring plates meet at the same
# phase. Staggered ovals grow/shrink along their rows instead of repeating a tile.
# For cubic smoothstep, t=.1958001 and .8041999 give 10 and 90 percent.
# This half-width gives .050 metres *between* those levels, not full support.
_T10_EDGE = .050 / (2*(.8041999-.1958001))


def _type10_bands(rng):
    # A sequence of actual band lengths, not z divided by a varying pitch
    # (which would make the phase jump or even run backwards). Keep the
    # extrema as well as the mean exactly, then shuffle the order per body.
    t = np.linspace(-1., 1., 32)
    pitch = np.linspace(.72, 1.35, len(t))
    pitch -= (pitch.mean()-1.)*(1-t*t)/np.mean(1-t*t)
    rng.shuffle(pitch)
    edges = np.r_[0., np.cumsum(2.25*pitch)]
    phases = rng.uniform(0., 2*np.pi, (len(t), 2))
    widths = rng.permutation(np.linspace(-1., 1., len(t)))
    return edges, phases, widths, rng.uniform(0., edges[-1])


def _type10_coords(pos, bands, scale):
    """Distances in pattern metres from bent band centrelines, and local duty controls."""
    edges, phases, widths, shift = bands
    x, y, z = (pos/scale).T
    y = y-1.55
    lean = .45*np.tanh(x/.65)
    u = z-.36*x-lean*y+shift
    u = np.remainder(u, edges[-1])
    i = np.minimum(np.searchsorted(edges, u, side='right')-1, len(widths)-1)
    period = edges[i+1]-edges[i]
    d = u-edges[i]-.5*period
    # Bend the centreline, not the pixel mask. Integrate a local heading
    # perturbation: sinusoidal slope components with wavelengths 1.2..2 m.
    # Mix phases per band to avoid a repeating family of parallel curves.
    v = y+.55*x
    k1, k2 = 2*np.pi/1.90, 2*np.pi/1.28
    p1, p2 = k1*v+phases[i,0], k2*v+phases[i,1]
    wave = .73*np.sin(p1)+.27*np.sin(p2)
    # Piecewise amplitude maps [-1,+1] to the slope deltas for [-18,+16]
    # around the local side heading. Use its antiderivative (the asymmetric
    # endpoints differ little, so a midpoint and half-range suffice).
    theta = np.arctan(lean)
    slope_lo = np.tan(theta-np.deg2rad(18.))-lean
    slope_hi = np.tan(theta+np.deg2rad(16.))-lean
    bias=(slope_hi+slope_lo)*.5; amp=(slope_hi-slope_lo)*.5
    primitive=-.73*np.cos(p1)/k1-.27*np.cos(p2)/k2
    d -= bias*v + amp*primitive
    # Gradient of d in world coordinates (scale cancels for metres/metre).
    dlean = .45/.65*(1-np.tanh(x/.65)**2)
    dt = dlean/(1+lean*lean)
    dlo = dt/np.cos(theta-np.deg2rad(18.))**2-dlean
    dhi = dt/np.cos(theta+np.deg2rad(16.))**2-dlean
    slope = bias+amp*wave
    dx = -.36-dlean*y-.55*slope-.5*(dlo+dhi)*v-.5*(dhi-dlo)*primitive
    dy = -lean-slope
    # Duty varies by band and gently along it. The bounded mapping in
    # _type10_mix keeps the calibrated widths inside [.28,.58] of pitch.
    vphase=2*np.pi*v/3.4+phases[i,1]
    width_key=1.45*widths[i]+.68*np.sin(vphase)
    dw=.68*(2*np.pi/3.4)*np.cos(vphase)
    return d, period, width_key, dx, dy, dw


def _type10_mix(coords, offset, scale):
    d, period, key, dx, dy, dw = coords
    f=1/(1+np.exp(-(key+offset)))
    half=.5*period*(.28+.30*f)
    deriv=.15*period*f*(1-f)*dw
    sign=np.sign(d)
    grad=np.sqrt((.55*deriv-sign*dx)**2+(deriv-sign*dy)**2+1)
    distance=(half-np.abs(d))*scale/grad
    return _step(-_T10_EDGE, _T10_EDGE, distance)


def _type10(pos, obj, painted, sc, tris, zone_ids, labels):
    """Area-calibrated hull and turret fields, with a single borrowed cheek colour on the tube."""
    fraction=float(sc.get('brown_fraction',.42)); scale=float(sc['scale'])
    if not .35<=fraction<=.55:
        raise ValueError('type10 brown_fraction must be in [.35,.55]')
    rng=np.random.default_rng(sc['seed']); fields=[_type10_bands(rng) for _ in range(2)]
    kind=np.array([2 if n=='gun_shell' else 1 if n=='turret_shell' else 0 for n in labels],np.int8)
    anchor=np.array([sc.get('cheek_anchor',(.30,1.98,2.23))]); root=_type10_coords(anchor,fields[1],scale)
    cross=sc.get('gun_crossing_z',4.18); gx,gy=sc.get('gun_oblique',(.37,.30)); axis_y=sc.get('bore_y',1.97)
    def prepare(points, owners):
        out=[]
        for k in range(3):
            idx=np.flatnonzero(owners==k)
            if not len(idx): continue
            pp=points[idx]
            if k==2:
                # Signed metre distance to ONE oblique plane, independent of sleeves.
                dist=(pp[:,2]-cross-gx*pp[:,0]-gy*(pp[:,1]-axis_y))/np.sqrt(1+gx*gx+gy*gy)
                data=_step(-_T10_EDGE,_T10_EDGE,dist)
            else:
                data=_type10_coords(pp,fields[k],scale)
            out.append((idx,k,data))
        return out

    def mix(n,groups,offset):
        values=np.empty(n,np.float32); cheek=_type10_mix(root,offset,scale)[0]
        for idx,k,data in groups:
            values[idx]=cheek+(1-2*cheek)*data if k==2 else _type10_mix(data,offset,scale)
        return values

    olive,brown=_rgb(sc['base']),_rgb(sc['brown'])
    base=np.empty((len(pos),3),np.float32); base[:]=olive
    if not painted.any(): return base
    # Uniform samples per square metre, INCLUDING the flexible painted drops.
    sel=np.isin(tris[3],zone_ids); q=tris[0][sel]; owners=kind[tris[4][sel]]
    area=.5*np.linalg.norm(np.cross(q[:,1]-q[:,0],q[:,2]-q[:,0]),axis=1)
    valid=area>0; q=q[valid]; owners=owners[valid]; cdf=np.cumsum(area[valid],dtype=np.float64)
    if not len(cdf): raise ValueError('painted texels but no painted area')
    count=131072; arng=np.random.default_rng(1979)
    tickets=(np.arange(count)+arng.random(count))*(cdf[-1]/count); ii=np.searchsorted(cdf,tickets)
    tri=q[ii]; a=np.sqrt(arng.random((count,1))); b=arng.random((count,1))
    samples=tri[:,0]*(1-a)+a*((1-b)*tri[:,1]+b*tri[:,2])
    groups=prepare(samples,owners[ii]); lo,hi=-16.,16.
    # Solve for the realised colour share after feathering, not a percentile
    # of unweighted atlas pixels. Gun-root inheritance is inside this solve.
    for _ in range(24):
        mid=(lo+hi)*.5; share=mix(count,groups,mid).mean(dtype=np.float64)
        if share<fraction: lo=mid
        else: hi=mid
    offset=(lo+hi)*.5
    share=mix(count,groups,offset).mean(dtype=np.float64)
    print(f'CAMO type10 paint_m2={cdf[-1]:.2f} brown_target={fraction:.3f} brown_area={share:.3f} edge10_90_m=.050')
    ids=np.flatnonzero(painted)
    for j in range(0,len(ids),65536):
        ix=ids[j:j+65536]; alpha=mix(len(ix),prepare(pos[ix],kind[obj[ix]]),offset)
        base[ix]=_mix(olive,brown,alpha)
    return base


# Five-row stencil, most significant bit at the reader's left.
_DIGITS = ((7,5,5,5,7), (2,6,2,2,7), (7,1,7,4,7), (7,1,7,1,7),
           (5,5,7,1,1), (7,4,7,1,7), (7,4,7,5,7), (7,1,2,2,2),
           (7,5,7,5,7), (7,5,7,1,7))


def _stencils(base, pos, obj, labels, painted, markings):
    for mark in markings:
        face = mark['face']
        if face not in ('front', 'rear'):
            raise ValueError('stencil face must be front or rear')
        text = mark.get('text', '92-0417')
        if not text or any(c not in '0123456789-' for c in text):
            raise ValueError('stencil text accepts only digits and hyphens')
        h = float(mark['height'])
        depth = float(mark.get('depth', h))
        if not (h > 0 and depth > 0):
            raise ValueError('stencil height and depth must be positive')
        cx, cy, cz = mark['center']
        name = mark.get('object', 'hull_shell')
        take = painted & np.isin(obj, [i for i, n in enumerate(labels) if n == name])
        cell = h/5
        sign = 1 if face == 'front' else -1
        if 'normal' in mark:
            n=np.array(mark['normal'],float); n/=np.linalg.norm(n)
            right=np.array(mark.get('right',(sign,0,0)),float); right-=n*(right@n); right/=np.linalg.norm(right)
            up=np.cross(n,right); ids=np.flatnonzero(take); rel=pos[ids]-np.array((cx,cy,cz),np.float32)
            xx=rel@right; yy=rel@up; slab=np.abs(rel@n)<=mark.get('depth',.012)
            width=mark.get('width',(4*len(text)-1)*cell)
            ok=slab & (abs(xx)<=width/2) & (abs(yy)<=h/2)
            ids=ids[ok]; col=np.floor((xx[ok]/width+.5)*(4*len(text)-1)).astype(int)
            row=np.floor((.5-yy[ok]/h)*5).astype(int)
        else:
            ids = np.flatnonzero(take & (abs(pos[:, 2] - cz) <= depth) & (abs(pos[:, 1] - cy) <= h/2))
            col = np.floor(sign*(pos[ids, 0]-cx)/cell + (4*len(text)-1)/2).astype(int)
            row = np.floor((cy-pos[ids, 1])/cell + 2.5).astype(int)
        glyphs = np.array([_DIGITS[int(c)] if c != '-' else (0,0,7,0,0) for c in text])
        inside = (col >= 0) & (col < 4*len(text)-1) & (col%4 < 3) & (row >= 0) & (row < 5)
        col, row, ids = col[inside], row[inside], ids[inside]
        bits = glyphs[col//4, row] & (4 >> (col%4))
        base[ids[bits != 0]] = _rgb(mark.get('colour', '#DAD9C8'))


def _zone_style(mat, colour):
    p = next((n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None) if mat.use_nodes else None
    rgb = p.inputs['Base Color'].default_value if p else mat.diffuse_color
    rough = p.inputs['Roughness'].default_value if p else mat.roughness
    metal = p.inputs['Metallic'].default_value if p else mat.metallic
    return (_rgb(colour) if colour is not None else np.asarray(rgb[:3], np.float32), rough, metal)


def _hull_maps(tris, raster, ao, sc, names, marks, ppm, labels=(), styles=None, markings=()):
    fill = raster['fill']
    pos = raster['pos'][fill]
    x, y, z = pos.T
    zone = raster['zone'][fill]
    zones = tris[-1]

    def zone_id(key):
        name = names.get(key, key)
        return zones.index(name) if name in zones else -2

    # Broad swathes climbing from skirt to deck. Warp in three dimensions so
    # the colours meet at plate corners and across separately packed parts.
    s = float(sc['scale'])
    if s <= 0:
        raise ValueError('camo scale must be positive')
    obj = raster['obj'][fill]
    pid = zone_id('tank_paint')
    painted = zone == pid
    type10 = sc.get('pattern', 'legacy') == 'type10'
    if type10:
        drop_id=zone_id('camo_drop'); drops=zone==drop_id
        base = _type10(pos,obj,painted|drops,sc,tris,(pid,drop_id),labels)
        base[drops] *= sc.get('drop_gain',.80)
    else:
        phase = np.random.default_rng(sc['seed']).uniform(-np.pi, np.pi, 4)
        u, v, w = x / s, y / s, z / s
        wave = np.sin(2.25*w + 1.45*v + 0.85*u + phase[0] + 1.25*np.sin(1.5*u - 1.1*v + phase[1]))
        wave += 0.60*np.sin(2.4*u - 1.65*v + 1.2*w + phase[2]) + 0.16*np.sin(4.4*w - 3*v + phase[3])
        olive = _rgb(sc['base'])
        base = _mix(olive, _rgb(sc['green']), 1 - _step(-0.10, 0.02, wave))
        base = _mix(base, _rgb(sc['brown']), _step(-0.015, 0.115, wave))
    rough = np.full(len(x), 0.75, np.float32)
    metal = np.zeros_like(rough)
    for key, (colour, r, m) in PLAIN.items():
        take = zone == zone_id(key)
        base[take], rough[take], metal[take] = _rgb(colour), r, m

    if type10:
        rubber = zone == zone_id('rubber')
        discs = [i for i, n in enumerate(labels) if n.startswith('disc_')]
        base[rubber] = _rgb('#34372F')
        base[rubber & np.isin(obj, discs)] = _rgb('#2C2E29')
    for key, (rgb, r, m) in (styles or {}).items():
        take = zone == zone_id(key)
        if not (type10 and key=='camo_drop'):
            base[take] = rgb
        rough[take], metal[take] = r, m

    features = _plate_edges(tris, pid)
    for mark in marks:
        kind = mark['kind']
        if kind not in ('bolt', 'seam'):
            raise ValueError(f'unknown mark kind: {kind}')
        features.append((mark['a'], mark['b'], kind, mark['radius'], mark['height'], None))
    height, ink = _relief(pos, obj, painted, features)
    if type10 or 'rack_mesh' in (styles or {}):
        rack = zone == zone_id('rack_mesh')
        # A continuous horizontal coordinate around axis-aligned rack corners.
        # Draw both diagonals into the opaque panel, with a raised wire profile.
        side = x[rack] + z[rack]
        up = 1.35*y[rack]
        pitch = 0.11
        wire_dist = np.minimum(abs(((side+up)/pitch + 0.5) % 1 - 0.5),
                               abs(((side-up)/pitch + 0.5) % 1 - 0.5))
        wire = 1 - _step(0.045, 0.16, wire_dist)
        base[rack] *= (0.32 + 0.95*wire)[:, None]
        height[rack] += 0.003*wire
    _stencils(base, pos, obj, labels, painted, markings)
    cloud = np.sin(5.3*x + 2.6*z) * np.sin(4.1*y - 3.5*z + np.sin(5*x))
    dirt = np.clip(sc['dust_strength'] * (1 - _step(0.26, 1.65, y)) * (0.8 + 0.2*cloud), 0, 1)
    dirt[zone == zone_id('glass_dark')] = 0
    if type10 and np.any(drops):
        # Keep mudflaps, tyres and the stowage bag out of the skirt treatment.
        seams=np.asarray(sc.get('drop_seams',(1.,-1.))); feet=np.asarray(sc.get('drop_bottom',(.30,)))
        panel=np.clip(np.searchsorted(-seams[1:],-z[drops]),0,len(feet)-1)
        low,high=sc.get('drop_dirt',(.10,.30)); top=sc.get('drop_top',.765)
        dirt[drops]=low+(high-low)*(1-_step(feet[panel],top,y[drops]))
    visibility = ao[fill]
    base = _mix(base, _rgb(sc['dust']), dirt)
    base *= ((1 + 0.035*cloud) * (1 - ink) * (0.86 + 0.14*visibility))[:, None]
    weathered_rough=rough+(0.95-rough)*dirt
    if type10: weathered_rough[drops]=rough[drops]
    orm = np.column_stack([visibility, weathered_rough, metal*(1 - dirt)])

    def sheet(a, background):
        out = np.full(fill.shape + a.shape[1:], background, np.float32)
        out[fill] = a
        return out

    normal = JA.normal_from_height(sheet(height, 0), 1 / (ppm * len(fill)))
    normal[~fill] = (0.5, 0.5, 1)
    return sheet(base, 0.1), sheet(orm, (1, 0.8, 0)), normal


def paint_tank(objects, mats, scheme, size, workdir, density=None, marks=None, *, markings=()):
    """Return the applied hull material. scheme overrides DEFAULT_SCHEME;
    density(object, material_name) is a relative UV density as in JA.unwrap.
    Mark a..b is a segment (a=b for a point bolt); height is signed metres.
    Build in the neutral pose, before posing/animating the exported model.

    scheme={'pattern': 'type10', 'brown_fraction': 0.42,
            'zones': {'amber_lens': None}} selects the two-colour skin.
    base/brown override its two swatches; scale multiplies the band dimensions.
    brown_fraction (.35.. .55) targets the fraction of physical painted area
    after feathering and before dust. camo_drop continues the hull mask on
    rubber; the turret has its own field. The tube inherits cheek_anchor colour
    up to a single oblique transition. Unpainted rubber uses the rubber zone. Assign rack_mesh
    to the opaque lower rack panel only (no alpha, geometry or UV overlay).
    zones maps optional material keys to None (input Principled swatch) or
    an sRGB hex override. Roughness/metallic use the input scalar defaults;
    linked textures aren't sampled. Type10 samples rack_mesh and amber_lens
    automatically when present. Existing lamp and belt shaders are kept.

    markings is independent of relief marks. Example (centres supplied by rig):
      markings=[dict(face='front', center=front_xyz, height=0.14),
                dict(face='rear', center=rear_xyz, height=0.14)]
    Height is full glyph height in metres. Both project onto tank_paint on
    object='hull_shell', in a +/- depth slab about center.z (depth defaults
    to height). Place centres on the intended plates. Optional text (digits
    and hyphens, default '92-0417') and colour (sRGB hex). Only albedo pixels
    change; the rear reads from the opposite direction. No decal meshes.
    """
    objects = [ob for ob in objects if ob.type == 'MESH' and len(ob.data.polygons)]
    names = {key: m.name for key, m in mats.mats.items()}
    keep = tuple(names.get(k, k) for k in KEEP)
    body, restore = [], []
    for ob in objects:
        me = ob.data
        keep_slots = {i for i, m in enumerate(me.materials) if m.name in keep}
        if all(p.material_index in keep_slots for p in me.polygons):
            continue  # in particular, do not unwrap the scrolling belts
        if me.users > 1:
            ob.data = me = me.copy()
        body.append(ob)
        if keep_slots and me.uv_layers.active:
            loops = [i for p in me.polygons if p.material_index in keep_slots for i in p.loop_indices]
            uv = me.uv_layers.active.data
            restore.append((me, [(i, uv[i].uv[:]) for i in loops]))
    if not body:
        raise ValueError('no hull faces to paint')
    options = scheme or {}
    pattern = options.get('pattern', 'legacy')
    if pattern not in ('type10', 'legacy'):
        raise ValueError(f'unknown camo pattern: {pattern}')
    swatches = dict(base='#485242', green='#485242', brown='#5E5545') if pattern == 'type10' else {}
    sc = {**DEFAULT_SCHEME, **swatches, **options}
    zones = dict(rack_mesh=None, amber_lens=None) if pattern == 'type10' else {}
    zones.update(sc.get('zones', {}))
    styles = {key: _zone_style(mats.mats[key], colour) for key, colour in zones.items()
              if key in mats.mats}
    bpy.context.view_layer.update()
    ppm = JA.unwrap(body, density=density, angle=52.0)
    try:
        tris = JA.triangles(body, skip=keep)
        # Sample AO on a cheap atlas, but cast against the complete vehicle,
        # including the belts. Floor is ground level in this coordinate frame.
        low = JA.raster(tris, max(1, min(512, size // 4)), pad=3)
        ao = JA.occlusion(JA.triangles(objects), low, reach=1.1, rays=16, floor=0.0)
        del low
        ao = JA.blur(JA.resize(ao, size), 1)
        raster = JA.raster(tris, size)
        maps = _hull_maps(tris, raster, ao, sc, names, marks or (), ppm,
                          [ob.name for ob in body], styles, markings or ())
        files = _save(workdir, 'tank_', *maps)
    finally:
        # A mixed mesh can contain both atlas and scrolling faces. Its atlas
        # layer is UV0 now; put the original UVs back on only the latter faces.
        for me, saved in restore:
            uv = me.uv_layers.active.data
            for i, value in saved:
                uv[i].uv = value
    mat = JA.material('armor', files)
    # Workbench TEXTURE uses the active image node, not the Principled graph.
    mat.node_tree.nodes.active = next(n for n in mat.node_tree.nodes if getattr(n, 'image', None) == files['base'])
    mat.diffuse_color = K.srgb(sc['base'] if pattern == 'type10' else sc['green'])
    mats.mats['armor'] = mat
    JA.apply(body, mat, keep=keep)
    return mat


def _track_maps(rg, tile_links, metal_tint='#58554d'):
    if int(tile_links) != tile_links or tile_links < 1:
        raise ValueError('tile_links must be a positive integer')
    width, pitch = rg.track_width, rg.pitch
    if width <= 0 or pitch <= 0 or not 0 <= rg.pad_share <= 1 or rg.horns not in (1, 2) or rg.horn_width <= 0:
        raise ValueError('invalid track dimensions')
    size = 512
    v, u = (np.indices((size, size), dtype=np.float32) + 0.5) / size
    # x across the shoe, y along one link, both measured from its centre.
    x = (u - 0.5) * width
    y = ((v * tile_links) % 1 - 0.5) * pitch
    ax, ay = abs(x), abs(y)
    aa = max(width, pitch * tile_links) / size

    def inside(signed_distance):
        return 1 - _step(-aa, aa, signed_distance)

    body = inside(np.maximum(ax - 0.476*width, ay - 0.438*pitch))
    # End connectors bridge the gap *between* links at the two margins.
    lug = inside(np.maximum(abs(ax - 0.42*width) - 0.048*width, 0.29*pitch - ay))
    pin = inside(np.hypot(ax - 0.42*width, pitch/2 - ay) - 0.09*pitch)
    # Rounded pad corners; the unpadded shoulders show the steel casting.
    r = min(0.10*pitch, rg.pad_share*pitch*.18)
    px, py = ax - 0.33*width + r, ay - rg.pad_share*pitch/2 + r
    pad_dist = np.hypot(np.maximum(px, 0), np.maximum(py, 0)) + np.minimum(np.maximum(px, py), 0) - r
    pad = inside(pad_dist) * body if rg.pad_share else np.zeros_like(body)
    # Horn-root dirt on the centre line or two flanking lines. Broken up in V
    # with integer-frequency fields so the final link meets the first one.
    horn_x = 0 if rg.horns == 1 else width * 0.442
    dirt = np.exp(-((ax - horn_x) / (rg.horn_width*0.70))**2) * _step(0.18*pitch, 0.46*pitch, ay)
    tau = 2*np.pi
    grain = np.sin(tau*(83*u + 47*v)) * np.sin(tau*(19*u - 31*v))
    mottling = np.sin(tau*(7*u + 3*v) + 0.8*np.sin(tau*5*v))
    wear = body * _step(0.32*pitch, 0.425*pitch, ay) * (0.67 + 0.28*mottling)
    steel = np.maximum(body, lug)
    base = _mix(_rgb('#292825'), _rgb(metal_tint), steel)
    base = _mix(base, _rgb('#9b9991'), np.maximum(wear, pin))
    base = _mix(base, _rgb('#343533'), pad)
    base = _mix(base, _rgb('#746550'), dirt * (1 - pad) * 0.64)
    base *= (1 + 0.06*grain + 0.045*mottling)[..., None]
    orm = np.stack([0.54 + 0.46*np.maximum(steel, pad),
                    0.82 - 0.24*steel - 0.16*wear + 0.31*pad + 0.06*dirt,
                    steel * (0.77 + 0.19*wear) * (1 - pad) * (1 - 0.7*dirt)], axis=2)
    height = 0.006*body + 0.008*lug + 0.002*pin + 0.012*pad + 0.00025*grain
    # One texel is not square in metres. Wrapped central differences keep
    # both tangent slopes continuous when the runtime scrolls V past 1.
    dx = (np.roll(height, -1, 1) - np.roll(height, 1, 1)) * size / (2*width)
    dy = (np.roll(height, -1, 0) - np.roll(height, 1, 0)) * size / (2*pitch*tile_links)
    n = np.stack([-dx, -dy, np.ones_like(dx)], axis=2)
    return base, orm, 0.5 + 0.5*n / np.linalg.norm(n, axis=2, keepdims=True)


def _wire_track(mat, files, occlusion_group):
    nt = mat.node_tree
    p = nt.nodes['Principled BSDF']

    def tex(key):
        node = nt.nodes.new('ShaderNodeTexImage')
        node.image = files[key]
        node.extension = 'REPEAT'
        return node.outputs['Color']

    nt.links.new(tex('base'), p.inputs['Base Color'])
    sep = nt.nodes.new('ShaderNodeSeparateColor')
    nt.links.new(tex('orm'), sep.inputs[0])
    nt.links.new(sep.outputs[1], p.inputs['Roughness'])
    nt.links.new(sep.outputs[2], p.inputs['Metallic'])
    group = nt.nodes.new('ShaderNodeGroup')
    group.node_tree = occlusion_group
    nt.links.new(sep.outputs[0], group.inputs['Occlusion'])
    nm = nt.nodes.new('ShaderNodeNormalMap')
    nt.links.new(tex('normal'), nm.inputs['Color'])
    nt.links.new(nm.outputs[0], p.inputs['Normal'])
    nt.nodes.active = next(n for n in nt.nodes if getattr(n, 'image', None) == files['base'])


def paint_tracks(mats, rg, workdir, tile_links=8, *, metal_tint='#58554d'):
    """Wire the same three 512px images into both existing track materials.
    U spans track_width, V spans pitch * tile_links metres (= runtime trackV).
    pad_share is the rubber fraction of each pitch; widths and pitch in metres.
    metal_tint is the cast shoe's sRGB hex colour (use '#59564C' for Type10);
    rubber pads, worn edges and the scrolling UVs are unchanged.
    Returns the shared Blender images by key (base, orm, normal).
    """
    left, right = mats['track_l'], mats['track_r']
    files = _save(workdir, 'track_', *_track_maps(rg, tile_links, metal_tint))
    group = bpy.data.node_groups.get('glTF Material Output')
    if group is None:
        group = bpy.data.node_groups.new('glTF Material Output', 'ShaderNodeTree')
        group.interface.new_socket('Occlusion', in_out='INPUT', socket_type='NodeSocketFloat')
    for mat in (left, right):
        _wire_track(mat, files, group)
    return files
