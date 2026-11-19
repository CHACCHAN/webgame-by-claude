"""Type 10 exterior game mesh. Stations from the ground-anchored fit are in game metres (x left, y up, z forward)."""
import argparse
import math
import sys
from pathlib import Path

import bpy
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import tank_kit as K
import jet_kit as J


T = {
    "hull": {
        # Each rib: deck z/y, keel z/y, half-widths at keel/chine/deck.
        "ribs": ((-3.625,1.665,-3.58,.88,.83,.93,1.08),
                 (-3.43,1.60,-3.02,.43,.85,.95,1.12),
                 (-1.66,1.60,-1.66,.43,.88,.97,1.15),
                 (-1.40,1.54,-1.40,.43,.88,.97,1.15),
                 (1.38,1.54,1.38,.43,.88,.97,1.15),
                 (2.04,1.53,2.04,.43,.87,.96,1.14),
                 (2.49,1.48,2.49,.43,.86,.95,1.12),
                 (3.575,1.17,2.925,.43,.83,.93,1.08)),
        "chine_fraction": .42,
        # Set the stern furniture INTO the two return bays; retain the centre profile.
        "stern_spine": .030, "stern_bay_start": .102, "stern_set_in": (.22,.10),
        "arm": {"profile": ((-.33,.21),(-.25,.28),(.065,.045),(.056,-.046),(-.053,-.06)),
                "span": (.94,1.075)},
        # Shoulder ribs: z, inner/outer x, underside, top. High underside over sprocket.
        "shoulder": ((-3.51,1.01,1.53,1.26,1.48),(-3.20,1.01,1.56,1.265,1.55),
                     (-1.66,1.04,1.56,1.265,1.55),(1.98,1.03,1.56,1.265,1.46),
                     (2.94,1.01,1.55,1.235,1.34),(3.39,1.00,1.57,1.16,1.235),
                     (3.57,.95,1.62,1.12,1.146)),
        "bins": {"x":1.325,"width":.44,"bottom":1.535,"top":1.620,
                 "runs":((-3.18,-2.57),(-2.545,-1.74)),"bevel":.023,"lid":.019,"lip":.011},
        "rear_bins": {"x":.72,"y":1.575,"z":-3.405,"size":(.87,.18,.35),"bevel":.027},
        "engine": {"x":.535,"z_span":(-3.22,-1.75),"bed_y":1.606,"width":.92,"height":.034,"slats":17,"rim":.020,"rim_h":.024,"division_gap":.065},
        "driver": {"z":2.11,"size":(.63,.56),"lid":.033,"blocks":((-.205,2.335,-.27),(0,2.385,0),(.205,2.335,.27)),
                   "block_size":(.145,.085,.104),"block_lift":.053},
        "nose": {"head":(.79,1.11,3.52),"head_size":(.18,.13,.105),
                 "mesh_x":(-.057,-.019,.019,.057),"mesh_y":(-.031,.0,.031),
                 "mesh_span":(.16,.107),"mesh_lift":.009,"wire":.0028,
                 "signal":(1.21,1.27,3.47),"signal_size":(.114,.095,.136),"signal_dx":.055,
                 "guard_path":((-.145,-.045,.055),(-.145,.074,.055),(.145,.074,.055),(.145,-.045,.055)),
                 "guard_radius":.009,"signal_r":.044,"signal_depth":.012,"eye":(.49,.84,3.365),"eye_radius":.066,"eye_bar":.016,
                 "eye_pad":(.185,.077,.089),"eye_inset":.043,"eye_drop":.173,"eye_sweep":.045},
        "stern": {"banks":((.415,.825,.591,7),(1.004,.282,.459,6)),"vent_y":1.177,"vent_depth":.227,"vent_bevel":.015,
                  "forward_overlap":.028,"inset_depth":.007,"slat_section":(.022,.025),
                  "slat_tilt":18.,
                  "cable":((.30,1.521,-3.410),(.21,1.533,-3.460),(.157,1.502,-3.559),(.183,1.435,-3.622),
                           (.285,1.403,-3.653),(.65,1.34,-3.677),(.96,1.279,-3.686),(1.089,1.289,-3.679),
                           (1.13,1.335,-3.661),(1.104,1.376,-3.646),(1.027,1.387,-3.635),(.974,1.373,-3.646)),
                  "cable_r":.019,"cable_clamp":(.043,.049,.055),
                  "eye_xy":(.46,.906),"eye_radius":.061,"eye_bar":.015,
                  "lamp":(1.29,.89,-3.53),"lamp_size":(.23,.09,.085),
                  "lamp_support":(1.29,1.078,-3.45),"support_size":(.28,.486,.073),"support_bevel":.012},
        "tube_segments":8,
    },
    "skirt": {
        "seams":(3.58,1.91,.69,-.46,-1.59,-2.78,-3.52), "gauge":.032,"gap":.015,
        "top":1.27,"base":.595,"front_tip":1.16,"front_foot":3.174,"rear_tip":1.04,
        "hole": {"half_height":.052,"half_width":.093,"radius":.026,
                 "stations":(((2.37,.99),(2.83,.99),(2.65,.69)),(),(),(),
                             ((-1.78,.97),(-2.24,.97),(-1.87,.67)),())},
        "hinge": {"fractions":(.21,.77),"inset":.024,"r":.022,"y":1.265,"length":.135},
        "bolts": {"y":.632,"margin":.15,"count":4,"radius":.014,"height":.003},
        "drops": {"bottom":(.35,.30,.28,.30,.34),"upper":.605,"gap":.031,"gauge":.017,
                  "mid_height":.42,"x_rows":(1.598,1.574,1.582),"clip":.085,"clip_start":.77},
        # Ground-anchored (inner,outer) face corners, xyz, left side. Reflect x only.
        "apron": {"strap_h":.032,"strap_depth":.018,"strap_bolts":5,"bolt_r":.012,
                  "ribs":(((.95,1.14,3.57),(1.64,1.14,3.57)),
                          ((.95,1.105,3.60),(1.64,1.105,3.60)),
                          ((.95,.82,3.74),(1.63,.83,3.74))),"gauge":.016},
        "cheek": {"span":(1.54,1.60),"profile":((3.15,1.25),(3.53,1.17),(3.59,1.105),(3.65,.86),(3.40,.978))},
        "mudflap": {"ribs":(((.965,1.265,-3.446),(1.52,1.265,-3.446)),
                             ((.95,.944,-3.46),(1.515,.946,-3.46)),
                             ((.93,.43,-3.41),(1.48,.45,-3.40))),"gauge":.018},
    },
    # Hull frame at zero aim. Roof is a datum, not the overall height.
    'ring': (1.55,-.02), 'trunnion': (1.96,1.40), 'roof': 2.30,
    'elevation': (-7.,10.), 'check_yaw': (0.,30.),
    'gear': dict(track_centre=1.25,track_width=.60,track_thickness=.05,pitch=.16,
                 road=((2.12,.37),(1.06,.37),(0.,.37),(-1.06,.37),(-2.12,.37)),
                 sprocket=(-3.05,.83,.37,12,.46), idler=(2.92,.73,.35),
                 rollers=((1.59,1.06,.13),(0.,1.06,.13),(-1.59,1.06,.13)),
                 horns=1,horn_height=.063,horn_width=.040,sag=.018,pad_share=.72,
                 wheel_width=.46,tyre_width=.15,tyre_depth=.064,dish_depth=.031,hub_bolts=8,
                 skirt_outer=1.62),
    'tile_links':8, 'tyre_colour':'#2C2E29', 'track_colour':'#59564C',
    # For each station of the half-outline: three corresponding (|x|,z) points.
    # The first two make a flat beside the gun; the long slant starts at the second.
    'turret': dict(
        lower=((.30,1.78),(.84,1.73),(1.30,1.59),(1.32,1.34),(1.415,.48),(1.43,-1.40),(1.44,-1.95)),
        crease=((.30,2.23),(.83,2.18),(1.32,1.59),(1.35,1.34),(1.44,.48),(1.445,-1.40),(1.43,-1.95)),
        upper=((.30,1.82),(.795,1.77),(1.14,1.405),(1.185,1.14),(1.24,.40),(1.24,-1.39),(1.195,-1.83)),
        lower_y=(1.641,1.641,1.604,1.602,1.621,1.673,1.670),crease_y=(1.98,1.98,1.98,1.98,1.98,1.99,2.010), slot_back=.95,
        core_halfwidth=1.15, core_front=.95,core_aft=-1.48,core_y=(1.667,2.275),
        race=((1.525,.95),(1.54,1.045),(1.60,1.045),(1.635,.985)),
        # Three butt-jointed side modules on the long flank, aft-most steps up.
        modules=((.48,-.10,1.617),(-.115,-.68,1.635),(-.695,-1.30,1.66)),
        module_x=(1.401,1.456,1.432), module_y=(1.975,2.056),
        covers=((.19,.38),(-.27,.26),(-.535,.24),(-.85,.28),(-1.14,.26)),
        cover_y=1.824, cover_h=.326, cover_x=1.454,cover_t=.022,
        tab_size=(.036,.048,.057), tab_y=1.982,tab_offset=.32,
        loop_x=1.372,loop_y=2.082,loop_z=(.233,-.399,-1.01),loop_half=.075,loop_h=.052,loop_r=.012,
        coax=(.53,2.014,2.165),coax_radius=.053,
        # Fixed annular mantlet and inner dark lip: (z,outer X/Y radii,inner X/Y radii).
        surround=((1.35,.353,.225,.215,.182),(1.52,.349,.236,.225,.187),
                  (1.63,.316,.232,.230,.202)),
        socket=((1.615,.240,.209,.227,.199),(1.669,.238,.217,.227,.207))),
    'rack': dict(half=1.35,front=-1.88,rear=-3.135,base=1.735,rail=2.153,mesh_top=1.933,
                 cap_r=.0175,post_r=.012,horizontal_r=.013,skin=.008,back_div=9,side_div=4,
                 cleats=(-.96,.96),cleat_size=(.064,.094,.18)),
    'roof_fit':dict(
        pano_top=((-0.99,2.75,-.33),(-.61,2.81,-.63),(-1.08,2.79,-.91)), # FO, FI, RO
        plinth_lo=(.47,.51),plinth_hi=(.425,.45),plinth_h=.202,
        pano_gap=.019,head_brow=(.45,.026,.060),shutter_size=(.30,.132,.016),
        handle_half=.123,handle_h=.032,handle_r=.009,
        # Forward optical face (also the game's eye), not the panoramic head.
        sight=(.60,2.444,.912),hood_cz=.73,hood_size=(.49,.27,.46),hood_t=.026,
        hood_window=(.344,.158,.014),hood_foot=.032,
        cupola=(-.48,-.05),cup_profile=((0.,.315),(.044,.34),(.109,.316),(.131,.342),(.157,.331)),
        blocks=9,block_radius=.319,block_y=.077,block_size=(.141,.062,.029),
        hatch=(.48,-.32),hatch_size=(.55,.61),hatch_t=.045,
        warning=(1.13,2.290,.82),warning_r=.067,warning_foot=(.183,.030,.166),
        aft_fitting=(1.306,2.086,-1.49),fitting_size=(.036,.158,.105),
        antenna=(1.16,2.297,-1.46),antenna_r=.041,antenna_base_h=.117,whip_delta=(.048,.435,-.099),whip_r=.007,
        mast=(0.,2.30,-1.32),mast_h=.532,mast_r=.025,mast_cap=(.079,.044,.067),
        pintle=(-.35,2.443,.03),mg_scale=1.00,mg_post=.074,
        mg_lift=.054,bag_offset=(-.142,.281,-.128),bag_size=(.122,.194,.229),
        mg_body=(.157,.152,.466),mg_centre=(0.,.364,-.08),mg_box=(.212,.211,.274),
        mg_box_centre=(.160,.324,-.126),mg_fork=(.109,.210,.414,-.158,.095),
        mg_stock_z=-.408,mg_jacket_z=.420,mg_tip=.99,mg_tip_r=.021),
    # Axial station and outside diameter, all z in hull frame; inside is a blind dark socket.
    'tube':dict(muzzle_y=1.99,root=((1.37,.245),(1.60,.271),(1.835,.312)),
                boot=((1.826,.323),(1.852,.40),(1.903,.374),(1.934,.390),(1.994,.350),(2.044,.372),
                      (2.111,.343),(2.156,.359),(2.222,.322),(2.275,.340),(2.38,.320)),
                wrinkle=.011,
                sleeves=((2.38,3.42,.320,.290),(3.42,4.62,.280,.240),(4.62,5.51,.230,.200)),
                clamp_width=.050,clamp_rise=.012,
                muzzle=((5.506,.200),(5.664,.200),(5.681,.208),(5.710,.208)),
                bore=.120,bore_recess=.154,
                reference=(-.13,1.97,5.53),ref_size=(.11,.10,.17),ref_glass=(.081,.069,.004),
                dots=(-.022,0.,.022),dot_r=.006),
    'zones':dict(race_contact=('#363831',.28,.78),skirt_rubber=('#34372F',.00,.91), amber=('#ad6926',.06,.38),
                 rack_mesh=('#4b5042',.35,.79), sensor=('#8d9282',.03,.73)),
    'paint':dict(pattern='type10',brown_fraction=.40,base='#505845',green='#505845',brown='#716651',dust='#a79778',
                 dust_strength=.11,scale=1.,seed=10),
}


def _h_tub(h):
    p = J.Part('folded tub')
    ribs = []
    for i,(zt,yt,zb,yb,wb,wc,wt) in enumerate(h['ribs']):
        c = h['chine_fraction']
        rib = []
        for w,z,y in ((wb,zb,yb),(wc,zb+(zt-zb)*c,yb+(yt-yb)*c),(wt,zt,yt)):
            a,b = h['stern_spine'],h['stern_bay_start']
            rib.append([(x,y,z+(h['stern_set_in'][i] if i<len(h['stern_set_in']) and abs(x)>=b else 0))
                        for x in (-w,-b,-a,a,b,w)])
        ribs.append(rib)
    def _h_face(q):
        p.face(q,K.PAINT,smooth=False)
    for a,b in zip(ribs,ribs[1:]):
        for j in range(len(a[0])-1):
            for k in (0,-1):
                q = [a[k][j],a[k][j+1],b[k][j+1],b[k][j]]
                _h_face(q if k==0 else q[::-1])
        for j in (0,-1):
            for k in range(len(a)-1):
                q = [a[k][j],a[k+1][j],b[k+1][j],b[k][j]]
                _h_face(q if j==-1 else q[::-1])
    for i in (0,-1):
        r = ribs[i]
        for k in range(len(r)-1):
            for j in range(len(r[k])-1):
                q = [r[k][j],r[k][j+1],r[k+1][j+1],r[k+1][j]]
                _h_face(q if i==-1 else q[::-1])
    return p


def _h_roof(h,z):
    for a,b in zip(h['ribs'],h['ribs'][1:]):
        if a[0]<=z<=b[0]:
            slope=(b[1]-a[1])/(b[0]-a[0])
            return a[1]+(z-a[0])*slope, J.unit((0,1,-slope))
    raise ValueError('roof station outside deck')


def _h_wire(parts,path,radius,mat):
    p=J.Part('formed wire')
    K._rail(p,path,radius,mat,seg=T['hull']['tube_segments'])
    parts.append(p)


def _h_clip(poly,axis,limit,sign):
    # Clip a convex (z,y) plate loop against a handhole edge or panel seam.
    out=[]
    for a,b in zip(poly,poly[1:]+poly[:1]):
        u,v=sign*(a[axis]-limit),sign*(b[axis]-limit)
        if u*v<0:
            t=u/(u-v)
            out.append(tuple(i+t*(j-i) for i,j in zip(a,b)))
        if v>=0:
            out.append(b)
    return out


def _h_skirts(parts,side,s,marks):
    seams=s['seams']; base=s['base']; top=s['top']; x=T['gear']['skirt_outer']
    for i,(fore,aft) in enumerate(zip(seams,seams[1:])):
        low=aft+(s['gap']/2 if i<len(seams)-2 else 0)
        high=fore-(s['gap']/2 if i else 0)
        poly=[(high,top),(low,top),(low,base),(high,base)]
        if i==0:
            poly=[(high,s['front_tip']),(s['front_foot'],top),(low,top),(low,base),(s['front_foot'],base)]
        elif i==len(seams)-2:
            poly=[(high,top),(low,top),(low,s['rear_tip']),(high,base)]
        hole=s['hole']; hh,hw,r=hole['half_height'],hole['half_width'],hole['radius']
        cuts=sorted(hole['stations'][i]); slices=[]
        # Horizontal scan strips with radiused slot ends. Only boundary edges
        # of the union get thickness; no doubled, coincident internal walls.
        if cuts:
            breaks=sorted({min(q[1] for q in poly),max(q[1] for q in poly),
                           *(y+k*(hh-r+r*math.sin(theta)) for _,y in cuts for k in (-1,1) for theta in np.linspace(0,math.pi/2,5))})
            def half_at(v,y):
                dy=max(0,abs(v-y)-(hh-r)); return hw-r+math.sqrt(max(0,r*r-dy*dy))
            for ly,uy in zip(breaks,breaks[1:]):
                strip=_h_clip(_h_clip(poly,1,ly,1),1,uy,-1)
                if not strip: continue
                active=[(z,y) for z,y in cuts if abs((ly+uy)/2-y)<hh]
                if not active:
                    slices.append(strip); continue
                # Clip against each straight side of the approximated arc.
                def clip_z(points,offset,gradient,sign):
                    sheared=[(z-gradient*(v-ly),v) for z,v in points]
                    return [(z+gradient*(v-ly),v) for z,v in _h_clip(sheared,0,offset,sign)]
                remain=strip
                for mid,y in active:
                    f,g=half_at(ly,y),half_at(uy,y); k=(g-f)/(uy-ly)
                    slices.append(clip_z(remain,mid-f,-k,-1)); remain=clip_z(remain,mid+f,k,1)
                slices.append(remain)
            # Build plates around real through-holes. Suppress shared faces
            # parallel to the scan strips; only outside and slot walls show.
            plate=J.Part('skirt plate'); xin=side*(x-s['gauge']); xout=side*x
            for q in slices:
                if len(q)<3: continue
                for xx,outsign in ((xout,side),(xin,-side)):
                    # q in z,y; derive orientation rather than trusting clip order.
                    ring=[(xx,yy,zz) for zz,yy in q]
                    if K._signed_area(q)*outsign>0: ring.reverse()
                    plate.face(ring,K.PAINT,False)
            # Edges of the outer outline and capsule loops, wound toward air.
            def walls(q,hole_wall):
                if (K._signed_area(q)*side<0) == hole_wall: q=q[::-1]
                for (z1,y1),(z2,y2) in zip(q,q[1:]+q[:1]):
                    plate.face([(xin,y1,z1),(xin,y2,z2),(xout,y2,z2),(xout,y1,z1)],K.PAINT,False)
            walls(poly,False)
            for mid,y in cuts:
                ys=[v for v in breaks if y-hh-1e-8<=v<=y+hh+1e-8]
                walls([(mid+half_at(v,y),v) for v in ys]+[(mid-half_at(v,y),v) for v in reversed(ys)],True)
            parts.append(plate)
        else: parts.append(K.prism(poly,*sorted((side*(x-s['gauge']),side*x))))
        hinge=s['hinge']; length=hinge['length']; end=s['front_foot'] if i==0 else high
        for f in hinge['fractions']:
            z=low+f*(end-low); cx=side*(x-hinge['inset'])
            parts.append(_turned('skirt hinge',(cx,hinge['y'],z),(0,0,1),[(-length/2,hinge['r']),(length/2,hinge['r'])],'steel',12))
        bolts=s['bolts']; end=s['front_foot'] if i==0 else high
        parts.append(K.bolt_row(marks,(side*x,bolts['y'],low+bolts['margin']),
                               (side*x,bolts['y'],end-bolts['margin']),bolts['count'],
                               bolts['radius'],bolts['height'],normal=(side,0,0)))
        d=s['drops']
        if i>=len(d['bottom']):
            continue
        start=low+d['gap']/2; end-=d['gap']/2
        bot=d['bottom'][i]; depth=d['upper']-bot
        # Straight at the hanger, then curl outward; clip only the lower corners.
        rows=[]
        for f in (0,d['mid_height'],d['clip_start'],1):
            xx=side*np.interp(f,(0,d['mid_height'],1),d['x_rows'])
            inset=d['clip'] if f==1 else 0
            rows.append([(xx,d['upper']-f*depth,z) for z in (start+inset,end-inset)])
        for (a,b),(c,e) in zip(rows,rows[1:]):
            loop=[a,b,e,c]
            parts.append(K.slab(loop if side>0 else loop[::-1],d['gauge'],'skirt_rubber'))
    def ribs(spec):
        return [[(side*x,y,z) for x,y,z in row] for row in spec['ribs']]
    ap=s['apron']; parts.append(K.mudguard(ribs(ap),ap['gauge']))
    inner,outer=ap['ribs'][0]; w=outer[0]-inner[0]; cx,sy,sz=np.mean(ribs(ap)[0],axis=0)
    parts.append(K.cbox((cx,sy,sz),(w,ap['strap_h'],ap['strap_depth']),.003))
    parts.append(K.bolt_row(marks,(cx-w*.43,sy,sz+ap['strap_depth']/2),
                (cx+w*.43,sy,sz+ap['strap_depth']/2),ap['strap_bolts'],ap['bolt_r'],.003,normal=(0,0,1)))
    cheek=s['cheek']; parts.append(K.prism(cheek['profile'],*sorted(side*x for x in cheek['span'])))
    flap=s['mudflap']; parts.append(K.mudguard(ribs(flap),
                                               flap['gauge'],'skirt_rubber'))


def _h_nose(parts,side,n):
    def _h_centre(q):
        return np.array((side*q[0],*q[1:]))
    sz=n['head_size']; c=_h_centre(n['head'])-(0,0,sz[2]/2); parts.append(K.lamp_box(c,sz,'headlight'))
    face=c+(0,0,sz[2]/2+n['mesh_lift']); w,h=n['mesh_span']
    for x in n['mesh_x']:
        _h_wire(parts,[face+(x,-h/2,0),face+(x,h/2,0)],n['wire'],'steel')
    for y in n['mesh_y']:
        _h_wire(parts,[face+(-w/2,y,0),face+(w/2,y,0)],n['wire'],'steel')
    # Station is the visible amber lens, not the cluster/guard pivot.
    c=_h_centre(n['signal'])-(side*n['signal_dx'],0,n['signal_size'][2]/2+n['signal_depth'])
    for dx,zone in ((n['signal_dx'],'amber'),(-n['signal_dx'],'glass_dark')):
        p=c+(side*dx,0,0); sz=n['signal_size']; parts.append(K.cbox(p,sz,.012))
        parts.append(_turned('signal lens',p+(0,0,sz[2]/2),(0,0,1),[(0,n['signal_r']),(n['signal_depth'],n['signal_r'])],zone,18))
    _h_wire(parts,[c+q for q in n['guard_path']],n['guard_radius'],K.PAINT)
    c=_h_centre(n['eye']); parts.append(K.cbox(c-(0,0,n['eye_inset']),n['eye_pad']))
    # Two feet on the inclined bow; the unsupported bight hangs below them.
    span=n['eye_radius']; drop=n['eye_drop']; sweep=n['eye_sweep']
    _h_wire(parts,[c+(i*span,-j*drop,j*sweep) for i,j in ((-1,0),(-1,.66),(-.77,.91),(0,1),(.77,.91),(1,.66),(1,0))],n['eye_bar'],'steel')


def _h_stern(parts,side,h):
    s=h['stern']; zt,yt,zb,yb=h['ribs'][0][:4]; slope=(zt-zb)/(yt-yb)
    n=J.unit((0,slope,-1)); u=np.array((-1.,0.,0.)); v=np.cross(n,u)
    def _h_surface(x,y):
        return np.array((side*x,y,zb+(y-yb)*slope+h['stern_set_in'][0]))
    for dx,w,height,count in s['banks']:
        depth=s['vent_depth']; c=_h_surface(dx,s['vent_y']); face=c+n*(depth-s['forward_overlap'])
        p=J.Part('stern louvres'); p.obox(K.PAINT,face-n*depth/2,(w,height,depth),(u,v,n),bevel=s['vent_bevel'],seg=1)
        p.obox('recess',face,(w*.92,height*.89,s['inset_depth']),(u,v,n))
        theta=math.radians(s['slat_tilt']); cv,sv=math.cos(theta),math.sin(theta)
        for dy in np.linspace(-.38*height,.38*height,count):
            p.obox(K.PAINT,face+v*dy+n*s['slat_section'][1]/2,(w*.90,*s['slat_section']),(u,cv*v+sv*n,cv*n-sv*v))
        parts.append(p)
    path=[np.asarray((side*x,y,z)) for x,y,z in s['cable']]; _h_wire(parts,path,s['cable_r'],'steel')
    for c in (path[0],path[-1]):
        parts.append(K.cbox(c,s['cable_clamp']))
    parts.append(K.tow_hook(_h_surface(*s['eye_xy']),n,s['eye_radius'],s['eye_bar']))
    x,y,z=s['lamp_support']; parts.append(K.cbox((side*x,y,z),s['support_size'],s['support_bevel']))
    x,y,z=s['lamp']; parts.append(K.lamp_box((side*x,y,z+s['lamp_size'][2]/2),s['lamp_size'],'taillight',(0,0,-1)))


def _hull(rg,marks):
    h=T['hull']; parts=[_h_tub(h)]; d=h['driver']; y,n=_h_roof(h,d['z'])
    parts.append(K.hatch((0,y,d['z']),n,size=d['size'],thickness=d['lid']))
    for x,z,yaw in d['blocks']:
        y,_=_h_roof(h,z)
        parts.append(K.periscope((x,y+d['block_lift'],z),d['block_size'],(yaw,0,1)))
    for side in (-1,1):
        sec=[]
        for z,a,b,lo,hi in h['shoulder']:
            sec.append((z,[(side*a,lo),(side*b,lo),(side*b,hi),(side*a,hi)]))
        parts.append(K.loft(sec))
        bins=h['bins']; top=bins['top']; bot=bins['bottom']; x=side*bins['x']
        for a,b in bins['runs']:
            parts.append(K.cbox((x,(top+bot)/2,(a+b)/2),(bins['width'],top-bot,b-a),bins['bevel']))
            parts.append(K.cbox((x,top,(a+b)/2),(bins['width']+bins['lip'],bins['lid'],b-a),bins['lid']/2))
        rb=h['rear_bins']; parts.append(K.cbox((side*rb['x'],rb['y'],rb['z']),rb['size'],rb['bevel']))
        e=h['engine']; a,b=e['z_span']
        for lo,hi in ((a,(a+b-e['division_gap'])/2),((a+b+e['division_gap'])/2,b)):
            x=side*e['x']; w=e['width']; y=e['bed_y']; r=e['rim']; rh=e['rim_h']
            parts.append(K.grille((x,y,(lo+hi)/2),(w,e['height'],hi-lo),e['slats']//2))
            for sg in (-1,1):
                parts.append(K.cbox((x+sg*w/2,y,(lo+hi)/2),(r,rh,hi-lo),.003))
            for z in (lo,hi): parts.append(K.cbox((x,y,z),(w,rh,r),.003))
        arm=h['arm']
        for wheel in rg.road:
            z=wheel[0]; y=wheel[1] if len(wheel)==3 else wheel[1]+rg.track_thickness
            parts.append(K.prism([(z+dz,y+dy) for dz,dy in arm['profile']],*sorted(side*x for x in arm['span']),mat='recess'))
        _h_skirts(parts,side,T['skirt'],marks)
        _h_nose(parts,side,h['nose'])
        _h_stern(parts,side,h)
    return K.combine('hull_shell',parts)





def _skin_y(name,rows,mat='tank_paint'):
    """Closed horizontal station loops, listed bottom to top; shared corresponding corners."""
    # In x,z projection the exterior top winds clockwise (+z cross +x = up).
    q=np.array(rows[-1]); twice=sum(a[2]*b[0]-a[0]*b[2] for a,b in zip(q,np.roll(q,-1,axis=0)))
    p=K.Part(name)
    p.loft(rows,mat,cap0=True,cap1=True,cap_centre=False,smooth=False,flip=twice<0)
    return p


def _rect_y(name,x,z,levels,mat='tank_paint'):
    return _skin_y(name,[[(x+i*w/2,y,z+j*d/2) for i,j in ((-1,-1),(-1,1),(1,1),(1,-1))]
                         for y,w,d in levels],mat)


def _turned(name,base,axis,profile,mat='tank_paint',seg=32,caps=True):
    p=K.Part(name); K._turned(p,base,axis,profile,mat,seg,caps); return p


def _bars(name,paths,radius,mat='tank_paint',seg=8):
    p=K.Part(name)
    for path in paths: K._rail(p,path,radius,mat,seg)
    return p


def _fixed_frame(stations,mat,seg):
    y,_=T['trunnion']; ang=np.arange(seg)*math.tau/seg
    # Four connected annular surfaces; nothing caps or obstructs the opening.
    rows=[[(rx*math.cos(a),y+ry*math.sin(a),z) for a in ang]
          for z,rx,ry,_,_ in stations]
    rows += [[(ix*math.cos(a),y+iy*math.sin(a),z) for a in ang]
             for z,_,_,ix,iy in reversed(stations)]
    p=K.Part('surround'); p.grid(rows,mat,closed_u=True,closed_v=True,smooth=seg>8)
    return p


def _turret_shell(marks):
    t=T['turret']; roof=T['roof']; rows=[]
    for outline,ys in ((t['lower'],t['lower_y']),(t['crease'],t['crease_y']),
                       (t['upper'],[roof]*len(t['upper']))):
        half=[(x,y,z) for (x,z),y in zip(outline,ys)]
        # U-shaped nose slot runs back past the trunnion: the shell must not
        # bridge the gun slot, even where its coplanar top/bottom are capped.
        half=[(half[0][0],half[0][1],t['slot_back']),*half]
        rows.append(half+[(-x,y,z) for x,y,z in reversed(half)])
    parts=[_skin_y('faceted shell',rows),_fixed_frame(t['surround'],'tank_paint',8),
           _fixed_frame(t['socket'],'rubber',32)]
    parts.append(_turned('race',(0,0,T['ring'][1]),(0,1,0),t['race'],'race_contact',56))
    # The box over the race is slightly recessed beneath the module skirts.
    a,b=t['core_y']; za=t['core_aft']; zb=t['core_front']
    parts.append(K.cbox((0,(a+b)/2,(za+zb)/2),(2*t['core_halfwidth'],b-a,zb-za),0.))
    parts.append(K.coax_port(t['coax'],t['coax_radius'],(0,.63,.78)))
    for side in (-1,1):
        for za,zb,bot in t['modules']:
            xi,xm,xt=t['module_x']; ym,yt=t['module_y']
            section=[(side*xi,bot),(side*xm,bot),(side*xm,ym),(side*xt,yt),(side*xi,yt)]
            parts.append(K.loft([(zb,section),(za,section)]))
        for z,width in t['covers']:
            x=side*t['cover_x']; parts.append(K.cbox((x,t['cover_y'],z),(t['cover_t'],t['cover_h'],width),.008))
            for dz in (-1,1):
                parts.append(K.cbox((x,t['tab_y'],z+dz*t['tab_offset']*width),t['tab_size'],.004,'steel'))
        for z in t['loop_z']:
            x=side*t['loop_x']; y=t['loop_y']; dz=t['loop_half']; h=t['loop_h']
            parts.append(_bars('lifting eye',[[(x,y,z-dz),(x,y+h,z-dz),(x,y+h,z+dz),(x,y,z+dz)]],t['loop_r']))
        a=t['upper']; K.weld_seam(marks,(side*a[3][0],roof,a[3][1]),(side*a[4][0],roof,a[4][1]))
    return parts


def _rack():
    t=T['rack']; w=t['half']; a,b=t['rear'],t['front']; d=b-a
    y,hi=t['base'],t['rail']; mid=t['mesh_top']; zr=(a+b)/2
    parts=[]; rails=[]; posts=[]; lower=[]
    for sy,paths in ((y,lower),(hi,rails)):
        for x in (-w,w): paths.append([(x,sy,a),(x,sy,b)])
        paths.append([(-w,sy,a),(w,sy,a)])
    for x in np.linspace(-w,w,t['back_div']+1):
        posts.append([(x,y,a),(x,hi,a)]); lower.append([(x,y,a),(x,y,b)])
    for x in (-w,w):
        for z in np.linspace(a,b,t['side_div']+1)[1:]: posts.append([(x,y,z),(x,hi,z)])
        parts.append(K.cbox((x,(y+mid)/2,zr),(t['skin'],mid-y,d),0.,'rack_mesh'))
    parts.append(K.cbox((0,(y+mid)/2,a),(2*w,mid-y,t['skin']),0.,'rack_mesh'))
    for x in t['cleats']: parts.append(K.cbox((x,y,b),t['cleat_size'],.006))
    return parts+[_bars('top rail',rails,t['cap_r']),_bars('pickets',posts,t['post_r']),
                  _bars('rack bottom',lower,t['horizontal_r'])]


def _roof():
    t=T['roof_fit']; y=T['roof']; parts=[]
    fo,fi,ro=np.array(t['pano_top']); ri=fi+ro-fo
    # Three measured roof corners define the rake of both its top and face.
    # Keep the base level; use the actual front face for the shutter and brow.
    head=[fo,fi,ri,ro]; x,_,z=np.mean(head,axis=0); py=y+t['plinth_h']; hy=py+t['pano_gap']
    foot=[(q[0],hy,q[2]) for q in head]; bearing_r=min(t['plinth_hi'])*.45
    parts.extend([_rect_y('sight plinth',x,z,[(y,*t['plinth_lo']),(py,*t['plinth_hi'])]),
                  _turned('sight bearing',(x,py,z),(0,1,0),[(0,bearing_r),(t['pano_gap'],bearing_r)],'recess'),
                  _skin_y('panoramic housing',[foot,head])])
    front=(fo+fi)/2; right=J.unit((fi[0]-fo[0],0,fi[2]-fo[2])); up=np.array((0.,1.,0.)); outward=np.cross(right,up)
    fittings=K.Part('panoramic optics'); brow=t['head_brow']; lens=t['shutter_size']
    fittings.obox('glass_dark',(front[0],(front[1]+hy)/2,front[2]),lens,(right,up,outward),bevel=.004,seg=1)
    fittings.obox(K.PAINT,front-up*brow[1]/2,brow,(right,up,outward),bevel=.004,seg=1); parts.append(fittings)
    ctr=np.mean(head,axis=0); rail=J.unit(fi-fo)*t['handle_half']; lift=up*t['handle_h']
    parts.append(_bars('sight grab',[[ctr-rail,ctr-rail+lift,ctr+rail+lift,ctr+rail]],t['handle_r']))
    x,ey,ez=t['sight']; z=t['hood_cz']; w,h,d=t['hood_size']; wall=t['hood_t']; foot=t['hood_foot']
    # Projecting brows above a recessed vertical lens, not a solid shiny cube.
    parts.extend([K.cbox((x,y+foot/2,z),(w,foot,d),.008),
                  K.cbox((x,y+h-wall/2,z),(w,wall,d),.006),
                  K.cbox((x,ey,ez-t['hood_window'][2]/2),t['hood_window'],.005,'glass_dark')])
    for s in (-1,1):
        xl=x+s*(w-wall)/2
        parts.append(K.prism([(z-d/2,y),(z+d/2-wall,y),(z+d/2,y+h),(z-d/2+wall,y+h)],xl-wall/2,xl+wall/2))
    parts.append(K.cbox((x,y+h/2,ez-wall),(w-2*wall,h-wall,wall),.008,'recess'))
    x,z=t['cupola']; parts.append(_turned('cupola',(x,y,z),(0,1,0),t['cup_profile'],seg=48))
    for angle in np.arange(t['blocks'])*math.tau/t['blocks']:
        fx,fz=math.sin(angle),math.cos(angle); r=t['block_radius']
        parts.append(K.periscope((x+r*fx,y+t['block_y'],z+r*fz),t['block_size'],(fx,0,fz)))
    x,z=t['hatch']; parts.append(K.hatch((x,y,z),size=t['hatch_size'],thickness=t['hatch_t']))
    for s in (-1,1):
        x,cy,z=t['warning']; x*=s; r=t['warning_r']
        parts.append(K.cbox((x,cy,z),t['warning_foot'],.011)); cy+=t['warning_foot'][1]/2
        parts.append(_turned('receiver',(x,cy,z),(0,1,0),[(r*math.sin(a),r*max(.035,math.cos(a)))
                              for a in np.linspace(0,math.pi/2,6)],'sensor',20))
        x,cy,z=t['aft_fitting']; x*=s; size=t['fitting_size']; parts.append(K.cbox((x,cy,z),size,.008))
        parts.append(K.cbox((x+s*size[0]*.48,cy,z),(size[0]*.1,size[1]*.69,size[2]*.69),.003,'glass_dark'))
        x,cy,z=t['antenna']; x*=s; parts.append(K.antenna_mount((x,cy,z),t['antenna_r'],t['antenna_base_h']))
        start=np.array((x,cy+t['antenna_base_h'],z)); dv=np.array(t['whip_delta'])*(s,1,1)
        parts.append(_turned('whip stub',start,dv,[(0,t['whip_r']),(np.linalg.norm(dv),t['whip_r']*.49)],'recess',8))
    c=np.asarray(t['mast']); mh=t['mast_h']; r=t['mast_r']
    parts.extend([_turned('wind mast',c,(0,1,0),[(0,r*1.55),(mh*.14,r*1.55),(mh*.17,r),(mh,r*.85)]),
                  K.cbox(c+(0,mh+t['mast_cap'][1]/2,0),t['mast_cap'],.008)])
    c=np.asarray(t['pintle']); lift=t['mg_lift']; base=c+(0,lift,0); scale=t['mg_scale']
    mg=K.Part('pintle prop'); half,lo,hi,zrear,zfore=t['mg_fork']; bx,by,bz=t['mg_centre']; w,h,d=t['mg_body']
    K._turned(mg,(0,0,0),(0,1,0),[(0,t['mg_post']),(.45*lo,t['mg_post']),(.55*lo,.7*t['mg_post']),(lo,.7*t['mg_post'])],seg=24)
    mg.box(K.PAINT,-half,half,lo,lo+.12*(hi-lo),zrear,zfore,bevel=.009,seg=1)
    for side in (-1,1): mg.box('steel',side*half-w*.08,side*half+w*.08,lo,hi,zrear,zfore,bevel=.008,seg=1)
    mg.obox('steel',(bx,by,bz),(w,h,d),bevel=.011); mg.obox(K.PAINT,t['mg_box_centre'],t['mg_box'],bevel=.011)
    mg.box('recess',-w*.34,w*.34,by-h*.31,by+h*.31,t['mg_stock_z'],bz,bevel=.008,seg=1)
    K._turned(mg,(0,by,0),(0,0,1),[(bz+d/2,.26*w),(t['mg_jacket_z'],.24*w),
              (t['mg_jacket_z'],t['mg_tip_r']),(t['mg_tip'],t['mg_tip_r'])],'steel',16)
    mg.transform(np.diag([scale,scale,scale,1.])); K.placed(mg,base)
    parts.extend([_turned('pintle foot',c,(0,1,0),[(0,t['mg_post']),(lift,t['mg_post'])]),
                  mg,K.cbox(base+np.array(t['bag_offset'])*scale,np.array(t['bag_size'])*scale,.025,'skirt_rubber')])
    return parts


def _gun():
    y,z0=T['trunnion']; t=T['tube']; parts=[]
    def tube(st,mat,seg=40,caps=True):
        return _turned('tube section',(0,y,0),(0,0,1),[(z,d/2) for z,d in st],mat,seg,caps)
    parts.append(tube(t['root'],'recess'))
    # Slightly uneven circumferential creases, attached to the elevating
    # portion only. End cuffs stay round where they meet the metal sleeves.
    boot=J.Part('bellows'); angles=np.arange(40)*math.tau/40; rows=[]
    for i,(z,d) in enumerate(t['boot']):
        warp=t['wrinkle']*np.sin(3*angles+i*.53)*math.sin(i*math.pi/(len(t['boot'])-1))
        rows.append(np.stack([d*.5*np.cos(angles),y+d*.5*np.sin(angles),z+warp],axis=1))
    boot.loft(rows,'rubber',cap0=True,cap1=True); parts.append(boot)
    for a,b,d0,d1 in t['sleeves']:
        w=t['clamp_width']; rise=t['clamp_rise']
        parts.append(tube([(a,d0),(a+w*.10,d0+rise),(a+w*.86,d0+rise),(a+w,d0),
                           (b-w,d1),(b-w*.90,d1+rise),(b-w*.14,d1+rise),(b,d1)],'tank_paint'))
    mz=t['muzzle'][-1][0]; bottom=mz-t['bore_recess']; bore=t['bore']
    parts.append(tube([*t['muzzle'],(mz,bore),(bottom,bore)],'steel',48,False))
    parts.append(tube([(bottom-t['ref_glass'][2],bore),(bottom,bore)],'recess',48))
    x,cy,z=t['reference']; w,h,d=t['ref_size']; gw,gh,gd=t['ref_glass']
    parts.append(K.cbox((x,cy,z),(w,h,d),.009)); front=z+d/2
    parts.append(K.cbox((x,cy,front),(gw,gh,gd),.002,'glass_dark'))
    for ox in t['dots']:
        parts.append(_turned('reference lens',(x+ox,cy,front+gd/2),(0,0,1),[(0,t['dot_r']),(gd/2,t['dot_r'])],'recess',10))
    # The section table gives z stations along a straight tube before posing.
    # Rotate about the trunnion and compensate the tiny axial foreshortening
    # so that the centre of the front face lands on the measured (y,z).
    gun=K.combine('gun_shell',parts); a=_rest_pitch(); c=math.cos(a); sn=math.sin(a)
    linear=np.array(((1,0,0),(0,c,sn/c),(0,-sn,1.)))
    pivot=np.array((0,y,z0)); M=np.eye(4); M[:3,:3]=linear; M[:3,3]=pivot-linear@pivot
    gun.transform(M); return gun


def _rest_pitch():
    ty,tz=T['trunnion']; t=T['tube']
    return math.atan2(t['muzzle_y']-ty,t['muzzle'][-1][0]-tz)


def _dims():
    ry,rz=T['ring']; ty,tz=T['trunnion']; x,y,z=T['roof_fit']['sight']
    return dict(turretZ=rz,ringY=ry,trunnion=ty-ry,trunnionZ=tz-rz,
                barrel=math.hypot(T['tube']['muzzle'][-1][0]-tz,T['tube']['muzzle_y']-ty),sight=(x,y-ry,z-rz))


def _gear():
    rg=K.RunningGear(**T['gear']); nominal=rg.pitch
    # The jet-style mesh uses equally spaced shoes. Lock their count, then
    # use their actual length for the geometry AND scrolling tile pitch.
    links=round(K.track_path(rg)[1][-1]/nominal)
    for _ in range(10):
        length=K.track_path(rg)[1][-1]; pitch=length/links
        if abs(pitch-rg.pitch)<1e-9: break
        rg.pitch=pitch
    if abs(K.track_path(rg)[1][-1]-links*rg.pitch)>.0001:
        raise ValueError('track spacing did not converge')
    print(f'LINKS {links} pitch={rg.pitch:.7f} nominal={nominal:.3f}')
    return rg


def build():
    J.clear_scene(); mats=K.materials(); dims=_dims(); rg=_gear(); marks=[]
    for name,(col,metal,rough) in T['zones'].items():
        mats.add(name,col,metallic=metal,roughness=rough)
    # Keep the fast shape pass legible without running the atlas painter.
    for name,swatch in [('tank_paint',T['paint']['green']),('rubber',T['tyre_colour'])]:
        c=J.srgb(swatch); mats[name].diffuse_color=c
        mats[name].node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value=c
    root,body,turret,gun=K.tank_nodes('type10',dims)
    # Part.build takes world geometry and reparents it to this bore-aligned
    # frame. TankModel uses the rest quaternion and local +Z for its flash.
    gun.rotation_euler.x=-_rest_pitch(); bpy.context.view_layer.update()
    hull=_hull(rg,marks).build(body,mats,name='hull_shell'); objects=[hull]
    built=K.running_gear(body,rg,mats,tile_links=T['tile_links']); objects.extend(built['objects'])
    # Race, turret cheeks and roof fittings share one mesh. The race seating
    # alone is exempted from turret/hull intersections before atlas collapse.
    upper=K.combine('turret_shell',_turret_shell(marks)+_rack()+_roof()); objects.append(upper.build(turret,mats))
    objects.append(_gun().build(gun,mats)); bpy.context.view_layer.update()
    return root,objects,mats,rg,marks


def _check_aim(root):
    from mathutils.bvhtree import BVHTree
    from mathutils import Matrix
    # BVHs of actual triangles in the same posed world frame. Do not use
    # transformed AABBs: an AABB across the front slot includes its air.
    nodes={o.name:o for o in root.children_recursive}; yaw=nodes['turret']; pitch=nodes['gun']
    fixed_y=yaw.matrix_basis.copy(); fixed_x=pitch.matrix_basis.copy()
    def faces(ob,mask=None):
        me=ob.data; me.calc_loop_triangles(); coords=[ob.matrix_world@v.co for v in me.vertices]
        tris=[tuple(t.vertices) for t in me.loop_triangles if mask is None or mask(t)]
        return BVHTree.FromPolygons(coords,tris,all_triangles=True)
    hull=faces(nodes['hull_shell']); moving=nodes['gun_shell']; shell=nodes['turret_shell']
    try:
        for az in T['check_yaw']:
            yaw.matrix_basis=fixed_y @ Matrix.Rotation(math.radians(az),4,'Z')
            bpy.context.view_layer.update(); turret_tree=faces(shell)
            # Check the turret's exterior too. Its hidden support race on
            # the traverse axis is intentionally seated against the roof.
            contact_slot=next(i for i,m in enumerate(shell.data.materials) if m.name=='race_contact')
            exterior=faces(shell,lambda tri: tri.material_index!=contact_slot)
            hull_overlap=len(hull.overlap(exterior))
            for el in T['elevation']:
                pitch.matrix_basis=fixed_x @ Matrix.Rotation(math.radians(-el),4,'X')
                bpy.context.view_layer.update(); barrel=faces(moving)
                cg=len(barrel.overlap(turret_tree)); ch=len(barrel.overlap(hull))
                print(f'POSE yaw={az:g} elev={el:g} gun_turret={cg} gun_hull={ch} turret_hull={hull_overlap}')
                if cg or ch or hull_overlap: raise ValueError('exterior intersection; see POSE line')
    finally:
        yaw.matrix_basis=fixed_y; pitch.matrix_basis=fixed_x; bpy.context.view_layer.update()


def _contract(root,objects,rg,full):
    nodes={o.name:o for o in root.children_recursive}; dims=_dims(); gun=nodes['gun']; turret=nodes['turret']; body=nodes['body']
    if gun.parent!=turret or turret.parent!=body or body.parent!=root: raise ValueError('pivot hierarchy')
    for node,p in ((turret,(0,dims['ringY'],dims['turretZ'])),(gun,(0,dims['trunnion'],dims['trunnionZ']))):
        if not np.allclose(K.G(node.location),p,atol=1e-5): raise ValueError(f'{node.name}: pivot mismatch')
    stations=[(z,700) for z,r in rg.road]+[(rg.sprocket[0],1400),(rg.idler[0],800)]+[(z,250) for z,_,_ in rg.rollers]
    for side in ('l','r'):
        belt=nodes[f'band_{side}']
        if J.tris_of(belt)>6000 or belt.parent!=body or [m.name for m in belt.data.materials]!=['track_'+side]:
            raise ValueError(f'{side}: track contract')
        for i,(z,budget) in enumerate(sorted(stations,reverse=True)):
            axle=nodes[f'roll_{side}{i}']; mesh=axle.children[0]
            if (axle.parent!=body or len(axle.children)!=1 or abs(K.G(axle.location)[2]-z)>1e-5
                    or J.tris_of(mesh)>budget): raise ValueError(f'{axle.name}: wheel contract ({J.tris_of(mesh)} / {budget})')
            if full and [m.name for m in mesh.data.materials]!=['armor']: raise ValueError(f'{axle.name}: wheel material')
    pts=np.asarray([K.G(o.matrix_world@v.co) for o in objects for v in o.data.vertices]); lo,hi=pts.min(0),pts.max(0)
    muzzle=max(K.G(gun.matrix_world.inverted()@nodes['gun_shell'].matrix_world@v.co)[2] for v in nodes['gun_shell'].data.vertices)
    target=np.array((0.,T['tube']['muzzle_y'],T['tube']['muzzle'][-1][0]))
    tip=K.G(body.matrix_world.inverted() @ gun.matrix_world @ K.B(0,0,muzzle))
    edge=max(x for row in T['skirt']['apron']['ribs'] for x,_,_ in row)
    if not (np.allclose(tip,target,atol=.001) and np.allclose([lo[0],hi[0]],[-edge,edge],atol=.003)):
        raise ValueError(f'fit datums: min={lo}, max={hi}, muzzle={tip}, target={target}')
    if full and {m.name for o in objects for m in o.data.materials}!={'armor','track_l','track_r','headlight','taillight'}:
        raise ValueError('unexpected delivery materials')
    eye=','.join(f'{n:.3f}' for n in dims['sight'])
    print('CONTRACT '+' '.join(f'{k}={dims[k]:.3f}' for k in ('turretZ','ringY','trunnion','trunnionZ','barrel'))+f' sight=({eye})')


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out',type=Path,required=True); ap.add_argument('--render',type=Path)
    ap.add_argument('--quick',action='store_true'); ap.add_argument('--dump',type=Path)
    ap.add_argument('--sheet',type=Path); ap.add_argument('--stage',choices=('shape','full'),default='full')
    args=ap.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
    root,objects,mats,rg,marks=build(); _check_aim(root)
    if args.dump: K.dump(objects,args.dump)
    full=args.stage=='full'
    if full:
        wd=args.out.resolve().parent/'tex-type10'
        K.paint_tracks(mats,rg,wd,T['tile_links'],metal_tint=T['track_colour'])
        scheme=dict(T['paint'],zones=dict.fromkeys(T['zones']))
        K.paint_tank(objects,mats,scheme,2048,wd,density=lambda ob,zone: .70 if ob.name.startswith('disc_') else 1.,
                     marks=marks)
    _contract(root,objects,rg,full); total,_=K.report(root)
    if total>60000: raise ValueError(f'{total} triangles exceeds 60k')
    K.export(root,args.out); print('GLB',args.out)
    renderdir=args.render or (args.sheet.parent/'type10-views' if args.sheet else None)
    if renderdir:
        K.render_check(root,renderdir,elev=T['elevation'],quick=args.quick)
        if args.sheet: K.sheet(renderdir,args.sheet)


if __name__=='__main__': main()
