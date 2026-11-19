"""Reusable cosmetic Parts. All positions use the kit's game frame."""
import math
import numpy as np
import tank_kit as T


def tiered_plate(tiers, mat=T.PAINT):
    """Loft horizontal tiers, bottom first. Each is (height m, cyclic [(x,z) m]); either winding."""
    rows = [[(x, y, z) for x, z in plan] for y, plan in tiers]
    if len(rows) < 2 or len(rows[0]) < 3 or any(len(r) != len(rows[0]) for r in rows):
        raise ValueError('inconsistent plan rings')
    # In the game frame +x cross +z points DOWN.
    area = sum(a[0]*b[2]-a[2]*b[0] for a,b in zip(rows[0],rows[0][1:]+rows[0][:1]))
    p = T.Part('tiered_plate')
    p.loft(rows if area < 0 else [r[::-1] for r in rows], mat, cap0=True, cap1=True,
           cap_centre=False, smooth=False)
    return p


def piping(path, radius, mat=T.PAINT, segments=8):
    """Solid round rail along xyz path (m), stock radius (m), segments per section."""
    from jet_kit import frame_along
    c, _, n, b = frame_along(path)
    t = np.arange(segments)*math.tau/segments
    p = T.Part('pipe')
    p.loft([a+radius*(np.outer(np.cos(t),v)+np.outer(np.sin(t),w)) for a,v,w in zip(c,n,b)],
           mat, cap0=True, cap1=True)
    return p


def turning(centre, axis, profile, mat=T.PAINT, segments=32, caps=(True,True), bands=None):
    """Turn [(axial distance, radius) m] around unit direction from centre xyz (m).
    List stations from base to tip; fold back inside for a lip. bands optionally names each span.
    caps closes base/tip (bool or material name). Returns a Part, not an object.
    """
    p = T.Part('turning')
    p.revolve(mat, [(r,d) for d,r in reversed(profile)], centre, axis, seg=segments,
              cap0=caps[1], cap1=caps[0], mat_of=(lambda i: bands[-1-i]) if bands else None)
    return p


def bezel(centre, direction, radius, depth, lens):
    """Round lamp, centre xyz at the lens face (m), outward direction, radius/depth (m), lens material."""
    prof = [(-depth,.87*radius),(-.85*depth,radius),(0,radius),(0,.83*radius),(-.17*depth,.74*radius)]
    return turning(centre,direction,prof,segments=24,caps=(True,lens),bands=[T.PAINT,T.PAINT,'steel','recess'])


def ring(centre, outer, inner, height, mat=T.PAINT, segments=40):
    """Horizontal annulus with base at centre xyz (m), outer/inner radii and height (m)."""
    prof = [(0,outer),(height,outer),(height,inner),(0,inner),(0,outer)]
    return turning(centre,(0,1,0),prof,mat,segments,caps=(False,False))


def face_grille(centre, size, slats, outward):
    """Vertical transom louvres. centre xyz (m), size=(width,depth,height) m, slat count, outward z sign."""
    p = T.grille((0,0,0),size,slats)
    matrix = np.eye(4); matrix[:3,:3] = ((1,0,0),(0,0,-outward),(0,outward,0))
    matrix[:3,3] = centre
    p.transform(matrix)
    return p


def paired_disc(radius, width, tread, rubber, dish, bolts, bolt_radius, segments, outer='rubber'):
    """Axle-local twin wheels. Radius, total width, tyre width/depth, dish inset and bolt_radius in m;
    bolts counts studs per exposed face, segments sets rim resolution, outer names the tread zone.
    """
    inner=radius-rubber; parts=[]
    for side in (-1,1):
        centre=(side*(width-tread)/2,0,0); axis=(side,0,0); h=tread/2
        profile=[(-h,.26*radius),(-h,.70*inner),(-h,.96*radius),(-.87*h,radius),
                 (.87*h,radius),(h,.975*radius),(h,inner),(h+.012*tread,inner*.94),
                 (h-dish,inner*.69),(h-dish,inner*.39),(h+.12*tread,inner*.30),
                 (h+.18*tread,inner*.19)]
        parts.append(turning(centre,axis,profile,segments=segments,
                             bands=[T.PAINT,T.PAINT,outer,outer,outer,outer,'steel',T.PAINT,T.PAINT,T.PAINT,'steel']))
        for i in range(bolts):
            theta=math.tau*i/bolts; rr=inner*.47
            pt=(centre[0]+side*(h-dish),rr*math.cos(theta),rr*math.sin(theta))
            parts.append(turning(pt,axis,[(0,bolt_radius),(bolt_radius*.54,bolt_radius),
                                          (bolt_radius*.67,.84*bolt_radius)],'steel',6,caps=(False,True)))
    return T.combine('paired disc',parts)


def spoked_drive(radius,width,teeth,spokes,spoke_width,bolts,bolt_radius,segments):
    """Open cosmetic drive wheel at axle origin. Radius, axial width, spoke_width and bolt_radius in m;
    teeth/spokes/bolts are counts per cheek, segments samples the central hub circumference.
    """
    parts=[]; hub=.36*radius
    parts.append(turning((0,0,0),(1,0,0),[(width*x,radius*r) for x,r in
                         ((-.51,.24),(-.49,.35),(-.36,.39),(-.27,.29),(.27,.29),(.36,.39),(.49,.35),(.51,.24))],segments=segments))
    for side in (-1,1):
        p=T.Part('tooth ring'); angles=[math.tau*(i+f)/teeth for i in range(teeth) for f in (0,.28,.56,.84)]
        scales=[.87,1,1,.87]*teeth
        # In the yz plane the positive cyclic winding points down +X.
        x0,x1=sorted((side*width*.39,side*width*.49))
        rings=[[(x,radius*r*math.cos(a),radius*r*math.sin(a)) for a,r in zip(angles,rr)]
               for x,rr in ((x0,scales),(x1,scales),(x1,[.72]*len(angles)),(x0,[.72]*len(angles)))]
        p.grid(rings,'steel',closed_u=True,closed_v=True,smooth=False)
        for i in range(spokes):
            a=math.tau*i/spokes; v=np.array([0,math.cos(a),math.sin(a)]); tangent=np.cross((1,0,0),v)
            c=np.array([side*width*.44,0,0])+v*(.54*radius)
            p.obox(T.PAINT,c,(.098*width,.44*radius,spoke_width),((1,0,0),v,tangent))
        parts.append(p)
        for i in range(bolts):
            a=math.tau*i/bolts; pt=(side*.50*width,.80*hub*math.cos(a),.80*hub*math.sin(a))
            parts.append(turning(pt,(side,0,0),[(0,bolt_radius),(.50*bolt_radius,bolt_radius),(.68*bolt_radius,.86*bolt_radius)],'steel',6,caps=(False,True)))
    return T.combine('open drive',parts)


def linked_band(rg,side,spec,tile_links=8):
    """Metric scrolling band around a RunningGear pitch path (m). side='l'/'r'; spec gives shoe,
    pad and connector extents as fractions of pitch/width/half-thickness; tile_links is pitches per UV repeat.
    """
    path,arc,_=T.track_path(rg); length=arc[-1]; count=round(length/rg.pitch); step=length/count
    w=rg.track_width; h=rg.track_thickness/2; xc=rg.track_centre*(1 if side=='l' else -1)
    p=T.Part('band_'+side); mat='track_'+side; tile=rg.pitch*tile_links
    def sample(d):
        d=d%length; i=np.searchsorted(arc,d,side='right')-1
        return path[i]+(path[i+1]-path[i])*((d-arc[i])/(arc[i+1]-arc[i]))
    def point(d,x,r):
        z,y=sample(d); tz,ty=sample(d+.002)-sample(d-.002); n=math.hypot(tz,ty)
        return (xc+x*w,y+r*tz/n,z-r*ty/n)
    def block(d,lo,hi,span,r0,r1,base=True,top=True):
        # Rings in x / path direction. Tangent cross across points outwards.
        coords=[(x,dd) for x,dd in ((lo,d-span),(lo,d+span),(hi,d+span),(hi,d-span))]
        rows=[[point(dd,x,r) for x,dd in coords] for r in (r0,r1)]
        def face(indices,edge=None):
            f=p.face([rows[k//4][k%4] for k in indices],mat,False)
            for loop,k in zip(f.loops,indices):
                x,dd=coords[k%4]; depth=0 if k<4 else r1-r0
                # Unfold each vertical wall in UV as well; a collapsed side
                # quad has no tangent frame for the scrolling normal map.
                if edge in (0,2): x+=depth/w*(1 if edge==0 else -1)
                if edge in (1,3): dd+=depth*(1 if edge==1 else -1)
                loop[p.uv].uv=(.5+x,1-dd/tile)
        if base: face((3,2,1,0))
        if top: face((4,5,6,7))
        for j in range(4):
            k=(j+1)%4; face((j,k,k+4,j+4),j)
    for i in range(count):
        d=(i+.5)*step; top=h*spec['steel_top']; half=spec['half']
        block(d,-half,half,step*spec['body']/2,-h,top)
        for s in (-1,1):
            lo,hi=sorted((s*spec['pad_inner'],s*spec['pad_outer']))
            block(d,lo,hi,step*rg.pad_share/2,top,h,False)
            a,b,span=spec['connector']; lo,hi=sorted((s*a,s*b))
            block(i*step,lo,hi,step*span,-.68*h,.82*h)
            x=s*.442; half=rg.horn_width/(2*w)
            block(d,x-half,x+half,step*.13,-h-rg.horn_height,-h,top=False)
    return p
