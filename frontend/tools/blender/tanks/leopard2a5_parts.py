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


def round_screen(centre, radius, depth, pitch, bar, segments=32):
    """Rear-facing circular screen. centre is at the lip (xyz m); radius, inset
    depth, horizontal bar pitch and bar radius are metres. segments samples the rim.
    """
    rr=radius-bar*2
    parts=[turning(centre,(0,0,-1),[(-depth,radius),(0,radius),(0,rr),
                   (-.75*depth,rr)],segments=segments,caps=(False,'recess'),
                   bands=[T.PAINT,'steel','recess'])]
    x,y,z=centre
    for i in range(-int(rr/pitch),int(rr/pitch)+1):
        dy=i*pitch; dx=math.sqrt(rr**2-dy**2)
        parts.append(piping([(x-dx,y+dy,z+depth*.38),(x+dx,y+dy,z+depth*.38)],bar,'steel',6))
    return T.combine('round screen',parts)


def laid_cable(path, radius, lay, sides=8):
    """Laid cable on an ordered xyz polyline (m). radius = outer radius (m),
    lay = axial length per turn (m), sides = core section samples. One relief
    strand catches highlights without meshing a bundle of individual wires.
    """
    from jet_kit import frame_along
    knots=np.asarray(path,float); arc=np.r_[0.,np.cumsum(np.linalg.norm(np.diff(knots,axis=0),axis=1))]
    ds=np.unique(np.r_[arc,np.linspace(0,arc[-1],int(math.ceil(arc[-1]*7/lay))+1)])
    xyz=np.column_stack([np.interp(ds,arc,col) for col in knots.T]); xyz,t,n,b=frame_along(xyz)
    phase=ds[:,None]*math.tau/lay
    strand=xyz+.77*radius*(np.cos(phase)*n+np.sin(phase)*b)
    return T.combine('laid cable',[piping(path,.84*radius,'steel',sides),piping(strand,.23*radius,'steel',5)])


def under_rim(stations, bottom, wall, mat='recess'):
    """Closed hollow rim. stations = increasing (z, half-width, top y) in m;
    bottom = level base y (m), wall = horizontal inset to the inner surface (m).
    """
    from jet_kit import offset_poly
    z,x,y=np.asarray(stations).T
    plan=list(zip(-x,z))+list(zip(x[::-1],z[::-1]))  # +Y winding
    inner=offset_poly(plan,-wall)
    def row(poly,top):
        return [(xx,float(np.interp(zz,z,y)) if top else bottom,zz) for xx,zz in poly]
    p=T.Part('under rim')
    p.grid([row(plan,False),row(plan,True),row(inner,True),row(inner,False)],
           mat,smooth=False,closed_u=True,closed_v=True)
    return p


def link_guides(band, centre_x, web_width, z_limits, max_y, size, crown, tile):
    """Append tapered guides to a built band mesh in its local game frame.
    centre_x, full inner web_width, inclusive z_limits, max face y, xyz size
    and UV tile length are metres; crown is the top/foot linear size ratio.
    One guide per upward web quad (not per resampled station). Return count.
    """
    import bmesh
    bm=bmesh.new(); me=band.data; count=0
    try:
        bm.from_mesh(me); bm.normal_update(); uv=bm.loops.layers.uv.active
        if uv is None: raise ValueError('band has no link UVs')
        for f in list(bm.faces):
            if len(f.verts)!=4 or f.normal.z<.9: continue
            q=np.array([T.G(v.co) for v in f.verts]); c=q.mean(axis=0)
            if c[1]>=max_y or not z_limits[0]<=c[2]<=z_limits[1]: continue
            if abs(c[0]-centre_x)>1e-4 or abs(np.ptp(q[:,0])-web_width)>1e-4: continue
            # +Z tangent and inward normal of this actual link, including grade.
            q=q[np.argsort(q[:,2])]; forward=q[2:].mean(axis=0)-q[:2].mean(axis=0)
            forward/=np.linalg.norm(forward); up=np.cross(forward,(1.,0.,0.))
            v0=sum(loop[uv].uv.y for loop in f.loops)/4
            rings=[]; coords={}
            for scale,rise in ((1.,0.),(crown,size[1])):
                ring=[]
                for sx,sz in ((-1,-1),(-1,1),(1,1),(1,-1)):
                    dz=sz*size[2]*scale/2
                    v=bm.verts.new(T.B(*(c+(sx*size[0]*scale/2,0,0)+dz*forward+rise*up)))
                    ring.append(v); coords[v]=(.88+sx*.017*scale,v0+dz/tile)
                rings.append(ring)
            a,b=rings
            for vs in [[a[i-1],a[i],b[i],b[i-1]] for i in range(4)]+[b]:
                face=bm.faces.new(vs); face.material_index=f.material_index; face.smooth=False
                for loop in face.loops: loop[uv].uv=coords[loop.vert]
            count+=1
        if not count: raise ValueError('no ground-run web faces on '+band.name)
        bm.normal_update(); bm.to_mesh(me); me.update()
    finally:
        bm.free()
    return count
