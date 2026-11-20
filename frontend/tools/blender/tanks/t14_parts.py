"""Reusable exterior mesh details. All arguments and returned Parts are in game metres."""
import math

import numpy as np
import tank_kit as T


def _unit(vec):
    a = np.asarray(vec, dtype=float)
    length = np.linalg.norm(a)
    if length < 1e-9:
        raise ValueError('zero-length direction')
    return a / length


def _axes(normal):
    n = _unit(normal)
    ref = (0, 1, 0) if abs(n[1]) < .95 else (0, 0, 1)
    u = _unit(np.cross(ref, n))
    return u, np.cross(n, u), n


def shell(rings, mat=T.PAINT):
    """Flat shroud, from horizontal (y, polygon_xz) cuts, bottom to top."""
    rows = [[(x, y, z) for x, z in loop] for y, loop in rings]
    if len(rows) < 2 or len(rows[0]) < 3 or any(len(q) != len(rows[0]) for q in rows):
        raise ValueError('shell requires matching horizontal loops')
    # A roof normal points up: clockwise when plotted on ordinary x/z paper.
    loop = rows[0]
    if sum(a[0]*b[2]-b[0]*a[2] for a,b in zip(loop,loop[1:]+loop[:1])) > 0:
        rows = [row[::-1] for row in rows]
    p = T.Part('faceted shell')
    p.loft(rows, mat, cap0=True, cap1=True, cap_centre=False, smooth=False)
    return p


def rod(path, radius, mat=T.PAINT, segments=8):
    """Bent round stock. Section bisects each bend; end faces are closed."""
    pts = np.asarray(path, dtype=float)
    dirs = [_unit(b-a) for a,b in zip(pts,pts[1:])]
    tangents = [dirs[0], *[_unit(a+b) for a,b in zip(dirs,dirs[1:])], dirs[-1]]
    u, _, _ = _axes(tangents[0]); rows = []
    for c,n in zip(pts,tangents):
        u = _unit(u - n*np.dot(n,u)) if abs(np.dot(n,u)) < .999 else _axes(n)[0]
        v = np.cross(n,u)
        rows.append([c + radius*(math.cos(a)*u + math.sin(a)*v)
                     for a in np.arange(segments)*math.tau/segments])
    p = T.Part('rod'); p.loft(rows,mat,cap0=True,cap1=True,cap_centre=False)
    return p


def slat_cage(x, posts, rear_edge, bottom, top, count, rail, post, turn, mount_x, ties):
    """One screen; rear_edge is a bottom-to-top polyline of (y,z) at the aft post.
    A rail crossing a corner has that same corner cut into its two end faces."""
    depth,h=rail
    heights,ends=zip(*rear_edge)
    if not (heights[0]==bottom and heights[-1]==top and ends[-1]==posts[-1]
            and all(a<b for a,b in zip(heights,heights[1:]))):
        raise ValueError('rear cage profile does not meet its top/bottom stations')
    def edge(y0,y1):
        ys=[y0,*[y for y in heights if y0<y<y1],y1]
        return [(np.interp(y,heights,ends),y) for y in ys]
    def stock(line,width):
        return line+[(z+width,y) for z,y in reversed(line)]
    p=T.Part('slat ties'); parts=[p]
    for y0 in np.linspace(bottom,top-h,count):
        line=edge(y0,y0+h)
        parts.append(T.prism(line+[(posts[0],line[-1][1]),(posts[0],line[0][1])],x-depth,x))
        parts.append(T.prism(stock(line,depth),x-turn,x-depth))
    line=edge(bottom,top)
    parts.append(T.prism(stock(line,post),x-depth-post,x-depth))
    parts.append(T.prism(stock([(z+depth,y) for z,y in line],post),x-turn,x-turn+post))
    for i,z in enumerate(posts[:-1]):
        z0=z-post if i==0 else z
        p.box(T.PAINT,x-depth-post,x-depth,bottom,top,z0,z0+post)
        for y in ties:
            p.box(T.PAINT,mount_x,x-depth-post,y-post/2,y+post/2,z0,z0+post)
    return T.combine('slat screen',parts)


def pocket_triangle(p, triangle, weights, size, rim, depth):
    """Replace one CCW facet by its surround, four reveals and a recessed pane.
    First triangle vertex is the apex, second and third its lower left/right."""
    a,b,c=np.asarray(triangle,dtype=float); centre=np.asarray(weights) @ np.array([a,b,c])
    u,v,n=_axes(np.cross(b-a,c-a)); w,h=size
    outer=[a,b,c,a]
    def rect(w,h):
        return [centre+i*w/2*u+j*h/2*v for i,j in ((-1,1),(-1,-1),(1,-1),(1,1))]
    def strip(out,inside,mat):
        for i in range(4):
            j=(i+1)%4
            pts=[out[i],out[j],inside[j],inside[i]] if not np.array_equal(out[i],out[j]) else [out[i],inside[j],inside[i]]
            p.face(pts,mat,False)
    bezel=rect(w+2*rim,h+2*rim); opening=rect(w,h); pane=[q-depth*n for q in opening]
    strip(outer,bezel,T.PAINT); strip(bezel,opening,'steel'); strip(opening,pane,'recess')
    p.face(pane,'glass_dark',False)


def notched_shroud(rings, slot, window):
    """Left half. The centre plane has no wall: mirror_x plus Part.build welds it.
    Section order is underside, ridge, lid; point order is centre bow around to stern."""
    p=T.Part('shroud'); rows=[[(x,y,z) for x,z in loop] for y,loop in rings]; u,c,r=rows
    x,back,floor,ceiling=slot
    if not floor<=u[0][1]<c[0][1]<ceiling<r[0][1] or x>=min(row[1][0] for row in rows):
        raise ValueError('slot must open through underside, inside the two inner cheek corners')
    # The bow of each half is straight between stations 0 and 1. The upper
    # entrance inclines back to the roof. K is its intersection with the lintel.
    k=np.interp(ceiling,(c[0][1],r[0][1]),(c[0][2],r[0][2]))
    us=(x,*u[0][1:]); cs=(x,*c[0][1:]); ks=(x,ceiling,k); k0=(0,ceiling,k)
    foot=(x,u[0][1],back); foot0=(0,u[0][1],back); sill=(x,ceiling,back); sill0=(0,ceiling,back)
    def face(q,mat=T.PAINT): p.face(q,mat,False)
    face(r); face([foot0,foot,us,*u[1:]][::-1]); face([r[1],r[0],k0,ks,cs,c[1]])
    face([c[1],cs,us,u[1]]); face([us,cs,ks,sill,foot],'recess')
    face([foot0,foot,sill,sill0],'recess'); face([sill0,sill,ks,k0],'recess')
    for i in range(1,len(r)-1):
        j=i+1; face([c[j],c[i],u[i],u[j]])
        if i==2:
            pocket_triangle(p,[r[i],c[i],c[j]],**window); face([r[j],r[i],c[j]])
        elif i==3:
            face([r[j],r[i],c[i]]); face([r[j],c[i],c[j]])
        else: face([r[j],r[i],c[i],c[j]])
    p.mirror_x(); return p


def face_panel(centre, normal, size, rim, relief, mat='recess'):
    """Shallow framed insert mounted on a sloping wall. centre is on the wall."""
    c=np.asarray(centre); axes=_axes(normal); n=axes[2]; w,h=size
    p=T.Part('framed insert')
    p.obox(T.PAINT,c+n*relief/2,(w,h,relief),axes)
    p.obox(mat,c+n*relief,(w-2*rim,h-2*rim,relief),axes)
    return p


def mesh_panel(centre, normal, size, grid, strip, relief):
    """Opaque lattice over a recessed backing, no alpha texture or cutout faces."""
    axes=_axes(normal); u,v,n=axes; c=np.asarray(centre); w,h=size; nx,ny=grid
    p=T.Part('rear mesh'); p.obox('recess',c,(w,h,relief),axes)
    for x in np.linspace(-(w-strip)/2,(w-strip)/2,nx):
        p.obox(T.PAINT,c+x*u+relief*n,(strip,h,relief),axes)
    for y in np.linspace(-(h-strip)/2,(h-strip)/2,ny):
        p.obox(T.PAINT,c+y*v+2*relief*n,(w,strip,relief),axes)
    return p


def port_box(centre, normal, size, grid, spacing, radius, lip, bevel, segments):
    """Box prop with an array of blind, dark circular insets on the outer face."""
    c=np.asarray(centre); axes=_axes(normal); u,v,n=axes; p=T.Part('port array')
    p.obox(T.PAINT,c,size,axes,bevel=bevel,seg=1)
    nx,ny=grid; dx,dy=spacing
    for i in range(nx):
        for j in range(ny):
            base=c+n*(size[2]/2)+u*((i-(nx-1)/2)*dx)+v*((j-(ny-1)/2)*dy)
            p.revolve('steel',[(radius-lip,lip/2),(radius-lip,lip),(radius,lip),(radius,0)],
                      base,axis=n,seg=segments,cap0='recess',mat_of=lambda k:'recess' if k==0 else 'steel')
    return p


def sleeved_tube(stations, length, face_d, bore_d, recess, bands, band_length, lift, sides):
    """Closed cosmetic shell on +Z. Stations are (distance, outer diameter);
    repeated distances give square shoulders. The only end cap at the nose
    is the dark disc behind the annular face, at length minus recess."""
    profile=[*stations,(length,face_d)]
    zs,ds=zip(*profile)
    if (not all(a<=b for a,b in zip(zs,zs[1:])) or stations[-1][0]>=length
            or not 0<bore_d<min(ds) or not 0<recess<length-zs[0]):
        raise ValueError('invalid sleeve or muzzle stations')
    # Insert both ends of each clamp into the interpolated base profile. The
    # radial step and its return are faces too: no coincident cylinders.
    events=[(z,[d/2]) for z,d in profile]; spans=[]
    for centre in bands:
        a,b=centre-band_length/2,centre+band_length/2
        if not zs[0]<a<b<length or any(a<=z<=b for z in zs) or any(a<=v and u<=b for u,v in spans):
            raise ValueError('clamp crosses a profile break or another clamp')
        spans.append((a,b)); ra,rb=np.interp([a,b],zs,ds)/2
        events.extend(((a,[ra,ra+lift]),(b,[rb+lift,rb])))
    zr=[(z,r) for z,rr in sorted(events,key=lambda event:event[0]) for r in rr]
    zr.extend(((length,bore_d/2),(length-recess,bore_d/2)))
    zones=[('steel' if any(a<=z0<=z1<=b for a,b in spans) else T.PAINT)
           for (z0,_),(z1,_) in zip(zr,zr[1:])]; zones[-1]='recess'
    angles=np.arange(sides)*math.tau/sides
    rings=[[(r*math.cos(phi),r*math.sin(phi),z) for phi in angles] for z,r in zr]
    p=T.Part('sleeved tube'); p.loft(rings,T.PAINT,cap0=True,cap1='recess',mats=lambda i,j:zones[j])
    return p
