"""Exterior mesh primitives for the Abrams. All points and offsets use game axes.
The caller owns the stations; these helpers return unbuilt tank_kit Parts.
"""
import math

import numpy as np
import tank_kit as T


def disc(kind, sign, rg, style):
    """Axle-local shells. Build looking at the outboard face; reverse the axis
    on the other side so both exposed caps are detailed. One mesh per pivot.
    """
    axis=(sign,0,0); o=(0,0,0)
    def lathe(profile,seg,zones):
        return turned(o,axis,profile,seg=seg,bands=zones)
    if kind in ('road','idler'):
        road=kind=='road'; r=rg.road[0][-1] if road else rg.idler[2]
        w=rg.wheel_width if road else rg.idler[3]
        cap=style['hub_x']-rg.track_centre if road else w/2
        face=w/2; gap=rg.horn_width/2+style['guide_clearance']; tyre=rg.tyre_width
        lip=r-rg.tyre_depth; dish=face-rg.dish_depth
        profile=[(.21*r,cap),(.28*r,face),(.39*r,dish),(.77*lip,dish),(.96*lip,face),
                 (lip,face),(r,face-style['shoulder']), (r,face-tyre), (lip,gap),(.23*r,gap)]
        p=[lathe(profile,24,['tank_paint','tank_paint','tank_paint','tank_paint','steel',
                                               'rubber','rubber','rubber','tank_paint'])]
        p.append(lathe([(.24*r,-gap),(lip,-gap),(r,-face+tyre),(r,-face+style['shoulder']),
                        (lip,-face),(.35*r,-face+rg.dish_depth)],16,
                       ['tank_paint','rubber','rubber','rubber','tank_paint']))
        for i in range(rg.hub_bolts if road else 6):
            t=math.tau*i/(rg.hub_bolts if road else 6)
            c=(sign*dish,.45*r*math.cos(t),.45*r*math.sin(t))
            p.append(turned(c,axis,[(style['nut_r'],style['nut_h']),(style['nut_r'],0)],'steel',6))
        return T.combine(kind,p)
    if kind=='roller':
        _,_,r,w=rg.rollers[0]; gap=rg.horn_width/2+style['guide_clearance']
        return T.combine(kind,[lathe([(.45*r,b),(r,b),(r,a),(.45*r,a)],12,['steel','rubber','steel'])
                               for a,b in ((gap,w/2),(-w/2,-gap))])
    _,_,r,n,w=rg.sprocket
    p=[lathe([(.26*r,w/2),(.37*r,.47*w),(.68*r,.30*w),(.80*r,.36*w),
              (.80*r,-.36*w),(.37*r,-.30*w),(.26*r,-w/2)],22,
             ['steel','tank_paint','tank_paint','steel','tank_paint','steel'])]
    # Two annular tooth rings, no radially overlapping full cylinders.
    for side in (-1,1):
        rows=[]
        for xx,teeth in ((.39,True),(.50,True),(.50,False),(.39,False)):
            ring=[]
            for k in range(n):
                for phase,rr in ((0,.86),(.28,1),(.56,1),(.85,.86)):
                    a=math.tau*(k+phase)/n; rad=r*(rr if teeth else .69)
                    ring.append((side*xx*w,rad*math.cos(a),rad*math.sin(a)))
            rows.append(ring)
        part=T.Part('tooth ring'); part.grid(rows,'steel',closed_u=True,closed_v=True,flip=side<0,smooth=False); p.append(part)
    return T.combine(kind,p)


def pair(part):
    part.mirror_x()
    return part


def boxes(spec):
    return [T.cbox(*row) for row in spec]


def turned(centre, axis, profile, mat=T.PAINT, seg=24, bands=None):
    """Profile runs from the high axial station to the low one (radius, offset)."""
    p = T.Part('turning')
    p.revolve(mat, profile, centre, axis=axis, seg=seg, cap0=True, cap1=True,
              mat_of=None if bands is None else bands.__getitem__)
    return p


def rail(path, radius, mat=T.PAINT, seg=8):
    # Loft outward CCW sections rather than smoothing across bends in a box.
    q = np.asarray(path, dtype=float)
    tangents = np.diff(q, axis=0)
    tangents /= np.linalg.norm(tangents, axis=1)[:, None]
    directions = np.vstack([tangents[0], tangents[:-1]+tangents[1:], tangents[-1]])
    directions /= np.linalg.norm(directions, axis=1)[:, None]
    w = directions[0]
    ref = np.eye(3)[np.argmin(abs(w))]
    rings = []
    angles = np.arange(seg)*math.tau/seg
    for c, w in zip(q, directions):
        ref = ref - w*np.dot(ref, w)
        ref /= np.linalg.norm(ref)
        rings.append(c + radius*(np.outer(np.cos(angles), ref) +
                                 np.outer(np.sin(angles), np.cross(w, ref))))
    p = T.Part('rail')
    p.loft(rings, mat, cap0=True, cap1=True, cap_centre=False)
    return p


def skin(rings, mat=T.PAINT):
    """Corresponding plan rings from underside to roof, CCW viewed from above."""
    p = T.Part('plate shell')
    _, rows=p.grid(rings,mat,closed_u=True,smooth=False)
    # Each level runs from the notch along the left cheek to the bustle,
    # then back along the right. Patch both cheek tops individually. After
    # the notch shoulder, bridge matching side stations across the roof.
    # These use the sidewall's actual vertices, including the notch wall.
    for level,flip in ((0,True),(-1,False)):
        row=rows[level]; half=len(row)//2; right=lambda k:len(row)-1-k
        def cap(ids):
            vs=[row[k] for k in ids]; face=p.bm.faces.new(vs[::-1] if flip else vs)
            face.material_index=p.slot(mat); face.smooth=False
        # 0 = recess back, 1 = inner lip, 2 = outer break, 3 = first side
        # station behind the recess. No polygon runs across the notch.
        for k in (1,2):
            cap([0,k,k+1]); cap([right(k+1),right(k),right(0)])
        cap([right(0),0,3,right(3)])
        for i in range(3,half-1): cap([right(i),i,i+1,right(i+1)])
    return p


def skirt(spec, outer, marks):
    parts = []
    bottom = spec['bottom']
    def top(z): return float(np.interp(z,spec['top_z'],spec['top_y']))
    for i, (a, b) in enumerate(zip(spec['cuts'], spec['cuts'][1:])):
        heavy = i >= len(spec['cuts'])-3
        x = outer if heavy else outer-spec['setback']
        thick = spec['heavy'] if heavy else spec['light']
        a += spec['gap']/2
        b -= spec['gap']/2
        # The cut line is shared by the steel panel and its rubber strip.
        if i == 0:
            edge = [(a+dz, bottom+dy) for dz, dy in spec['rear_cut']] + [(b, bottom)]
        elif i == len(spec['cuts'])-2:
            edge = [(a, bottom), (b-spec['nose_cut'], bottom), (b, top(b)-spec['nose_lip'])]
        else:
            edge = [(a, bottom), (b, bottom)]
        h = 0 if heavy else spec['rubber']
        seam = [(z,y+h) for z,y in edge]
        parts.append(T.prism(seam+[(b,top(b)),(a,top(a))], x-thick, x))
        if h:
            parts.append(T.prism(edge+seam[::-1], x-thick, x-spec['lip'], 'rubber'))
        size = spec['hinge_size']; face_x = x+size[0]
        for t in spec['hinges']:
            z = a+(b-a)*t; y = top(z)
            parts.append(T.cbox((x+size[0]/2,y-size[1]/4,z),size,spec['bevel']))
            # The back tangent of each barrel sits on the exposed latch face.
            for off in spec['knuckles']:
                parts.append(turned((face_x+spec['pin_r'],y,z+off),(0,0,1),
                             [(spec['pin_r'],spec['pin_len']/2),(spec['pin_r'],-spec['pin_len']/2)],T.PAINT,12))
            for dy in spec['strap_bolts']:
                parts.append(turned((face_x,y-dy,z),(1,0,0),
                             [(spec['stud_r'],spec['stud_h']),(spec['stud_r'],0)],T.PAINT,6))
        for s in (-1,1):
            T.bolt_row(marks,(s*x,top(a)-spec['bolt_drop'],a+spec['inset']),
                       (s*x,top(b)-spec['bolt_drop'],b-spec['inset']),4,
                       radius=spec['bolt_r'],height=spec['bolt_h'],normal=(s,0,0)).bm.free()
    return pair(T.combine('aprons',parts))


def guarded_lamp(spec):
    p = [turned((x,y,z),(0,0,1),prof,seg=20,bands=zones)
         for (x,y,z),prof,zones in spec['lamps']]
    # Front lens is its own shallow disc; no emissive material on the bezel.
    for centre, profile in spec['lenses']:
        p.append(turned(centre,(0,0,1),profile,'headlight',20))
    p.extend(boxes(spec['feet']))
    p.extend(rail(path,spec['bar']) for path in spec['guards'])
    return pair(T.placed(T.combine('front lamps',p),spec['centre']))


def deck_door(centre,size,count,s):
    x,y,z=centre; w,h,d=size; e=s['edge']; p=[T.grille(centre,size,count)]
    for k in (-1,1):
        p.append(T.cbox((x+k*(w-e)/2,y+h/2,z),(e,h,d),e/4))
        p.append(T.cbox((x,y+h/2,z+k*(d-e)/2),(w-2*e,h,e),e/4))
        c=(x+k*w*.31,y+h,z-d/2); r=s['hinge_r']; half=s['hinge_span']/2
        p.append(turned(c,(1,0,0),[(r,half),(r,-half)],seg=12))
        a=(c[0]-half,y+h,z+d/2); b=(c[0]+half,y+h,z+d/2)
        p.append(rail([a,(a[0],a[1]+s['stand'],a[2]),(b[0],b[1]+s['stand'],b[2]),b],s['bar']))
    return T.combine('intake cover',p)


def exhaust(spec):
    c = np.asarray(spec['centre']); w,h,d = spec['size']; f = spec['frame']
    p = [T.cbox(c,(w,h,d),f/3,'recess')]
    for sign in (-1,1):
        p.extend([T.cbox(c+(sign*(w-f)/2,0,-d/2),(f,h,f),f/4),
                  T.cbox(c+(0,sign*(h-f)/2,-d/2),(w-f*2,f,f),f/4)])
    ax = math.radians(spec['angle']); step = (h-2*f)/spec['count']
    blades = T.Part('louvre blades')
    for i in range(spec['count']):
        blades.obox('steel',c+(0,-h/2+f+(i+.5)*step,-d/2),
                    (w-2*f, step*spec['cover'],spec['gauge']),
                    ((1,0,0),(0,math.cos(ax),math.sin(ax)),(0,-math.sin(ax),math.cos(ax))))
    p.append(blades)
    return T.combine('exhaust',p)


def bustle_rack(s):
    # U-shaped bent rails: the two forward ends terminate at the side bins.
    path = np.array(s['outline']); parts = []
    for y,r in s['rails']:
        parts.append(rail([(x,y,z) for x,z in path],r))
    lo,hi = s['rails'][0][0],s['rails'][-1][0]
    for a,b,n in zip(path,path[1:],s['bays']):
        for t in np.arange(n)/n:
            x,z = a+t*(b-a)
            parts.append(rail([(x,lo,z),(x,hi,z)],s['upright']))
    x,z = path[-1]; parts.append(rail([(x,lo,z),(x,hi,z)],s['upright']))
    # Intersect each floor member with the actual plan. Closing the open
    # front of the U for these queries introduces no geometry there.
    def crossings(axis,value):
        hits=[]
        for a,b in zip(path,np.roll(path,-1,axis=0)):
            d=b[axis]-a[axis]
            if abs(d)>1e-9 and min(a[axis],b[axis])<=value<=max(a[axis],b[axis]):
                hits.append(a[1-axis]+(value-a[axis])/d*(b[1-axis]-a[1-axis]))
        return hits
    def aft(x): return min(crossings(0,x))
    for x in s['bearers']:
        parts.append(rail([(x,lo,aft(x)),(x,lo,s['mount'])],s['upright']))
    # Split bracing at any rail corner it crosses so the brace stays on
    # the back wall even where that wall turns diagonally toward the left.
    for i,(a,b) in enumerate(zip(s['bearers'][::2],s['bearers'][2::2])):
        y0,y1=(lo,hi) if i%2 else (hi,lo)
        xs=[a,*sorted(set(x for x,z in path if a<x<b and z<s['mount'])),b]
        parts.append(rail([(x,y0+(y1-y0)*(x-a)/(b-a),aft(x)) for x in xs],s['wire']))
    for x in s['bearers'][::2]:
        knee=max(aft(x),s['floor_z'][2])
        parts.append(rail([(x,lo,s['mount']),(x,lo,knee),(x,hi,s['mount'])],s['upright']))
    for z in s['floor_z']:
        hits=crossings(1,z); left=max(-s['floor_x'],min(hits)); right=min(s['floor_x'],max(hits))
        parts.append(rail([(left,lo,z),(right,lo,z)],s['wire'],seg=6))
    return T.combine('rack',parts)


def outfit(s):
    """One roof appliance, specified in a mounting frame parallel to the body."""
    p = boxes(s.get('boxes',()))
    p.extend(turned(*row) for row in s.get('turnings',()))
    p.extend(T.periscope(*row) for row in s.get('optics',()))
    p.extend(T.slab(*row) for row in s.get('plates',()))
    p.extend(rail(*row) for row in s.get('rails',()))
    return T.placed(T.combine('appliance',p),s['base'])


def shield(s):
    """Separate armored view panels; the slits between the frames stay open."""
    p=[]; up=np.array((0,1,0)); lo,hi=s['bottom'],s['top']; f=s['frame']
    for x,z,xx,zz in s['panes']:
        a=np.array((x,0.,z)); b=np.array((xx,0.,zz)); u=b-a
        width=np.linalg.norm(u); u/=width; n=np.cross(u,up); mid=(a+b)/2
        pane=T.Part('opaque shield pane'); axes=(u,up,n)
        pane.obox('glass_dark',mid+up*(lo+hi)/2,(width-f,hi-lo-f,s['glass']),axes)
        for end in (a,b):
            pane.obox(T.PAINT,end+up*(lo+hi)/2,(f,hi-lo,s['depth']),axes)
        for y in (lo,hi):
            pane.obox(T.PAINT,mid+y*up,(width+f,f,s['depth']),axes)
        for t in (.18,.82):
            foot=a+(b-a)*t; p.append(rail([foot,foot+lo*up],s['post'],seg=6))
        p.append(pane)
    return T.placed(T.combine('loader shields',p),s['base'])
