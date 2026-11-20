"""Exterior mesh for the Type 16. All stations and fittings use rest-pose game metres."""
import math

import bmesh
import jet_kit as K

RING = (0, 1.80, -0.56)
TRUN = (0, 2.25, 0.49)
AXLES = (2.39, .69, -.95, -2.36)
BUSTLE_DOORS = ((-2.554,-1.862),(-1.841,-1.257),(-1.236,-.790))


def finish(part, parent, mats):
    # Weld the poles of turned details before orienting the closed shells.
    bm = part.bm
    bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=.00001)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    return part.build(parent, mats, weld=False)


def box(p, m, x, y, z, w, h, d, bevel=0):
    p.box(m, x-w/2, x+w/2, y-h/2, y+h/2, z-d/2, z+d/2, bevel=bevel, seg=1, smooth=False)


def rod(p, m, a, b, r, n=10, end=None):
    p.cylinder(m, a, b, r, seg=n, r2=end)


def pipe(p, m, points, r=.014, n=8):
    p.tube(points, r, m, seg=n)


def loft(p, rings, mat, zones=None):
    p.loft(rings, mat, cap0=True, cap1=True, cap_centre=False, smooth=False, mats=zones)


# Measured side/deck break. The same piecewise curve supports the deck fittings.
DECK = ((-3.48,1.75),(-3.28,1.75),(-2.92,1.767),(-.56,1.777),
        (1.12,1.77),(1.92,1.74),(2.33,1.71),(2.74,1.68),(3.15,1.64),
        (3.57,1.59),(3.76,1.46))


def deck_y(z):
    for (a,ya),(b,yb) in zip(DECK,DECK[1:]):
        if z<=b: return ya+(yb-ya)*max(0,z-a)/(b-a)
    return DECK[-1][1]


def deckplate(p,m,x0,x1,z0,z1,rise,height):
    stations=[z0]+[z for z,_ in DECK if z0<z<z1]+[z1]
    loft(p,[[(x,deck_y(z)+rise+h,z) for x,h in ((x0,0),(x1,0),(x1,height),(x0,height))]
            for z in stations],m)


def bow_panel(p,q):
    # Share the corners of the actual bow face: two wells recessed into the
    # slope. Each eye emerges from its own well rather than a black decal.
    a,b,c,d=q
    for u,v,pocket in ((0,.075,False),(.075,.219,True),(.219,.781,False),(.781,.925,True),(.925,1,False)):
        lower=mix3(a,d,u); upper=mix3(b,c,u)
        patch=[lower,upper,mix3(b,c,v),mix3(a,d,v)]
        if not pocket:
            p.face(patch,'plate',False); continue
        split=[[mix3(patch[i],patch[j],f) for i,j in ((0,1),(3,2))] for f in (.28,.75)]
        lo,hi=split
        for face in ([patch[0],patch[3],lo[1],lo[0]],[hi[0],hi[1],patch[2],patch[1]]): p.face(face,'plate',False)
        inside=inset_quad(p,[lo[0],lo[1],hi[1],hi[0]],.085,(0,.013,-.052),'plate')
        cx,cy,cz=mix3(inside[0],inside[2],.5)
        pipe(p,'iron',[(cx-.068,cy+.045,cz-.015),(cx-.068,cy+.016,cz+.030),
                       (cx-.047,cy-.032,cz+.042),(cx+.046,cy-.032,cz+.042),
                       (cx+.068,cy+.016,cz+.030),(cx+.068,cy+.045,cz-.015)],.016)


def lifting_lug(p,x):
    # Pierced cheek welded to the upper transom; the hole looks across the
    # vehicle and the rounded tip projects aft, not above the deck silhouette.
    tri=[(1.724,-3.448),(1.609,-3.408),(1.667,-3.559)]
    cy,cz=1.668,-3.479
    outer=[mix3(a,b,t/6) for a,b in zip(tri,tri[1:]+tri[:1]) for t in range(6)]
    loops=[]
    for dx in (-.014,.014):
        rim=[(x+dx,y,z) for y,z in outer]; hole=[]
        for y,z in outer:
            t=math.atan2(z-cz,y-cy); hole.append((x+dx,cy+.022*math.cos(t),cz+.022*math.sin(t)))
        loops.append((rim,hole))
    for i in range(len(outer)):
        j=(i+1)%len(outer); (a,b),(c,d)=loops
        for face in ([a[i],a[j],b[j],b[i]],[c[i],c[j],d[j],d[i]],
                     [a[i],a[j],c[j],c[i]],[b[i],b[j],d[j],d[i]]): p.face(face,'rib',False)


def transom(y):
    return -3.37-.11*min(1.,max(0.,(y-1.51)/.24))


def rear_leaf(p,m,x0,x1,y0,y1,corner,offset,depth):
    # Follow the kink at y=1.51 so the upper door and gap cannot disappear
    # into the sloping rear plate. offset is measured aft from that plate.
    levels=((y0,x0+corner,x1-corner),(y0+corner,x0,x1),(1.51,x0,x1),
            (y1-corner,x0,x1),(y1,x0+corner,x1-corner))
    loft(p,[[(x,y,transom(y)-d) for x,d in ((a,offset),(b,offset),(b,offset+depth),(a,offset+depth))]
            for y,a,b in levels],m)


def hull(p):
    # Each station has four independently surveyed levels, from belly to deck.
    # The shoulder below the wheel arches turns inwards before joining the keel.
    sections=[(-3.02,.58,.75, -3.37,.97,1.39, -3.37,1.51,1.40, -3.48,1.40),
              (-2.95,.51,.86, -3.25,.95,1.20, -3.25,.98,1.47, -3.28,1.47),
              (-2.85,.46,.94, -3.06,.93,1.20, -3.06,1.13,1.48, -3.06,1.48),
              (-2.72,.45,.95, -2.85,.94,1.20, -2.85,1.32,1.49, -2.92,1.49)]
    for z,_ in DECK[3:7]:
        sections.append((z,.45,.95, z,.94,1.20, z,1.32,1.49, z,1.49))
    sections += [(2.50,.45,.95, 2.74,.94,1.20, 2.74,1.32,1.49, 2.74,1.49),
                 (2.68,.56,.95, 2.94,.86,1.16, 3.15,1.28,1.49, 3.15,1.49),
                 (2.82,.68,.95, 3.16,.79,1.08, 3.52,1.24,1.49, 3.57,1.49),
                 (2.88,.70,.95, 3.22,.78,1.04, 3.50,1.16,1.17, 3.76,1.17)]
    rings=[]
    for zb,yb,xb,zm,ym,xm,zs,ys,xs,zt,xt in sections:
        side=[(xb,yb,zb),(xm,ym,zm),(min(xm,xs)-.01,ys-.012,zs),
              (xs,ys,zs),(xt,deck_y(zt),zt)]
        rings.append(side+[(-x,y,z) for x,y,z in reversed(side)])
    p.grid(rings,'plate',closed_u=True,smooth=False,
           mats=lambda i,j:'keel' if i in (0,1,2,6,7,8,9) else 'plate')
    for ring in (rings[0],rings[-1]):
        for i in range(4):
            q=[ring[i],ring[i+1],ring[-2-i],ring[-1-i]]
            if ring is rings[-1] and i==1: bow_panel(p,q)
            else: p.face(q,'plate' if i>=2 else 'keel',False)
    # Underslung beam, with two swept brackets attaching it to the keel.
    box(p,'keel',0,.505,2.995,1.70,.17,.19,.026)
    for s in (-1,1):
        loft(p,[[(s*x,y,z) for y,z in ((.56,2.91),(.56,3.05),(.78,3.12),(.74,2.83))]
                for x in (.54,.70)],'keel')
    for s in (-1,1):
        # Stepped louvre housing extruded from its measured side elevation.
        outline=[(1.03,1.36),(1.03,1.16),(1.16,1.03),(1.77,1.03),(1.91,1.17),(1.91,1.36)]
        loft(p,[[(s*x,y,z) for z,y in outline] for x in (1.20,1.477)],'plate')
        field=[(1.06,1.665),(1.06,1.187),(1.19,1.052),(1.75,1.052),(1.883,1.187),(1.883,1.665)]
        loft(p,[[(s*x,y,z) for z,y in field] for x in (1.474,1.498)],'grille')
        for i in range(16):
            z=1.12+i*.047
            bottom=1.067+max(0,abs(z-1.47)-.27)
            box(p,'rib',s*1.50,(1.653+bottom)/2,z,.024,1.653-bottom,.019,.005)
        if s==1:
            box(p,'grille',1.495,1.58,2.13,.015,.16,.35,.015)
            for y in (1.54,1.58,1.62): box(p,'iron',1.506,y,2.13,.012,.012,.32)
        # The rear opening is the angled shoulder of the hull itself.
        poly=[(2.89,1.33),(3.44,1.23),(3.26,.94),(3.09,1.0)]
        loft(p,[[(s*x,y,z) for z,y in poly] for x in (1.16,1.465)],'plate')
        for z,top,bottom,xc,w in ((1.806,1.15,.83,1.22,.55),(-3.04,.95,.22,1.16,.58)):
            box(p,'rubber',s*xc,(top+bottom)/2,z,w,top-bottom,.036,.008)
            box(p,'iron',s*xc,top,z,w,.046,.05,.007)
        for z in AXLES:
            for y in (.49,.79):
                for dz in (-.20,.20): rod(p,'iron',(s*.84,y+.02,z+dz),(s*1.24,y-.065,z),.044)
            rod(p,'iron',(s*1.02,.58,z-.10),(s*.98,1.21,z-.14),.068)
            rod(p,'iron',(s*.72,.545,z),(s*1.25,.545,z),.076)
            # Stationary inner brake backing plate also hides the reverse livery of the shared wheel.
            rod(p,'iron',(s*1.087,.545,z),(s*1.105,.545,z),.312,32)
        # U under the grille and a separate four-point ladder in the next bay.
        pipe(p,'iron',[(s*1.435,1.055,1.315),(s*1.469,1.005,1.315),
                       (s*1.469,.827,1.315),(s*1.469,.806,1.335),
                       (s*1.469,.806,1.645),(s*1.469,.827,1.665),
                       (s*1.469,1.005,1.665),(s*1.435,1.055,1.665)],.015)
        for rz in (-.296,.096):
            pipe(p,'iron',[(s*1.395,1.325,rz),(s*1.459,1.277,rz),(s*1.464,.554,rz)],.016)
            rod(p,'iron',(s*1.194,.958,rz),(s*1.464,.577,rz),.013)
        for ry in (.567,.901): rod(p,'rib',(s*1.464,ry,-.297),(s*1.464,ry,.097),.017)
        box(p,'iron',s*1.459,.941,-.10,.036,.201,.107,.008)
        for x,y,z in ((1.471,1.06,3.26),(1.471,.93,3.34),(1.47,1.015,1.55),(1.48,1.0,-.10),(1.48,.88,-.10),(1.475,1.27,-2.93)):
            rod(p,'iron',(s*(x-.022),y,z),(s*x,y,z),.046,16)
            rod(p,'amber',(s*x,y,z),(s*(x+.011),y,z),.035,16)
        # Four-sided open front rim, two divided pockets. Lens faces sit behind
        # the metal lip (inboard pair) or inside a separate circular ferrule.
        box(p,'plate',s*1.285,1.039,3.34,.37,.306,.21,.018)
        box(p,'grille',s*1.285,1.039,3.447,.338,.28,.015,.006)
        for x in (1.109,1.461): box(p,'rib',s*x,1.039,3.456,.018,.30,.043,.004)
        for y in (.895,1.183): box(p,'rib',s*1.285,y,3.456,.37,.018,.043,.004)
        box(p,'iron',s*1.302,1.039,3.46,.017,.274,.034,.004)
        box(p,'iron',s*1.208,1.039,3.461,.17,.014,.032,.003)
        for y in (.976,1.103): box(p,'headlight',s*1.208,y,3.455,.146,.083,.013,.006)
        for y,m in ((1.11,'headlight'),(.976,'amber')):
            rod(p,'iron',(s*1.390,y,3.444),(s*1.390,y,3.470),.055,20)
            rod(p,m,(s*1.390,y,3.469),(s*1.390,y,3.475),.045,20)
        # Tubular corners have four returns to the armour; keep the cage empty
        # across the lenses. Depth is visible from a front quarter view.
        for x in (1.107,1.462):
            for y in (.890,1.192): box(p,'rib',s*x,y,3.461,.016,.016,.118,.002)
            box(p,'rib',s*x,1.041,3.513,.016,.317,.016,.002)
        for y in (.890,1.192): box(p,'rib',s*1.285,y,3.513,.367,.016,.016,.002)
        # Flush transom sockets. All lens and box faces remain outside the rear
        # plate at -3.37, with only about one centimetre of stand-off.
        box(p,'plate',s*1.18,1.175,-3.341,.36,.35,.077,.016)
        rod(p,'iron',(s*1.18,1.25,-3.377),(s*1.18,1.25,-3.385),.067,20)
        for x,m,w in ((1.054,'clear',.077),(1.166,'taillight',.13),(1.289,'amber',.084)):
            box(p,m,s*x,1.085,-3.382,w,.071,.009,.003)
        lifting_lug(p,s*1.29)
        for x in (.992,1.115): box(p,'keel',s*x,.982,-3.357,.056,.094,.096,.010)
        pipe(p,'iron',[(s*.990,.986,-3.384),(s*.990,.936,-3.418),(s*1.015,.891,-3.438),
                       (s*1.091,.891,-3.438),(s*1.117,.936,-3.418),(s*1.117,.986,-3.384)],.023)
    # Exactly 10 mm of dark reveal outside the slightly right-of-centre leaf.
    rear_leaf(p,'grille',-.6175,.2375,.993,1.721,.045,-.003,.019)
    rear_leaf(p,'door',-.6075,.2275,1.003,1.711,.043,.014,.017)
    for y in (1.158,1.568):
        leaf=[(-.641,y-.036),(-.366,y-.028),(-.310,y),(-.366,y+.028),(-.641,y+.036)]
        loft(p,[[(x,h,transom(h)-off) for x,h in leaf] for off in (.030,.071)],'rib')
        rod(p,'iron',(-.624,y-.047,transom(y-.047)-.068),(-.624,y+.047,transom(y+.047)-.068),.026,16)
    box(p,'iron',.181,1.410,-3.424,.075,.091,.050,.008)
    box(p,'rib',.222,1.409,-3.449,.100,.038,.018,.004)
    # Keeper and folded hasp; leave the square eye open against the door.
    pipe(p,'iron',[(.250,1.428,-3.447),(.250,1.428,-3.478),(.250,1.394,-3.478),(.250,1.394,-3.447)],.008)
    pipe(p,'rib',[(.145,1.342,-3.401),(.145,1.342,-3.456),(.155,1.408,-3.456)],.012)
    for x in (.46,.76,.868):
        r=.014 if x>.80 else .018
        def stem(y): return (x-.04+(y-1.125)*.19,y,transom(y)-.043)
        pipe(p,'tool',[stem(y) for y in (1.125,1.51,1.681)],r)
        for y in (1.308,1.570):
            cx,_,cz=stem(y)
            pipe(p,'rib',[(cx-.032,y,transom(y)),(cx-.032,y,cz-.018),(cx+.032,y,cz-.018),(cx+.032,y,transom(y))],.008)
    # Dished shovel blade with a tapered cutting edge and a raised central ridge.
    blade=[(.329,1.215),(.474,1.202),(.507,1.144),(.491,1.034),(.436,.995),(.353,1.024),(.321,1.151)]
    for i,(x,y) in enumerate(blade):
        u,v=blade[(i+1)%len(blade)]
        p.face([(.418,1.135,-3.473),(x,y,-3.444),(u,v,-3.444)],'iron',False)
        p.face([(.418,1.135,-3.427),(u,v,-3.444),(x,y,-3.444)],'tool',False)
    loft(p,[[(x,y,z) for x,y in ((.622,1.156),(.791,1.14),(.826,1.098),(.731,1.11),(.685,1.073))]
            for z in (-3.421,-3.448)],'iron')
    # Bow fittings are flush impressions in the atlas (including the scope
    # strip). Only the small lifting handles rise through the sightline.
    for x,z in ((.4385,2.8575),(1.0325,3.0225)):
        y=deck_y(z)
        pipe(p,'iron',[(x-.058,y-.003,z),(x-.058,y+.025,z),(x+.058,y+.025,z),(x+.058,y-.003,z)],.006)


def mix3(a,b,t):
    return tuple(v+(w-v)*t for v,w in zip(a,b))


def inset_quad(p,quad,rim=.07,offset=(0,0,-.025),frame='cheek',floor='grille'):
    # Replace a single outer face: surround, four reveal faces, blind pocket.
    a,b,c,d=quad
    def uv(u,v): return mix3(mix3(a,b,u),mix3(d,c,u),v)
    inner=[uv(u,v) for u,v in ((rim,rim),(1-rim,rim),(1-rim,1-rim),(rim,1-rim))]
    low=[tuple(x+y for x,y in zip(v,offset)) for v in inner]
    for j in range(4):
        k=(j+1)%4
        p.face([quad[j],quad[k],inner[k],inner[j]],frame,False)
        p.face([inner[j],inner[k],low[k],low[j]],'iron',False)
    p.face(low,floor,False)
    return inner


def roof_stack(p,x,z,levels,mat):
    # Width, depth and clipping of each square section can all change with height.
    rings=[]
    for y,w,d,c in levels:
        a=w/2; b=d/2
        rings.append([(x+i,y,z+j) for i,j in ((-a+c,-b),(a-c,-b),(a,-b+c),(a,b-c),
                                                (a-c,b),(-a+c,b),(-a,b-c),(-a,-b+c))])
    loft(p,rings,mat)


def turret_shell(p):
    rod(p,'iron',(0,1.75,-.56),(0,1.838,-.56),.94,56)
    # Separate cheek lofts leave a genuine channel for the moving shield. The
    # belt advances farther than either roof or floor to give the sharp apex.
    for s in (-1,1):
        rings=[]
        for z,inner,base,belt,roof,y0,y1,y2,d0,d1,d2 in (
                (-2.62,.003,.96,1.09,.98,1.96,2.42,2.51,0,0,.05),
                (-1.85,.003,1.0,1.12,1.00,1.82,2.15,2.55,0,0,0),
                (-1.60,.003,1.02,1.15,1.00,1.81,2.10,2.54,0,0,0),
                (-.74,.003,1.03,1.27,.97,1.81,2.09,2.52,0,0,0),
                (.39,.399,.99,1.32,.97,1.83,2.075,2.394,0,0,0),
                (1.12,.414,.945,1.27,.94,1.82,2.03,2.358,-.47,0,-.63)):
            # At the forward cut the underside sweeps back from the outer belt
            # to z=.65 under the cheek and z=.45 at the bay. A short bevel on
            # the INNER roof edge exposes daylight beside the moving shield.
            nose=z>1.0; dip=.128 if nose else .095 if z>0 else 0
            zi=z+d0-(.20 if nose else 0); zr=z+d2
            rings.append([(s*inner,y0,zi),(s*base,y0,z+d0),
                          (s*belt,y1,z+d1),(s*roof,y2,zr),
                          (s*(inner+.20),y2,zr),(s*(inner+dip*.42),y2-dip,zr-.36*dip),
                          (s*inner,y1+.047,z+d1-(.17 if nose else 0))])
        # Explicit lower and upper front facets: don't let an n-gon tessellator
        # bridge the cut from the toe to the roof across the belt line.
        # Add a station at each end of the smoke gallery, retaining the original
        # belt and roof lines. Omit the skin over the gallery rather than trying
        # to bury black boxes and cylinders into an intact upper cheek surface.
        aft,fore=rings[3:5]
        cuts=[[mix3(a,b,(z+.74)/1.13) for a,b in zip(aft,fore)] for z in (-.72,-.065)]
        rings[4:4]=cuts
        p.face(list(reversed(rings[0])),'cheek',False)
        for j,(r,t) in enumerate(zip(rings,rings[1:])):
            for i in range(7):
                k=(i+1)%7; q=[r[i],t[i],t[k],r[k]]
                if i==2 and j==4:
                    lo=[mix3(q[0],q[3],.28),mix3(q[1],q[2],.28)]
                    hi=[mix3(q[0],q[3],.73),mix3(q[1],q[2],.73)]
                    p.face([q[0],q[1],lo[1],lo[0]],'cheek',False)
                    p.face([hi[0],hi[1],q[2],q[3]],'cheek',False)
                    inset_quad(p,[lo[0],lo[1],hi[1],hi[0]],.035,(-s*.14,-.030,0))
                    # Continuous lower armour lip, not a strip supporting buttons.
                    lip=[tuple(v+d for v,d in zip(pt,(s*.023,.022,0))) for pt in lo]
                    loft(p,[[pt,(pt[0]-s*.018,pt[1]-.028,pt[2]),
                             (ep[0],ep[1]-.025,ep[2]),ep] for pt,ep in zip(lo,lip)],'cheek')
                else:
                    p.face(q,'chin' if i in (0,1,6) else 'cheek',False)
        r=rings[-1]
        for indices,zone in (((0,1,2),'chin'),((0,2,6),'chin'),((6,2,3),'cheek'),
                             ((6,3,4),'cheek'),((6,4,5),'cheek')):
            p.face([r[i] for i in indices],zone,False)
    loft(p,[[(x,y,z) for x,y in ((-.432,1.84),(.432,1.84),(.432,top),(-.432,top))]
            for z,top in ((-2.235,2.48),(-.48,2.495),(.18,2.418))],'cheek')
    for s in (-1,1):
        for j in range(4):
            z=-.157-j*.148
            # Shoulder crosses the skin at ~1.16; the last 10 cm of cylinder
            # are clear of the lip. The cap overhangs it by just 2 mm.
            rod(p,'iron',(s*1.076,2.181,z),(s*1.236,2.341,z),.040,20)
            rod(p,'rib',(s*1.219,2.324,z),(s*1.236,2.341,z),.041,20)
            rod(p,'tool',(s*1.236,2.341,z),(s*1.242,2.347,z),.043,20)
        # Wedge blister with a recessed outer window. Its foot follows the side slope.
        q=[(s*1.213,2.165,.043),(s*1.221,2.165,.188),(s*1.107,2.397,.154),(s*1.107,2.397,.058)]
        out=[(x+s*.071,y,z) for x,y,z in q]
        for j in range(4):
            k=(j+1)%4; p.face([q[j],q[k],out[k],out[j]],'cheek',False)
        p.face(q,'cheek',False); inset_quad(p,out,.15,(-s*.017,0,0),floor='optic')
        # Rectangular doors on the boxy bustle. Each is a folded leaf: split
        # its face where it crosses the casting's belt, so no edge sinks inside.
        for z0,z1 in BUSTLE_DOORS:
            columns=[]
            for z in (z0,z1):
                j=next(i for i in range(3) if z<=rings[i+1][2][2])
                a,b=rings[j],rings[j+1]; f=(z-a[2][2])/(b[2][2]-a[2][2])
                bot,line,roof=[mix3(a[k],b[k],f) for k in (1,2,3)]
                col=[]
                for h in (2.006,line[1],2.463):
                    l,r=(bot,line) if h<=line[1] else (line,roof)
                    x,_,_=mix3(l,r,(h-l[1])/(r[1]-l[1])); col.append((x+s*.024,h,z))
                columns.append(col)
            a,b=columns
            for j in (0,1): p.face([a[j],b[j],b[j+1],a[j+1]],'bustle',False)
            rim=a+list(reversed(b)); inner=[(x-s*.033,y,z) for x,y,z in rim]
            for i in range(6):
                k=(i+1)%6; p.face([rim[i],rim[k],inner[k],inner[i]],'rib',False)
            p.face(inner,'cheek',False)
        loft(p,[[(s*x,y,z) for z,y in ((-2.008,2.393),(-1.798,2.393),(-1.798,2.484),(-2.008,2.484))]
                for x in (1.035,1.083)],'cheek')
        box(p,'rib',s*1.136,2.471,-1.903,.186,.031,.188,.008)
        for z in (-1.969,-1.836): rod(p,'iron',(s*1.074,2.384,z),(s*1.211,2.46,z),.013)
        wx=1.181
        rod(p,'iron',(s*wx,2.484,-1.90),(s*wx,2.542,-1.90),.055,16)
        rod(p,'rib',(s*wx,2.542,-1.90),(s*wx,2.604,-1.90),.046,16,.031)
        dx=math.tan(math.radians(8)); dz=math.tan(math.radians(15)); dy=2.4/math.sqrt(1+dx*dx+dz*dz)
        rod(p,'iron',(s*wx,2.602,-1.9),(s*(wx+dx*dy),2.602+dy,-1.9-dz*dy),.010,8,.0035)
    # Bent rails with quarter-round returns and separate short diagonal feet.
    for y in (2.02,2.20,2.43):
        left=[(-1.06,y,-2.693)]+[(-.974-.086*math.cos(t*math.pi/10),y,-2.758-.086*math.sin(t*math.pi/10)) for t in range(6)]
        pipe(p,'rib',left+[(-x,h,z) for x,h,z in reversed(left)],.016)
    for x in (-.95,-.64,-.32,0,.32,.64,.95):
        rod(p,'rib',(x,2.02,-2.844),(x,2.43,-2.844),.013)
        if abs(x) in (.95,.32):
            pipe(p,'rib',[(x,1.984,-2.602),(x,2.02,-2.837),(x,2.12,-2.837)],.015)
    # Forward edge of the basket clears the transom; these four outriggers
    # bridge the 6 cm of daylight, unlike the thin rails of the basket itself.
    for s in (-1,1):
        for y in (2.02,2.43):
            box(p,'cheek',s*1.023,y,-2.616,.105,.094,.039,.008)
            rod(p,'iron',(s*1.024,y,-2.626),(s*1.06,y,-2.709),.024,10)
    # Commander's vision drum: trapezoidal glass blocks are let into flat
    # facets, protected by a projecting upper flange. The loader has a low lid.
    x,z=-.52,-.79
    rod(p,'iron',(x,2.49,z),(x,2.552,z),.335,32)
    n=10; radius=.319
    for i in range(n):
        a,b=[j*math.tau/n for j in (i,i+1)]
        q=[(x+radius*math.cos(t),y,z+radius*math.sin(t)) for t,y in ((a,2.547),(b,2.547),(b,2.649),(a,2.649))]
        mid=(a+b)/2
        inset_quad(p,q,.16,(-.012*math.cos(mid),0,-.012*math.sin(mid)),floor='optic')
    rod(p,'cheek',(x,2.646,z),(x,2.680,z),.333,32,.311)
    for x,z,base,r in ((-.52,-.79,2.679,.295),(.51,-1.23,2.551,.315)):
        rod(p,'iron',(x,base-.024,z),(x,base+.007,z),r,32)
        rod(p,'cheek',(x,base+.005,z),(x,base+.026,z),r*.99,32,r*.96)
        pipe(p,'iron',[(x-.067,base+.027,z),(x-.067,base+.056,z),(x+.067,base+.056,z),(x+.067,base+.027,z)],.010)
        for dx in (-.13,.13): rod(p,'rib',(x+dx-.034,base+.023,z-.253),(x+dx+.034,base+.023,z-.253),.020)
    roof_stack(p,.578,-.48,[(2.481,.485,.64,.033),(2.566,.485,.64,.033),(2.598,.42,.55,.047),
                             (2.728,.408,.534,.047),(2.75,.364,.46,.044)],'cheek')
    rod(p,'iron',(.578,2.747,-.48),(.578,2.783,-.48),.167,24)
    roof_stack(p,.578,-.48,[(2.78,.347,.362,.046),(2.816,.357,.376,.047),(2.913,.295,.324,.046)],'cheek')
    # Tilt the optical face back to follow the tapered head.
    q=[(.456,2.814,-.289),(.700,2.814,-.289),(.679,2.905,-.311),(.477,2.905,-.311)]
    inset_quad(p,[(x,y,z+.012) for x,y,z in q],.065,(0,0,-.008),'iron','optic')
    roof_stack(p,.578,-.48,[(2.910,.323,.348,.041),(2.934,.306,.336,.040)],'rib')
    # Hood has a back and two jambs; the window is behind the brow, not on it.
    box(p,'cheek',-.637,2.450,.205,.45,.182,.32,.022)
    box(p,'grille',-.637,2.482,.366,.394,.108,.013,.006)
    box(p,'optic',-.642,2.48,.375,.302,.080,.012,.006)
    for x in (-.847,-.427): box(p,'cheek',x,2.483,.393,.030,.126,.077,.005)
    box(p,'rib',-.637,2.549,.295,.47,.034,.335,.009)
    for x in (-.500,-.484): box(p,'iron',x,2.482,.385,.013,.087,.010)
    # Open fork on a low foot. Two tapered blades seen from the front, and a
    # diagonal in the fore-aft view; the central opening has no backing face.
    roof_stack(p,.212,-.646,[(2.495,.35,.37,.04),(2.555,.35,.37,.04),(2.580,.31,.33,.033)],'cheek')
    for side in (-1,1):
        center=.229+side*.127
        loft(p,[[(x+side*dx,y,z) for z,y,dx in ((-.801,2.574,.014),(-.730,2.574,.014),(-.535,3.075,-.026),(-.590,3.075,-.026))]
                for x in (center-.014,center+.014)],'iron')
        rod(p,'rib',(.229+side*.119,2.579,-.483),(.229+side*.106,2.909,-.654),.016,12)
    box(p,'iron',.235,3.080,-.584,.230,.057,.172,.009)
    # Single deep cradle on vehicle right (-X); ammunition hangs to +X.
    loft(p,[[(x,y,z) for z,y in ((-.831,3.190),(-.79,3.090),(-.49,3.081),(-.429,3.158),(-.49,3.201))]
            for x in (.112,.151)],'tool')
    box(p,'iron',.235,3.186,-.62,.136,.147,.47,.018)
    box(p,'iron',.331,3.124,-.658,.093,.052,.161,.009)
    box(p,'tool',.432,3.146,-.65,.177,.184,.250,.011)
    box(p,'rib',.432,3.243,-.65,.193,.022,.262,.005)
    rod(p,'iron',(.235,3.20,-.388),(.235,3.20,-.142),.049,16,.039)
    rod(p,'iron',(.235,3.20,-.148),(.235,3.20,.38),.027,16,.022)
    for x in (.175,.295):
        rod(p,'iron',(x,3.169,-.82),(x,3.194,-1.22),.018)
        rod(p,'rubber',(x,3.139,-1.22),(x,3.250,-1.22),.025)


def gun_shell(p):
    x,y,z=TRUN
    box(p,'iron',0,y-.043,z-.35,.65,.318,.98,.035)
    rings=[]
    for d,w,bot,top in ((-.24,.384,-.218,.170),(.43,.398,-.215,.110),(.88,.328,-.174,.070)):
        rings.append([(a,y+b,z+d) for a,b in ((-w+.04,bot),(w-.04,bot),(w,bot+.045),(w,top-.034),(w-.045,top),(-w+.045,top),(-w,top-.034),(-w,bot+.045))])
    # Two half-octagons meet along the front's centreline. Use identical
    # boundary subdivisions on the shell and recesses (no hidden cap or T joints).
    def perimeter(q,side,divider):
        ids=(0,7,6,5) if side<0 else (1,2,3,4)
        pts=[mix3(q[0],q[1],.5)]+[q[i] for i in ids]+[mix3(q[4],q[5],.5)]
        seq=pts+[pts[0]] if divider else pts
        edge=[mix3(a,b,j/4) for a,b in zip(seq,seq[1:]) for j in range(4)]
        return edge if divider else edge+[pts[-1]]
    shell=[perimeter(q,1,False)+list(reversed(perimeter(q,-1,False)[1:-1])) for q in rings]
    p.loft(shell,'shield',cap0=True,cap1=False,smooth=False)
    front=z+.88
    for side in (-1,1):
        cx=side*.226; cy=y-.055
        rect=[(px,py) for px,py,_ in perimeter(rings[-1],side,True)]
        surfaces=[[(x1,y1,front) for x1,y1 in rect]]
        for rad,depth in ((.038,0),(.030,-.007),(.028,-.027)):
            ring=[]
            for x1,y1 in rect:
                t=math.atan2(y1-cy,x1-cx); ring.append((cx+rad*math.cos(t),cy+rad*math.sin(t),front+depth))
            surfaces.append(ring)
        p.loft(surfaces,'shield',cap1='grille',cap_centre=False,smooth=False,mats=lambda i,j:'iron' if j==2 else 'shield')
    # Lip follows the face. A single biased fabric bulge runs smoothly into
    # the cylindrical sleeve; neither a stack of washers nor a see-through gap.
    def boot_ring(d,rx,ry,flatten,wrinkle):
        pts=[]
        for i in range(40):
            t=i*math.tau/40; sn=math.sin(t); c=math.cos(t)
            fac=1+wrinkle*(.65*math.cos(5*t+.4)+.35*math.sin(3*t))
            pts.append((rx*c*fac,y+ry*sn*(flatten if sn>0 else 1)*fac,z+d-.014*sn))
        return pts
    lip=[boot_ring(*v) for v in ((.846,.193,.166,.59,0),(.879,.194,.171,.61,0),
                                   (.903,.182,.163,.66,0),(.903,.163,.143,.73,0))]
    p.loft(lip,'shield',cap0=True,cap1=True,cap_centre=False,smooth=True)
    boot=[boot_ring(*v) for v in ((.887,.159,.141,.76,.015),(.917,.178,.153,.78,.030),
                                   (.975,.170,.146,.88,.038),(1.021,.138,.132,.97,.027),
                                   (1.068,.113,.113,1,.004))]
    p.loft(boot,'rubber',cap0=True,cap1=True,cap_centre=False,smooth=True)
    # One manifold turned shell. Consecutive rings AT the same station close
    # both exposed annuli: .1125 -> .157 at 1.40, .157 -> .0925 at 1.95.
    # No coincident caps on the collar planes. Keep a crisp normal on each step.
    profile=[(0,1.033),(.1125,1.033),(.1125,1.40),(.157,1.40),(.160,1.405),
             (.160,1.431),(.150,1.435),(.150,1.915),(.160,1.919),(.160,1.945),
             (.157,1.95),(.0925,1.95),(.075,3.415),(.080,3.415),(.080,3.45),
             (.070,3.45),(.070,4.15),(.0525,4.15),(.0525,4.128),(0,4.128)]
    faces=p.revolve('sleeve',profile,TRUN,axis=(0,0,1),seg=40,
                    mat_of=lambda k:'bore' if k>=17 else 'brake' if k>=15 else 'shield' if k in (3,4,5,7,8,9,12,13) else 'sleeve')
    for i,face in enumerate(faces):
        k=i%(len(profile)-1)
        if profile[k][1]==profile[k+1][1]: face.smooth=False


def build(body,turret,gun,mats):
    parts=[]
    for name,fn,parent in (('hull_casting',hull,body),('turret_casting',turret_shell,turret),('gun_casting',gun_shell,gun)):
        p=K.Part(name)
        fn(p)
        parts.append(finish(p,parent,mats))
    return parts
