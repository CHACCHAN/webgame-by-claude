"""Shared tank modelling kit. All geometry and pivot arguments are in game metres:
+x = vehicle left, +y = up, +z = forward; B/G convert to/from Blender (x,-z,y).
In the rest pose the body's origin is on the ground between the tracks. Model
ONE Part per moving assembly, not an object per plate, bolt, or tyre. Parts
below are unbuilt and contain material NAME keys, not bpy material objects.

RUNNING GEAR
  Round 2 additions: road_wheel, idler, sprocket and return_roller accept
  keyword-only seg=None (circular rim/dish tessellation; teeth stay explicit).
  None uses the budgeted silhouette. Higher overrides can exceed the budget.
  paint_tank accepts optional markings (including planar normal/right/width);
  paint_tracks accepts optional metal_tint. See tank_atlas for their keys.
  Combined traverse_min/max pose views are available in render_check.
  RunningGear(...) describes one side. Prefer keyword fields: track_centre
  (positive left x), track_width, track_thickness (pad face to inner face),
  pitch, road=[(z,r),...], wheel_width (axle span), tyre_width (one hoop),
  tyre_depth (radial), dish_depth, hub_bolts. Road y defaults to r+thickness;
  explicit (z,y,r) overrides it. sprocket=(z,y,pitch_radius,teeth,width);
  idler and rollers use (z,y,r[,width]); rollers=[] loads the wheel tops.
  sag is the midpoint drop between upper supports, horns=1|2, horn_height
  and horn_width set the guide lugs, pad_share is the fraction of each pitch
  covered by rubber, skirt_outer is positive x at the exterior skirt face.
  track_path(rg) -> (pts,s,True), corresponding (z,y) pitch-line samples and
  cumulative metres; pts[-1]==pts[0]. track_band(rg,side,mats,tile_links=8)
  -> one closed Part; side='l'/'r' or +1/-1. U spans width; EXPORTED glTF V
  increases towards the rear on the bottom run. Blender UV.v=1-glTF.v.
  Each link has a recessed web, raised pad (pad_share sets its footprint),
  two edge pin bosses and one or two guides, all using track_l or track_r.
  Cost per side: (30 + 10*horns) * max(8, round(path_length/pitch)) tris.
  For an integer-link fit set pitch = path_length / desired_links on the
  caller's RunningGear; the kit never rewrites pitch or the UV tile length.
  road_wheel(radius,width,tyre_width=None,tyre_depth=None,dish_depth=None,
  hub_bolts=8), sprocket(radius,width,teeth), idler(radius,width),
  return_roller(radius,width) -> axle-local rolling Parts, local spin axis X.
  Disc costs (triangulated): road 696 with 8 bolts per hub, idler 776,
  sprocket 348 + 40*teeth including both tooth rings, carrier 240. Small
  hub rings use fewer corners than the tread; bolt count is not an LOD.
  tyre_wheel(radius,width,rim_radius=None,hub_bolts=10) -> tyre and rim.
  running_gear(body_node,rg,mats,tile_links=8) -> dict(objects,trackV,nodes):
  builds BOTH bands and every pivot (roll_l0 / roll_r0 are foremost) with one
  mesh child apiece. trackV=tile_links*pitch. Pass the same tile_links to
  paint_tracks. wheeled_gear(spec) takes a mapping with body_node,mats,axles
  (four (z,y) centres),track_centre,radius,width and optional rim_radius;
  makes wheel_1l -> spin_1l etc., returns the same keys (trackV=0).
  side_skirt(rg,z0,z1,y_top,y_bottom,thickness,panels,rubber_edge) -> left
  skirt; panels is a count, rubber_edge a strip height. mirror_x adds right.

HULL AND FURNITURE (size = width,height,length unless noted)
  prism(profile_zy,x0,x1,mat) extrudes a simple (z,y) loop; loft(sections,mat)
  joins equally sized, consistently ordered (z,polygon_xy) stations.
  slab(corners,thickness,mat) thickens a CCW outer face inward. cbox(centre,
  size,chamfer,mat) makes a flat-bevelled box. Omitted mat is tank_paint.
  hatch(centre,normal,radius=... OR size=(w,h),thickness=...) makes lid and
  handle; centre is on the mounting plane. periscope(centre,size,forward)
  is an opaque window block. smoke_dischargers(n,centre,direction,spacing,
  radius,length) is a bank of exterior props. basket(centre,size,bars,radius)
  makes a rail rack; tow_hook(centre,normal,radius,bar) makes a towing eye.
  lamp_box(centre,size,mat,forward) is a casing with a named lens (headlight
  or taillight). mudguard(corners,thickness,mat) takes pairs of inner/outer
  edge points from back to front. grille(centre,size,louvres) makes a louvred
  inset. antenna_mount(centre,radius,height) makes a stepped socket at base.
  bolt_row(marks,a,b,n,radius,height,normal,geo_radius) appends paint marks
  and returns a Part (hex heads for large bolts only); weld_seam(marks,a,b,
  radius,height) appends a normal-map bead. Supply hull/world marks at rest,
  not moving-node local coordinates. Marks are dictionaries of kind, a, b,
  radius, height (a=b for a bolt). Heights/radii here are metres, not pixels.
  gun_barrel(calibre,length,sleeve_segments,muzzle_ref,evacuator=None) makes
  an axle-local exterior shell on +z: calibre is bore diameter, sleeve_segments
  a count, muzzle_ref a bool, evacuator optionally (z0,z1,outer_radius).
  mantlet(centre,size) is its moving collar; coax_port(centre,radius,normal)
  is a blind rimmed aperture. commander_sight(centre,height,radius) makes a
  glazed sight on its pedestal; rws_mg(centre,scale) is a pintle prop.

ASSEMBLY, PAINT, EXPORT AND CHECKS
  materials() returns jet_kit.Materials; shape zones are tank_paint, rubber,
  steel, recess, glass_dark; lamps and track_l/r survive paint BY NAME. Start
  in a clean scene (Blender's .001 suffixes break the loader's contract).
  combine(name,parts) consumes Parts into one Part, retaining zones and UVs;
  placed(part,offset) translates game coordinates in place. Part.build takes
  WORLD geometry, converting it into its parent's frame: place a gun-local
  barrel at the world trunnions BEFORE build(gun,mats), not after parenting.
  tank_nodes(tid,dims) -> root,body,turret,gun, from turretZ,ringY,trunnion,
  trunnionZ; the last two offsets are turret-local. No geometry may extend beyond
  the muzzle along +z. Keep the roll_* prefix for pivots, not mesh children.
  paint_tank(objects,mats,scheme,size,workdir,density=None,marks=None) bakes
  one armor atlas in rest space. scheme keys base,green,brown,dust are sRGB
  hex strings; scale is in metres, seed an integer, dust_strength a fraction.
  size is atlas pixels (2048 delivery); density(obj,zone) is relative UV size.
  paint_tracks(mats,rg,workdir,tile_links=8) wires three shared 512px PNGs.
  dump(objects,path) saves f15-compatible NPZ P,O,Z,names,zones before paint.
  export(root,path) exports only the model as GLB. report(root) prints TRIS,
  MATERIALS, TRACKV for tracks, and DIMS measured at rest (gun tip on bore
  axis; belly height at the midline), returns (triangle_count,material_names).
  render_check(root,outdir,elev=(-7,10),views=None,quick=False) writes named
  1280x720 PNGs. elev is min/max in degrees, views a selection of tank_scene
  VIEWS, quick selects Workbench instead of CPU Cycles. sheet(outdir,path)
  assembles the available named views into a labelled JPEG without Pillow.
"""
from __future__ import annotations

import math
import sys
from bisect import bisect_right
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'jets'))
import bpy
import numpy as np
import jet_kit as _jet
from jet_kit import B, G, Materials, Part, node
from tank_atlas import paint_tank, paint_tracks
from tank_scene import render_check, sheet


@dataclass
class RunningGear:
    road: tuple = ((1.95,.33), (.95,.33), (-.05,.33), (-1.05,.33), (-2.05,.33))
    sprocket: tuple = (-3., .62, .32, 11, .43)
    idler: tuple = (2.95, .58, .30)
    rollers: tuple = ((1.2,.90,.10), (-1.4,.90,.10))
    track_centre: float = 1.30
    track_width: float = .55
    pitch: float = .165
    pad_share: float = .72
    horns: int = 2
    horn_width: float = .045
    sag: float = .03
    skirt_outer: float = 1.62

    track_thickness: float = .10  # ground face to wheel contact face
    wheel_width: float = .42
    tyre_width: float = .13       # axial width of each road wheel's rubber hoop
    tyre_depth: float = .044      # its radial depth
    dish_depth: float = .034
    hub_bolts: int = 8
    horn_height: float = .075

    def __post_init__(self):
        if not (self.road and self.track_centre > 0 and self.track_width > 0 and self.pitch > 0
                and 0 < self.pad_share <= 1 and self.horns in (1, 2)
                and 0 < self.horn_width < self.track_width / (2*self.horns)
                and min(self.track_thickness,self.wheel_width,self.tyre_width,self.tyre_depth,self.horn_height)>0
                and self.hub_bolts >= 0 and self.dish_depth >= 0 and self.sag >= 0):
            raise ValueError('invalid running gear dimensions')


def _road_centres(rg):
    return [(w[0], w[1]+rg.track_thickness, w[1]) if len(w)==2 else tuple(w) for w in rg.road]


def _outside(a, b):
    # Left normal of the directed external tangent, in the (z,y) plane.
    dz, dy = b[0]-a[0], b[1]-a[1]
    d = math.hypot(dz, dy)
    if d <= abs(a[2]-b[2]):
        raise ValueError('a wheel encloses another wheel on the pitch line')
    u, v = dz/d, dy/d
    k = (a[2]-b[2])/d
    h = math.sqrt(1-k*k)
    return k*u-h*v, k*v+h*u


def _chain(discs):
    # Skip wheels below the tension line (above it on the ground run).
    chain = []
    for c in discs:
        while len(chain) >= 2:
            u,v = _outside(*chain[-2:])
            x,y = _outside(chain[-1], c)
            if u*y-v*x <= 0:
                break
            chain.pop()
        chain.append(c)
    return chain


def track_path(rg):
    # Inflate rolling surfaces to the pitch line. Sprocket radius already
    # denotes its pitch circle; the tips enter the belt at the shoulders.
    h = .5*rg.track_thickness
    def inflate(c):
        z,y,r = c[:3]; return z,y,r+h
    road = list(map(inflate,_road_centres(rg)))
    rear, front = sorted((tuple(rg.sprocket[:3]), inflate(rg.idler)))
    rollers = list(map(inflate,rg.rollers))
    lower = _chain([front, *sorted(road, reverse=True), rear])
    supports = [rear,*sorted(rollers or road),front]
    upper = _chain(supports)
    # With no carrier rollers the upper chain is slack on the road-wheel
    # crowns, even when the end wheels sit above a taut external tangent.
    # Enforce actual supports, not a near-360-degree wrap round a low wheel.
    crown_spans = not rollers and len(upper)!=len(supports)
    if crown_spans: upper=supports
    # One point per supporting circle; on each visit emit its clockwise arc
    # between the incoming/outgoing tangent normals, then its outgoing span.
    route = lower + upper[1:-1]
    normals = [_outside(c, route[(i+1)%len(route)]) for i,c in enumerate(route)]
    if crown_spans:
        normals[len(lower)-1:]=[(0.,1.)]*(len(route)-len(lower)+1)
    pts = []
    def add(z,y):
        if not pts or math.dist(pts[-1], (z,y)) > 1e-8:
            pts.append((z,y))

    for i,(z,y,r) in enumerate(route):
        nz,ny = normals[i]
        a = math.atan2(normals[i-1][1], normals[i-1][0])
        b = math.atan2(ny,nz)
        sweep = (a-b) % math.tau
        if math.tau-sweep < 1e-9:
            sweep = 0.
        n = max(1, math.ceil(sweep/.15))
        for j in range(n+1):
            angle = a-sweep*j/n
            add(z+r*math.cos(angle), y+r*math.sin(angle))
        if (rg.sag or crown_spans) and i >= len(lower)-1:
            zz,yy,rr = route[(i+1)%len(route)]
            z0,y0 = pts[-1]
            dz,dy = zz+rr*nz-z0, yy+rr*ny-y0
            steps = max(4, math.ceil(math.hypot(dz,dy)/rg.pitch))
            for j in range(1,steps):
                t = j/steps
                p = z0+t*dz
                q = y0+(t*t*(3-2*t) if crown_spans else t)*dy-rg.sag*math.sin(math.pi*t)**2
                # A slack upper span can touch a wheel skipped by _chain.
                for wz,wy,wr in [rear,front,*road,*rollers]:
                    if abs(p-wz) < wr:
                        q = max(q, wy+math.sqrt(wr*wr-(p-wz)**2))
                add(p,q)
    if math.dist(pts[-1],pts[0]) < 1e-8:
        pts[-1]=pts[0]
    else:
        pts.append(pts[0])
    s = [0.]
    for a,b in zip(pts,pts[1:]):
        s.append(s[-1]+math.dist(a,b))
    return np.asarray(pts),np.asarray(s),True


def _side(side):
    if side in ('l','left',1):
        return 'l',1
    if side in ('r','right',-1):
        return 'r',-1
    raise ValueError('side must be l/r or +1/-1')


def track_band(rg, side, mats, tile_links=8):
    letter,sign = _side(side)
    tile = tile_links*rg.pitch
    if int(tile_links)!=tile_links or tile <= 0:
        raise ValueError('tile_links must be positive')
    pts,s,_ = track_path(rg)
    p = Part('band_'+letter)
    mat = 'track_'+letter
    xc,w,h = sign*rg.track_centre, rg.track_width, rg.track_thickness/2
    length=s[-1]; links=max(8,round(length/rg.pitch)); link=length/links
    def sample(dist):
        d=dist % length
        i=min(len(pts)-2,bisect_right(s,d)-1)
        t=(d-s[i])/(s[i+1]-s[i]); return np.asarray(pts[i])*(1-t)+np.asarray(pts[i+1])*t
    def frame(dist):
        z,y=sample(dist); delta=sample(dist+.002)-sample(dist-.002)
        tz,ty=delta/np.linalg.norm(delta)
        def point(x,rad):
            return (xc+x,y+rad*tz,z-rad*ty)
        return point
    # The web follows the pitch polygon. Build details on its ruled faces,
    # not on a second sampled curve (which would float off the end wheels).
    web = .58*h
    def face(corners):
        f=p.face([q for q,u,d in corners],mat,False)
        for loop,(_,u,d) in zip(f.loops,corners): loop[p.uv].uv=(u,1.-d/tile)

    for i in range(links):
        d0=i*link
        a,b=frame(d0),frame(((i+1)%links)*link)
        def corner(x,rad,t,u):
            q=np.asarray(a(x,rad))*(1-t)+np.asarray(b(x,rad))*t
            return q,u,d0+t*link

        section=[(-.47,-h),(.47,-h),(.47,web),(-.47,web)]
        for j,(x,r) in enumerate(section):
            xx,rr=section[(j+1)%4]
            u,v=((.865,.895),(.97,.99),(.97,.03),(.01,.03))[j]
            face([corner(x*w,r,0,u),corner(xx*w,rr,0,v),
                  corner(xx*w,rr,1,v),corner(x*w,r,1,u)])

        def lug(x,base,tip,outer):
            # Open foot on the web, four sloping walls and a flat crown.
            # Both dimensions taper, so plan-projected UVs have area even
            # on the two end walls. Guides sample steel, pads span the tile.
            rings=[]
            for rad,half,span in (base,tip):
                ring=[corner(x+sx*half,rad,.5+st*span,
                             .5+sx*half/w if outer else .88+sx*.017*half/base[1])
                      for sx,st in ((-1,-1),(1,-1),(1,1),(-1,1))]
                rings.append(ring[::-1] if outer else ring)
            foot,cap=rings
            for j in range(4):
                k=(j+1)%4
                face([foot[j],foot[k],cap[k],cap[j]])
            face(cap)

        # A separate raised rubber shoe with a lower steel valley at the
        # joint. Only the pad reaches +h (ground on the lower straight).
        lug(0.,(web,.35*w,.5*rg.pad_share),(h,.33*w,.46*rg.pad_share),True)
        guide=min(.442*w,.47*w-.5*rg.horn_width)
        for x in ((0.,) if rg.horns==1 else (-guide,guide)):
            lug(x,(-h,.5*rg.horn_width,.21),(-h-rg.horn_height,.17*rg.horn_width,.085),False)

        # A chamfered pin boss at each edge. Collapse the crown to a short
        # ridge: two quads and two triangles, no buried back plate. Project
        # UVs onto the radial/longitudinal plane in the steel edge strip.
        for edge in (-1,1):
            def pin(width,rad,t):
                return corner(edge*width*w,rad*h,t,.5+edge*(.473+.015*rad))
            q0,q1,q2,q3=(pin(.47,rad,t) for rad,t in
                         ((-.78,.06),(.42,.06),(.42,.39),(-.78,.39)))
            n,m=pin(.5,-.18,.12),pin(.5,-.18,.33)
            for poly in ([q0,q1,n],[q1,q2,m,n],[q2,q3,m],[q3,q0,n,m]):
                face(poly if edge>0 else poly[::-1])
    return p


def _dish(p,r,w,x,outer,bolts,seg,tyre_width=None,tyre_depth=None,dish_depth=None):
    # Cross-section from exposed hub, through recessed dish and rim lip, over
    # the tread to the opposite hub. The descending axial traverse gives
    # jet_kit.Part.revolve its outward winding.
    tread=min(.90*w,tyre_width if tyre_width is not None else .72*w)
    inner=r-(tyre_depth if tyre_depth is not None else .12*r)
    inset=min(.32*w, dish_depth if dish_depth is not None else .18*w)
    face=[(.18*inner,.50*w),(.26*inner,.48*w),(.34*inner,.45*w-inset),(.72*inner,.45*w-.8*inset),
          (inner*.96,.48*w),(inner,.49*w),(inner,.5*tread+.007*w),(.99*r,.5*tread),(r,.46*tread)]
    profile=[(rr,x+a) for rr,a in face]+[(rr,x-a) for rr,a in reversed(face)]
    zones=['steel','tank_paint','tank_paint','tank_paint','steel','steel',outer,outer]
    bands=zones+[outer]+zones[::-1]
    p.revolve('tank_paint',profile,(0,0,0),seg=seg,cap0=True,cap1=True,mat_of=lambda k:bands[k])
    for side in (-1,1):
        for i in range(bolts):
            angle=math.tau*i/bolts
            y,z=.37*inner*math.cos(angle),.37*inner*math.sin(angle)
            p.revolve('steel',[(.049*r,.038*r),(.055*r,.028*r),(.055*r,0)],
                      (x+side*(.45*w-inset),y,z),axis=(side,0,0),seg=6,cap0=True,smooth=False)


def _axial_ring(x,r,n):
    return [(x,r*math.cos(i*math.tau/n),r*math.sin(i*math.tau/n)) for i in range(n)]


def _ring_strip(p,a,b,mat,smooth):
    # Both rows run CCW about +X. Advance whichever row reaches the next
    # azimuth first; coincident steps form a quad. No T-junctions or poles.
    na,nb=len(a),len(b)
    i=j=0
    while i<na or j<nb:
        da,db=(i+1)*nb,(j+1)*na
        poly=[a[i%na]]
        if da<=db:
            i+=1; poly.append(a[i%na])
        if db<=da:
            poly.append(b[(j+1)%nb])
        poly.append(b[j%nb])
        if db<=da: j+=1
        p.face(poly,mat,smooth)


def _rolling_disc(p,r,w,x,outer,bolts,seg,tyre_width=None,tyre_depth=None,dish_depth=None,carrier=False):
    # Spend circumference on the silhouette, not the small concentric hub
    # rings. Keep both faces of each disc, including the inboard bolt heads.
    tread=min(.90*w,tyre_width if tyre_width is not None else .72*w)
    inner=r-(tyre_depth if tyre_depth is not None else .12*r)
    inset=min(.32*w,dish_depth if dish_depth is not None else .18*w)
    seat=.45*w-inset
    if carrier:
        profile=[(.56*inner,seat,6),(inner,.49*w,6),(r,.5*tread,seg)]
        zones=['tank_paint',outer]
    else:
        profile=[(.22*inner,.50*w,8),(.32*inner,seat,8),(.88*inner,seat,8),
                 (inner,.49*w,seg),(r,.5*tread,seg)]
        zones=['steel','tank_paint','steel',outer]
    rows=[_axial_ring(x-a,rr,n) for rr,a,n in profile]
    rows.extend(_axial_ring(x+a,rr,n) for rr,a,n in reversed(profile))
    p.face(rows[0][::-1],'steel',False)
    for a,b,mat in zip(rows,rows[1:],zones+[outer]+zones[::-1]):
        _ring_strip(p,a,b,mat,True)
    p.face(rows[-1],'steel',False)

    for side in (-1,1):
        for i in range(bolts):
            angle=math.tau*i/bolts
            y,z=.39*inner*math.cos(angle),.39*inner*math.sin(angle)
            base=[(xx,y+dy,z+dz) for xx,dy,dz in _axial_ring(x+side*seat,.055*r,6)]
            if side<0: base.reverse()
            tip=(x+side*(seat+.038*r),y,z)
            for a,b in zip(base,base[1:]+base[:1]): p.face([a,b,tip],'steel',False)


def road_wheel(radius,width,tyre_width=None,tyre_depth=None,dish_depth=None,hub_bolts=8,*,seg=None):
    p=Part('road_disc')
    seg=max(8,min(20,(700-184-24*hub_bolts)//16)) if seg is None else max(8,int(seg))
    for sign in (-1,1):
        _rolling_disc(p,radius,.41*width,sign*.295*width,'rubber',hub_bolts,seg,tyre_width,tyre_depth,dish_depth)
    return p


def sprocket(radius,width,teeth,*,seg=None):
    if not isinstance(teeth,int) or teeth < 3:
        raise ValueError('teeth must be an integer >= 3')
    p = Part('drive_disc')
    _rolling_disc(p,.84*radius,.86*width,0.,'steel',8,20 if seg is None else max(8,int(seg)))
    for sign in (-1,1):
        # Keep the four-corner tooth silhouette, but only one bore vertex
        # per tooth. Back and front annuli have opposite winding.
        lo,hi=sorted((sign*.42*width,sign*.50*width))
        rows=[]
        for x in (lo,hi):
            ring=[]
            for i in range(teeth):
                for phase,scale in ((0,.88),(.28,1.),(.56,1.),(.84,.88)):
                    a=math.tau*(i+phase)/teeth
                    ring.append((x,radius*scale*math.cos(a),radius*scale*math.sin(a)))
            rows.append(ring)
        bore0,bore1=(_axial_ring(x,.76*radius,teeth) for x in (lo,hi))
        for a,b in ((bore0,rows[0]),(rows[0],rows[1]),(rows[1],bore1),(bore1,bore0)):
            _ring_strip(p,a,b,'steel',False)
    return p


def idler(radius,width,*,seg=None):
    p = Part('idler_disc')
    for sign in (-1,1):
        _rolling_disc(p,radius,.41*width,sign*.295*width,'steel',6,28 if seg is None else max(8,int(seg)))
    return p


def return_roller(radius,width,*,seg=None):
    p = Part('carrier_disc')
    for sign in (-1,1):
        _rolling_disc(p,radius,.4*width,sign*.30*width,'rubber',3,10 if seg is None else max(8,int(seg)),carrier=True)
    return p


def tyre_wheel(radius,width,rim_radius=None,hub_bolts=10):
    p = Part('tyre_disc')
    rim=radius*.59 if rim_radius is None else rim_radius
    if not 0 < rim < radius: raise ValueError('require 0 < rim_radius < radius')
    _dish(p,radius,width,0.,'rubber',hub_bolts,40,tyre_depth=radius-rim)
    return p


def _local_mesh(part,name,parent,mats,origin=(0,0,0)):
    # Part.build(parent,...) converts world-space verts to parent space.
    # These verts are already local: parent the finished mesh instead.
    obj = part.build(None,mats,name=name)
    obj.parent = parent
    obj.location = B(*origin)
    return obj


def _local_node(name,parent,origin):
    obj = node(name)
    obj.parent = parent
    obj.location = B(*origin)
    return obj


def running_gear(body_node,rg,mats,tile_links=8):
    wheels = [(z,y,r,road_wheel,(r,rg.wheel_width,rg.tyre_width,rg.tyre_depth,rg.dish_depth,rg.hub_bolts)) for z,y,r in _road_centres(rg)]
    z,y,r,teeth,width = rg.sprocket
    wheels.append((z,y,r,sprocket,(r,width,teeth)))
    for make,items in ((idler,[rg.idler]),(return_roller,rg.rollers)):
        for z,y,r,*w in items:
            wheels.append((z,y,r,make,(r,w[0] if w else .76*rg.track_width)))
    wheels.sort(key=lambda w:w[0],reverse=True)
    objects,nodes = [],[]
    for letter,sign in (('l',1),('r',-1)):
        for i,(z,y,r,make,args) in enumerate(wheels):
            suffix = letter+str(i)
            pivot = _local_node('roll_'+suffix,body_node,(sign*rg.track_centre,y,z))
            pivot['radius'] = r
            nodes.append(pivot)
            objects.append(_local_mesh(make(*args),'disc_'+suffix,pivot,mats))
        objects.append(_local_mesh(track_band(rg,letter,mats,tile_links),'band_'+letter,body_node,mats))
    track_v = float(tile_links*rg.pitch)
    body_node['trackV'] = track_v
    return dict(objects=objects,trackV=track_v,nodes=nodes)


def wheeled_gear(spec):
    objects,nodes = [],[]
    axles = sorted(spec['axles'], reverse=True)
    if len(axles)!=4 or len({z for z,y in axles})!=4:
        raise ValueError('the 8x8 rig needs four distinct axle stations')
    for i,(z,y) in enumerate(axles,1):
        for letter,sign in (('l',1),('r',-1)):
            suffix = str(i)+letter
            pivot = _local_node('wheel_'+suffix,spec['body_node'],(sign*spec['track_centre'],y,z))
            spin = _local_mesh(tyre_wheel(spec['radius'],spec['width'],spec.get('rim_radius')),
                               'spin_'+suffix,pivot,spec['mats'])
            nodes.extend((pivot,spin))
            objects.append(spin)
    return dict(objects=objects,trackV=0.,nodes=nodes)


def side_skirt(rg,z0,z1,y_top,y_bottom,thickness,panels,rubber_edge):
    lo,hi = sorted((z0,z1))
    if panels < 1 or thickness <= 0 or hi<=lo or not 0<=rubber_edge<y_top-y_bottom:
        raise ValueError('invalid skirt dimensions')
    p = Part('skirt_l')
    x = rg.skirt_outer
    dz = (hi-lo)/panels
    gap = min(.014,dz*.045)
    mid = y_bottom+rubber_edge
    for i in range(panels):
        a,b = lo+i*dz+gap/2, lo+(i+1)*dz-gap/2
        p.box('tank_paint',x-thickness,x,mid,y_top,a,b,bevel=.008,seg=1)
        if rubber_edge:
            p.box('rubber',x-.8*thickness,x-.14*thickness,y_bottom,mid,a,b,bevel=.004,seg=1)
    return p

PAINT = 'tank_paint'


def materials():
    """Build the named temporary paint zones, permanent lamp and band slots, in a clean scene."""
    m = Materials()
    for name, colour, metal, rough in [
        (PAINT, '465138', .15, .78), ('steel', '575952', .72, .55), ('rubber', '292a28', .0, .91),
        ('recess', '22251e', .12, .84), ('glass_dark', '253832', .22, .27),
        ('track_l', '49463d', .48, .79), ('track_r', '49463d', .48, .79),
    ]:
        m.add(name, colour, metallic=metal, roughness=rough)
    for name, col in [('headlight', 'ede3c5'), ('taillight', 'aa2720')]:
        m.add(name, col, roughness=.32, emissive=col, strength=.25)
    return m


def combine(name, parts):
    """Consume Parts into one Part in their common game frame; retain zones, smoothing and UV corners."""
    out = Part(name)
    for p in parts:
        verts = {v: out.bm.verts.new(v.co) for v in p.bm.verts}
        for f in p.bm.faces:
            g = out.bm.faces.new([verts[v] for v in f.verts])
            g.material_index = out.slot(p.slots[f.material_index])
            g.smooth = f.smooth
            for dest, src in zip(g.loops, f.loops):
                dest[out.uv].uv = src[p.uv].uv
        p.bm.free()
    return out


def placed(part, offset):
    """Translate a Part in game metres in-place and return it (before build)."""
    d = B(*offset)
    for v in part.bm.verts:
        v.co += d
    return part


def _unit3(v):
    a = np.asarray(v, dtype=float)
    length = np.linalg.norm(a)
    if length < 1e-9:
        raise ValueError('direction cannot be zero')
    return a / length


def _basis(n):
    w = _unit3(n)
    u = _unit3(np.cross((0, 1, 0) if abs(w[1]) < .9 else (0, 0, 1), w))
    return u, np.cross(w, u), w


def _turned(p, base, axis, profile, mat=PAINT, seg=24, caps=True, mat_of=None):
    """Outward-wound turned shell. Profile in (axial distance, radius), back to front."""
    u, v, w = _basis(axis)
    base = np.asarray(base, dtype=float)
    az = np.arange(seg) * (2 * math.pi / seg)
    rad = np.outer(np.cos(az), u) + np.outer(np.sin(az), v)
    rows = [base + a*w + r*rad for a, r in profile]
    p.loft(rows, mat, cap0=caps, cap1=caps, mats=(lambda i,j: mat_of(j)) if mat_of else None)


def _signed_area(poly):
    return sum(a[0]*b[1]-a[1]*b[0] for a,b in zip(poly, poly[1:]+poly[:1])) * .5


def prism(profile_zy, x0, x1, mat=PAINT):
    """Extrude a simple side polygon [(z,y),...] between two x stations; either winding."""
    poly = list(profile_zy)
    if len(poly) < 3 or x0 >= x1 or abs(_signed_area(poly)) < 1e-9:
        raise ValueError('prism needs a non-empty side profile and x0 < x1')
    if _signed_area(poly) > 0:
        poly.reverse()  # z cross y = -x
    p = Part('prism')
    p.loft([[(x,y,z) for z,y in poly] for x in (x0,x1)], mat, cap0=True, cap1=True, cap_centre=False, smooth=False)
    return p


def loft(sections, mat=PAINT):
    """Skin [(z, polygon_xy), ...] at increasing z. Corresponding corners in consistent cyclic order."""
    sec = [(float(z), list(poly)) for z,poly in sections]
    if len(sec) < 2 or len(sec[0][1]) < 3:
        raise ValueError('loft needs at least two rings of three or more corners')
    n = len(sec[0][1]); ccw = _signed_area(sec[0][1]) > 0
    if any(z >= zz for (z,_),(zz,_) in zip(sec,sec[1:])) or any(len(q)!=n or (_signed_area(q)>0)!=ccw for _,q in sec):
        raise ValueError('loft: check z order, winding and corner counts')
    p = Part('loft')
    p.loft([[(x,y,z) for x,y in (poly if ccw else reversed(poly))] for z,poly in sec], mat,
           cap0=True, cap1=True, cap_centre=False, smooth=False)
    return p


def slab(corners, thickness, mat=PAINT):
    """Plate whose outer face is the supplied planar loop, CCW viewed from outside. Extrude inward."""
    q = np.asarray(corners, dtype=float)
    if len(q) < 3 or thickness <= 0:
        raise ValueError('slab needs a face loop and positive thickness')
    n = _unit3(np.sum(np.cross(q-q[0],np.roll(q,-1,axis=0)-q[0]),axis=0))
    p = Part('slab')
    p.loft([q-n*thickness, q], mat, cap0=True, cap1=True, cap_centre=False, smooth=False)
    return p


def cbox(centre, size, chamfer=0., mat=PAINT):
    """Box with one flat bevel on every edge, centred at xyz, size (width,height,length)."""
    p = Part('cbox'); a = np.asarray(centre)-np.asarray(size)*.5; b = a+size
    p.box(mat,a[0],b[0],a[1],b[1],a[2],b[2],bevel=chamfer,seg=1,smooth=False)
    return p


def _rail(part,path,radius,mat,seg=8):
    # N,Bn,T is a right-handed parallel-transport frame. Use that order
    # round the section (CCW looking back down the path), including caps.
    points,_,normal,binormal=_jet.frame_along(path)
    angles=np.arange(seg)*math.tau/seg
    rings=[c+radius*(np.outer(np.cos(angles),n)+np.outer(np.sin(angles),b))
           for c,n,b in zip(points,normal,binormal)]
    part.loft(rings,mat,cap0=True,cap1=True)


def hatch(centre, normal=(0,1,0), radius=None, size=None, thickness=.046, mat=PAINT):
    """Round (radius) or rectangular (size pair) hatch lid and handle on a plane, centre at its base."""
    c = np.asarray(centre); u,v,w = _basis(normal); p = Part('hatch')
    if (radius is None) == (size is None):
        raise ValueError('supply radius or size')
    if radius is not None:
        _turned(p,c,w,[(0,radius),(.75*thickness,radius),(thickness,.97*radius)],mat)
        grip = radius*.56
    else:
        p.obox(mat,c+w*thickness*.5,(size[0],size[1],thickness),axes=(u,v,w),bevel=.008)
        grip = min(size)*.32
    a,b = c-u*grip*.5+w*thickness, c+u*grip*.5+w*thickness
    _rail(p,[a,a+.035*w,b+.035*w,b],.009,'steel',seg=8)
    return p


def periscope(centre, size=(.17,.09,.12), forward=(0,0,1)):
    """Opaque vision block, size xyz, facing forward (not parallel to the up axis)."""
    u,v,w = _basis(forward); c=np.asarray(centre); p=Part('periscope')
    p.obox(PAINT,c,size,(u,v,w),bevel=.009)
    p.obox('glass_dark',c+w*size[2]*.5,(size[0]*.8,size[1]*.56,.003),(u,v,w))
    return p


def smoke_dischargers(n, centre, direction=(.7,.65,.3), spacing=.11, radius=.038, length=.23):
    """Bank of n capped exterior smoke-tube props; centre is middle of the row at its base."""
    u,_,w=_basis(direction); p=Part('discharger bank')
    for i in range(n):
        c=np.asarray(centre)+u*((i-(n-1)/2)*spacing)
        _turned(p,c,w,[(0,radius),(.88*length,radius),(.89*length,1.09*radius),(length,1.09*radius)],seg=12)
        _turned(p,c+w*length,w,[(0,.87*radius),(.002,.87*radius)],mat='recess',seg=12)
    return p


def basket(centre,size=(1.4,.30,.45),bars=5,radius=.012):
    """Open rectangular rail basket, centre xyz at its middle; bars = pickets across each long face."""
    c=np.asarray(centre); h=np.asarray(size)*.5; p=Part('basket')
    for iy in (-1,1):
        ring=[c+h*(x,iy,z) for x,z in ((-1,-1),(1,-1),(1,1),(-1,1))]
        for a,b in zip(ring,ring[1:]+ring[:1]):
            _rail(p,[a,b],radius,PAINT,seg=8)
    for t in np.linspace(-1,1,max(2,bars)):
        for z in (-1,1):
            _rail(p,[c+h*(t,-1,z),c+h*(t,1,z)],radius,PAINT,seg=8)
        _rail(p,[c+h*(t,-1,-1),c+h*(t,-1,1)],radius,PAINT,seg=8)
    return p


def tow_hook(centre,normal=(0,0,1),radius=.068,bar=.018):
    """Rounded towing eye; centre is midpoint between its mounting feet; bar = stock radius."""
    u,_,w=_basis(normal); a=np.linspace(0,math.pi,13)
    p=Part('tow eye'); _rail(p,[np.asarray(centre)+radius*(u*np.cos(t)+w*np.sin(t)) for t in a],bar,PAINT,seg=8)
    return p


def lamp_box(centre,size,mat,forward=(0,0,1)):
    """Painted casing with a distinct front lens slot named headlight/taillight; size xyz."""
    u,v,w=_basis(forward); c=np.asarray(centre); p=Part('lamp')
    p.obox(PAINT,c,size,(u,v,w),bevel=.014,seg=1)
    p.obox(mat,c+w*(size[2]*.5),(.82*size[0],.73*size[1],.009),(u,v,w),bevel=.002,seg=1)
    return p


def mudguard(corners,thickness=.018,mat=PAINT):
    """Folded fender from ordered pairs (inner edge point, outer edge point), along its length."""
    ribs=list(corners)
    if len(ribs)<2:
        raise ValueError('mudguard needs at least two ribs')
    parts=[]
    for (a,b),(d,c) in zip(ribs,ribs[1:]):
        q=np.asarray([a,b,c,d]); n=np.cross(q[1]-q[0],q[2]-q[0]); parts.append(slab(q if n[1]>=0 else q[::-1],thickness,mat))
    return combine('mudguard',parts)


def grille(centre,size=(.7,.045,.55),louvres=9):
    """Horizontal grille with a dark inset and inclined slats across its width (size xyz)."""
    c=np.asarray(centre); w,h,d=size
    p=cbox(c,(w,.009,d),.003,'recess'); ang=math.radians(28)
    axes=((1,0,0),(0,math.cos(ang),math.sin(ang)),(0,-math.sin(ang),math.cos(ang)))
    if louvres<1: raise ValueError('grille needs at least one louvre')
    for i in range(louvres):
        p.obox(PAINT,c+(0,h*.5,d*((i+.5)/louvres-.5)),(.94*w,.009,.78*d/louvres),axes)
    return p


def antenna_mount(centre,radius=.055,height=.11):
    """Stepped antenna foot, vertical, with origin at its bottom."""
    p=Part('antenna mount'); _turned(p,centre,(0,1,0),[(0,radius),(.25*height,radius),(.28*height,.54*radius),(height,.36*radius)],seg=16)
    return p


def bolt_row(marks,a,b,n,radius=.014,height=.004,normal=(0,1,0),geo_radius=.026):
    """Append world-space bolt marks; returns a Part containing only bolts >= geo_radius (hex heads)."""
    p=Part('bolt heads')
    for c in np.linspace(a,b,n):
        marks.append(dict(kind='bolt',a=tuple(c),b=tuple(c),radius=radius,height=height))
        if radius>=geo_radius:
            _turned(p,c,normal,[(0,radius),(.8*height,radius),(height,.86*radius)],'steel',6)
    return p


def weld_seam(marks,a,b,radius=.012,height=.003):
    """Append one raised bead segment in hull-frame xyz for the height painter (no geometry)."""
    marks.append(dict(kind='seam',a=tuple(a),b=tuple(b),radius=radius,height=height))


def gun_barrel(calibre,length,sleeve_segments=4,muzzle_ref=True,evacuator=None):
    """Axle-local cosmetic barrel on +z. calibre = bore diameter in metres, length to muzzle face;
    sleeve_segments = count, muzzle_ref = include reference box, evacuator = optional (z0,z1,outer_radius)."""
    r=calibre*.5
    if not (0<calibre<length and isinstance(sleeve_segments,int) and sleeve_segments>=0):
        raise ValueError('check calibre, barrel length and sleeve count')
    p=Part('barrel'); zaxis=(0,0,1)
    # Continuous shell with a recessed dark bore; no decal or cap forward of z=length.
    prof=[(0,2.15*r),(.16*length,2*r),(.79*length,1.40*r),(.966*length,1.29*r),
          (.969*length,1.43*r),(length,1.43*r),(length,r),(length-min(.12,length*.12),r)]
    _turned(p,(0,0,0),zaxis,prof,seg=32,caps=False,mat_of=lambda j: 'recess' if j==6 else ('steel' if j>=3 else PAINT))
    bore=length-min(.12,length*.12)
    _turned(p,(0,0,0),zaxis,[(bore-.001,r),(bore,r)],'recess',32)
    for k in range(sleeve_segments):
        za=(.15+.63*k/sleeve_segments)*length; zb=(.15+.63*(k+1)/sleeve_segments)*length
        rad=r*(2.28-.45*k/sleeve_segments); gap=min(.009,(zb-za)*.07)
        _turned(p,(0,0,0),zaxis,[(za,rad*.95),(za+gap,rad),(zb-3*gap,rad),(zb-2.8*gap,1.07*rad),
                                 (zb-gap,1.07*rad),(zb-.8*gap,rad*.94)],seg=24,mat_of=lambda j: 'steel' if j==3 else PAINT)
    if evacuator is not None:
        a,b,rr=evacuator
        if not 0<=a<b<=length or rr<=r: raise ValueError('invalid evacuator envelope')
        _turned(p,(0,0,0),zaxis,[(a,.77*rr),(a+.12*(b-a),rr),(b-.12*(b-a),rr),(b,.77*rr)],seg=28)
    if muzzle_ref:
        p.box(PAINT,-.85*r,.85*r,1.25*r,2.83*r,.907*length,.956*length,bevel=.005,seg=1,smooth=False)
        p.box('glass_dark',-.52*r,.52*r,1.82*r,2.46*r,.955*length,.957*length)
    return p


def mantlet(centre=(0,0,0),size=(.72,.40,.40)):
    """Chamfered external barrel collar, centre and xyz extents in the trunnion frame."""
    return cbox(centre,size,min(size)*.17)


def coax_port(centre,radius=.036,normal=(0,0,1)):
    """Opaque inset and raised rim on a plate; not a cut through the mesh."""
    p=Part('coax port'); _turned(p,centre,normal,[(0,radius),(.014,radius),(.014,.72*radius),(.005,.72*radius)],seg=16,
                                 caps=False,mat_of=lambda j: 'recess' if j==2 else 'steel')
    _turned(p,centre,normal,[(.003,.72*radius),(.005,.72*radius)],mat='recess',seg=16)
    return p


def commander_sight(centre,height=.34,radius=.14):
    """Panoramic sight pedestal and glazed head; centre at turret roof, points forward."""
    c=np.asarray(centre); p=Part('sight')
    _turned(p,c,(0,1,0),[(0,radius),(.12*height,radius),(.14*height,.68*radius),(.6*height,.68*radius)],seg=20)
    return combine('commander sight',[p,periscope(c+(0,.77*height,0),(radius*1.9,.46*height,radius*1.6))])


def rws_mg(centre,scale=1.):
    """Stylised exterior silhouette of a pedestal MG with receiver, box and cradle; centre at base."""
    p=Part('pintle'); _turned(p,(0,0,0),(0,1,0),[(0,.14),(.05,.14),(.07,.09),(.24,.09)],seg=16)
    for x in (-.125,.125): p.box(PAINT,x-.018,x+.018,.21,.39,-.12,.10,bevel=.009,seg=1)
    p.box('steel',-.082,.082,.30,.44,-.31,.18,bevel=.012,seg=1)
    p.box(PAINT,.14,.33,.23,.43,-.22,.04,bevel=.013,seg=1)
    _turned(p,(0,.38,.18),(0,0,1),[(0,.047),(.22,.042),(.23,.025),(.72,.021)],mat='steel',seg=12)
    p.transform(np.diag([scale,scale,scale,1.])); return placed(p,centre)


def tank_nodes(tid,dims):
    """Rest transforms from TankInfo.dims. jet_kit.node takes *world* origins, including for children."""
    z,y=dims['turretZ'],dims['ringY']
    root=node(tid); body=node('body',root); turret=node('turret',body,(0,y,z))
    gun=node('gun',turret,(0,y+dims['trunnion'],z+dims['trunnionZ']))
    return root,body,turret,gun


def export(root,path):
    """Export this hierarchy only to GLB (no check cameras, lamps or floor)."""
    path=Path(path).resolve(); path.parent.mkdir(parents=True,exist_ok=True); _jet.export_glb(str(path),root)


def dump(objects,path):
    """Same NPZ layout as f15.dump; call before painting for the construction zone names."""
    from f15 import dump as jet_dump
    Path(path).resolve().parent.mkdir(parents=True,exist_ok=True)
    bpy.context.view_layer.update(); jet_dump(objects,str(path))


def report(root):
    """Jet triangle/material census plus measured rest dimensions and track scale. Hull z bounds include fixed fittings and flaps, not the bands. Clearance is hull centreline underside."""
    bpy.context.view_layer.update()
    total,used=_jet.report(root)
    body=next(o for o in root.children if o.name=='body'); turret=next(o for o in body.children if o.name=='turret')
    gun=next(o for o in turret.children if o.name=='gun')
    inv=body.matrix_world.inverted(); invgun=gun.matrix_world.inverted()
    clouds=[]; barrel=[]; belly=[]; hull_bounds=[]
    for o in body.children_recursive:
        if o.type!='MESH': continue
        matrix=inv @ o.matrix_world
        pts=np.array([G(matrix @ v.co) for v in o.data.vertices]); clouds.append(pts)
        if o in list(gun.children_recursive):
            m=invgun @ o.matrix_world; barrel.extend(G(m @ v.co)[2] for v in o.data.vertices)
        if o.parent==body and not any(m.name in ('track_l','track_r') for m in o.data.materials):
            hull_bounds.append((pts[:,2].min(),pts[:,2].max()))
            # Intersect triangle edges with x=0: skirts, wheel pods and lamps aren't belly clearance.
            o.data.calc_loop_triangles()
            for t in o.data.loop_triangles:
                q=pts[list(t.vertices)]
                for a,b in zip(q,np.roll(q,-1,axis=0)):
                    if a[0]==0: belly.append(a[1])
                    elif a[0]*b[0]<0: belly.append(a[1]+(b[1]-a[1])*a[0]/(a[0]-b[0]))
    allpts=np.concatenate(clouds); lo,hi=allpts.min(0),allpts.max(0); width,height,length=hi-lo
    muzzle=G(inv @ gun.matrix_world @ B(0,0,max(barrel)))
    hull_rear=min((lo_z for lo_z,_ in hull_bounds),default=float('nan'))
    hull_front=max((hi_z for _,hi_z in hull_bounds),default=float('nan'))
    if 'trackV' in body: print(f'TRACKV {body["trackV"]:.6f} bottom_front_to_rear')
    print(f'DIMS length={length:.3f} width={width:.3f} height={height:.3f} groundClearance={min(belly,default=float("nan")):.3f} '
          f'muzzle=({muzzle[0]:.3f},{muzzle[1]:.3f},{muzzle[2]:.3f}) '
          f'hullFrontZ={hull_front:.3f} hullRearZ={hull_rear:.3f} lengthOverGun={muzzle[2]-hull_rear:.3f}')
    return total,used
