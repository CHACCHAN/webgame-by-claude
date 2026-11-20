"""Round-five exterior. S is the photo fit; only the game pivot/muzzle contract lives elsewhere.
Hull coordinates are world xyz. Turret stations use absolute y and ring-relative z;
gun fittings are local to the trunnions. Positive x is the vehicle's left."""
import numpy as np

import tank_kit as T
import t14_parts as P


S = dict(
    road_z=(2.548,1.624,.699,-.114,-.936,-1.742,-2.548), road_y=.447, road_r=.358,
    gear=dict(sprocket=(-3.416,.949,.33,12,.44), idler=(3.342,.964,.289,.42),
              rollers=((2.,1.08,.10,.34),(.4,1.08,.10,.34),(-1.4,1.08,.10,.34)),
              # With hub heights fixed, the shoe depth is road_y - road_r at ground contact.
              track_centre=1.40,track_width=.58,pitch=.17,track_thickness=.089,
              wheel_width=.43,tyre_width=.135,tyre_depth=.045,dish_depth=.032,hub_bolts=10,
              horns=2,horn_width=.038,horn_height=.07,sag=0.,pad_share=.71,skirt_outer=1.86),
    arms=dict(housing_x=(1.06,1.26),r=.11,pivot_y=.76,lead=.42,arm_x=(1.06,1.16),
              pivot_h=.14,hub_h=.11,stub_r=.06,sides=16,bolt_count=6,bolt_circle=.076,
              bolt_r=.013,bolt_h=.008,margin=.010,x_limit=1.30),
    # Transverse hull sections (z, keel y, keel half-width, chine y, chine
    # half-width, deck y, deck half-width). The transom is the first cap.
    body=((-4.28,.61,1.275,1.37,1.65,1.86,1.62),(-3.85,.58,1.08,1.37,1.62,1.86,1.62),
          (-2.75,.58,1.08,1.37,1.62,1.86,1.62),(-.50,.58,1.08,1.37,1.62,1.86,1.62),
          (.30,.58,1.08,1.37,1.62,1.82,1.62),(1.30,.58,1.08,1.37,1.62,1.82,1.62),
          (1.90,.58,1.08,1.37,1.62,1.75,1.62)),
    crew_crown=(1.03,1.86),  # half-width and height of the flat hatch-bearing strip
    nose=((1.90,1.86,1.03),(2.74,1.67,.96),(2.95,1.59,1.13),(3.80,1.25,1.04),(4.00,1.16,.91)),
    keel=((1.90,.58),(3.40,.66),(4.00,1.16)),
    outer=((1.90,1.75,1.62),(2.45,1.70,1.62),(2.90,1.66,1.86),(3.19,1.60,1.85),
           (3.55,1.56,1.845),(4.11,1.304,1.817)),
    # The blocks are level across. The taller centre strip retains its own
    # vertical flanks where it stands proud of the inboard edges.
    block_inner_top=((1.90,1.75),(2.45,1.70),(2.90,1.66),(3.19,1.60),(3.55,1.56),(4.11,1.304)),
    band_rear=((-4.28,1.75),(-1.52,1.805)),band_end=2.90,
    block_lip=.038,block_inset=.082,
    block_floor=((1.90,1.37),(3.40,1.017),(4.11,1.017)),block_inner=1.03,
    skirt=dict(seams=(-1.52,-.96,-.40,.16,.72,1.28,1.84,2.40,2.96,3.52,4.11),
               top=((-1.52,1.66),(2.65,1.66),(3.19,1.60),(3.55,1.56),(4.11,1.304)),
               foot=((-1.52,.80),(3.52,.80)),split=.98,front_bottom=1.00,gap=.012,
               hard_t=.055,rubber_t=.030,rubber_setback=.010,bolt_drop=.070,bolt_r=.015,bolt_h=.004),
    cage=dict(x=2.015,posts=(-1.41,-2.436,-3.462,-4.488),rear_edge=((1.07,-4.02),(1.342,-4.578),(1.878,-4.488)),
              bottom=1.07,top=1.878,count=14,rail=(.020,.015),post=.035,turn=.18,mount_x=1.60,ties=(1.40,1.78)),
    lids=dict(rect=((- .88,1.53),(.66,1.60)),size=(.59,.64),circle=(-.10,1.70),r=.275,
              y=1.86,h=.083,scope=(.26,.08,.095),scope_drop=.018),
    hood=((0,1.733,2.60),(.48,.13,.22)),grilles=((.59,1.866,-3.42),(.87,.05,.93),16),
    access=((1.30,1.86,-3.42),(.46,.84),.032),
    # A relieved lower inboard corner leaves the small transom light visible.
    box=dict(c=(1.594,1.60,-4.41),size=(.70,.50,.26),notch=(.30,.12)),
    tail=dict(c=(1.475,1.412,-4.29),r=.035,rim=.008,stand=.021),
    rear_eye=dict(c=(.44,1.12,-4.28),w=.17,h=.24,d=.15,bar=.028),
    nose_eye=((.79,1.02,3.86),(0,0,1),.080,.020),
    cable=(((1.22,1.620,-4.305),(.72,1.620,-4.322),(-.75,1.620,-4.322),(-1.22,1.620,-4.305),
            (-1.14,1.319,-4.330),(-.98,1.067,-4.340),(-.79,0.950,-4.340),(-.63,0.969,-4.340),
            (-.48,1.134,-4.350),(-.44,1.290,-4.350),(-.22,1.436,-4.330),(.22,1.436,-4.330),
            (.44,1.290,-4.350),(.48,1.134,-4.350),(.63,0.969,-4.340),(.79,0.950,-4.340),
            (.98,1.067,-4.340),(1.14,1.319,-4.330),(1.22,1.562,-4.305)),.0225),
    lamp=dict(c=(1.163,1.362,4.070),w=.23,h=.10,d=.13,border=.013,gap=.008,
              lens_t=.007,bevel=.007,count=4,guard=.05,wire=.009),
    handle=(((1.57,1.823,1.03),(1.57,1.883,1.05),(1.57,1.881,1.32),(1.57,1.819,1.34)),.012),
    cheek=((2.00,((0,1.12),(.40,1.12),(.77,1.02),(1.14,.02),(1.11,-.70),(1.01,-1.10),(.88,-1.36),(0,-1.36))),
           (2.19,((0,1.30),(.43,1.30),(.88,1.21),(1.36,.06),(1.31,-.73),(1.19,-1.15),(1.01,-1.36),(0,-1.36))),
           (2.73,((0,.86),(.43,.86),(.76,.75),(1.07,.41),(1.15,-.52),(1.06,-1.12),(.91,-1.36),(0,-1.36)))),
    slot=(.28,.60,1.96,2.53),window=dict(weights=(.50,.297,.203),size=(.30,.18),rim=.008,depth=.03),
    side_panel=dict(edge=3,along=.69,up=.43,size=(.35,.24),rim=.013,depth=.010),
    # Absolute end sections (aft, joint). Grid outer face is 2.5 reliefs aft of its origin.
    bustle=dict(sections=((-2.9225,((0,2.39),(.74,2.39),(.84,2.391),(.84,2.65),(.795,2.703),(0,2.703))),
                          (-1.36,((0,2.39),(.85,2.39),(.98,2.45),(.98,2.67),(.91,2.73),(0,2.73)))),
                skin_z=(-2.90,-2.475,-2.05,-1.39),gap=.024,skin_overlap=.015,skin_d=.18,skin_bottom=2.19,bevel=.027),
    mesh=((0,2.547,-2.9225),(0,0,-1),(1.590,.312),(38,7),.012,.009),
    drum=((0,1.89,-.05),1.04,.28),
    # Each tube has a separate forward cap. Stagger x slightly for a readable overlapping bank.
    aps=dict(mouth_x=(1.17,1.14,1.11,1.08,1.05),mouth_z=(-.55,-.29,-.03,.23,.50),
             y=1.93,dir=(.22,.025,1),r=.09,length=.30),
    commander=dict(c=(-.49,2.73,-1.42),pedestal=.12,r=.30,
                   cyl_z=-1.27,cyl_r=.15,cyl_top=3.37,band_h=.12,band_drop=.08,
                   box_profile=((-1.70,2.83),(-1.41,2.83),(-1.41,3.375),(-1.83,3.375)),box_w=.45,
                   back_box_z=(-2.09,-1.80),back_box_y=(3.18,3.38),back_box_w=.30,back_bevel=.01,
                   stub_z=(-1.10,-.94),stub_y=3.26,stub_r=.025),
    gunner=((- .66,2.815,.46),(.37,.20,.34)),
    decoy=dict(centre=(.94,2.72,.20),normal=(.23,0,1),size=(.32,.22,.30),
               grid=(4,3),spacing=(.066,.061),radius=.026,lip=.004,bevel=.012,segments=12),
    mast=dict(c=(.634,2.73,0.),socket=(.05,.085),stem_r=.0225,height=.58,
              head_r=.035,head_h=.24,count=3,gap=.006),
    whip=dict(c=(.83,2.716,-2.05),socket=(.05,.08),height=.50,r=.008),
    gun=dict(breech=((0,0,-.54),(.45,.30,.96),.036),shield=(.46,.36,.65),front=1.55,
             clip=.08,rear_scale=.73,collar=((.152,.38),(.164,.35),(.164,.135),(.17,.12)),
             tube=dict(stations=((.34,.235),(.40,.235),(1.50,.235),(1.80,.225),(2.10,.220),
                                 (2.40,.210),(2.70,.210),(3.00,.200),(4.40,.200),(4.45,.200),
                                 (4.45,.215),(4.85,.215)),face_d=.190,bore_d=.125,recess=.12,
                       bands=(1.62,2.30,2.95,3.60),band_length=.035,lift=.008,sides=32)),
)

def gear_spec():
    return T.RunningGear(road=tuple((z,S['road_y'],S['road_r']) for z in S['road_z']),**S['gear'])


def _pair(p):
    p.mirror_x()
    return p


def _at(rows,z,col=1):
    return np.interp(z,[row[0] for row in rows],[row[col] for row in rows])


def _hull_skin():
    body=S['body']; nose=S['nose']; outer=S['outer']; keel=S['keel']
    crown_x,crown_y=S['crew_crown']; k=S['skirt']; parts=[]; sections=[]
    # Chine -> skirt seat -> deck edge -> hatch strip. All four are vertices
    # of the same loft: there is no horizontal gap over the return track.
    for z in sorted({r[0] for r in body+S['band_rear']}):
        y0,w0,y1,w1,y2,w2=(_at(body,z,i) for i in range(1,7))
        seat_x=_at(S['band_rear'],z) if z<k['seams'][0] else S['gear']['skirt_outer']-k['hard_t']
        half=[(w0,y0),(w0,y1),(w1,y1),(seat_x,_at(k['top'],z)),(w2,y2),(crown_x,crown_y)]
        sections.append((z,half+[(-x,y) for x,y in reversed(half)]))
    parts.append(T.loft(sections))
    # Four longitudinal strips meeting at the lip, not an overlapping full-width wedge.
    centre=T.Part('centre bow'); prev=None
    for z in sorted({q[0] for q in nose+keel}):
        y=_at(nose,z); x=_at(nose,z,2)
        lo=_at(keel,z); row=[(-x,lo,z),(x,lo,z),(x,y,z),(-x,y,z)]
        if prev is not None:
            for i in range(4):
                j=(i+1)%4; q=[prev[i],prev[j],row[j],row[i]]
                if q[-1]==q[-2]: q.pop()
                centre.face(q,T.PAINT,False)
        else: centre.face(row[::-1],T.PAINT,False)
        prev=row
    parts.append(centre)
    # Continuous upper surface under the top-mounted lamp; the inboard wall
    # follows the central plate until the two projecting blocks separate.
    z_join=outer[0][0]
    stations=sorted({q[0] for q in outer+nose+S['block_floor']+S['block_inner_top']+k['top'] if z_join<=q[0]<=outer[-1][0]})
    p=T.Part('outer bow'); prev=None
    for z in stations:
        top=_at(outer,z); xo=_at(outer,z,2); lo=_at(S['block_floor'],z)
        inn=_at(nose,z,2) if z<=nose[-1][0] else np.interp(z,(nose[-1][0],outer[-1][0]),(nose[-1][2],S['block_inner']))
        inset=S['block_inset'] if z<outer[-1][0] else 0
        # The skirt seat remains at x=1.805 as the deck edge sweeps out to
        # meet it. At the bow the outer block is itself the roof of the track.
        if z<=S['band_end']:
            seat=(S['gear']['skirt_outer']-k['hard_t'],_at(k['top'],z),z)
        else:
            seat=(xo-inset,top-S['block_lip'],z)
        inner_y=_at(S['block_inner_top'],z)
        row=[(inn,lo,z),(max(xo-inset,seat[0]-inset),lo,z),seat,(xo,top,z),(inn,inner_y,z)]
        if prev is None: p.face(row[::-1],T.PAINT,False)
        else:
            for i in range(len(row)):
                j=(i+1)%len(row); p.face([prev[i],prev[j],row[j],row[i]],T.PAINT,False)
        prev=row
    p.face(prev,T.PAINT,False); parts.append(_pair(p)); return parts


def _skirts(rg,marks):
    k=S['skirt']; p=[]; x=rg.skirt_outer; split=k['split']
    for left,right in zip(k['seams'],k['seams'][1:]):
        a,b=left+k['gap']/2,right-k['gap']/2
        top=lambda z:_at(k['top'],z); foot=lambda z:_at(k['foot'],z)
        # Include intermediate slope changes without adding a panel seam.
        zs=sorted({a,b,*[z for z,y in k['top'] if a<z<b],*[z for z,_,_ in S['outer'] if S['band_end']<=z and a<z<b]})
        has_rubber=right<=k['foot'][-1][0]
        bottom=split if has_rubber else k['front_bottom']
        panels=[T.prism([(a,bottom),(b,bottom)]+[(z,top(z)) for z in reversed(zs)],x-k['hard_t'],x)]
        if has_rubber:
            xr=x-k['rubber_setback']
            panels.append(T.prism([(a,foot(a)),(b,foot(b)),(b,split),(a,split)],xr-k['rubber_t'],xr,'rubber'))
        def taper(z): return _at(S['outer'],z,2)-x if z>S['band_end'] else 0.
        for panel in panels:
            for vert in panel.bm.verts:
                z=T.G(vert.co)[2]; vert.co.x+=taper(z)
            p.append(panel)
        for sign in (-1,1):
            # Joint fasteners remain atlas relief rather than extra geometry.
            z=(a+b)/2; c=(sign*(x+taper(z)),top(z)-k['bolt_drop'],z)
            marks.append(dict(kind='bolt',a=c,b=c,radius=k['bolt_r'],height=k['bolt_h']))
    return _pair(T.combine('skirts',p))


def _lamp():
    k=S['lamp']; c=np.array(k['c']); w,h,d,t=k['w'],k['h'],k['d'],k['lens_t']; rim=k['border']
    # Shear the casing along the measured block slope; the LEDs stay upright.
    outer=S['outer']; rise=_at(outer,c[2]-d)-_at(outer,c[2]); dx=w/k['count']
    case=T.cbox((0,0,-d/2),(w+2*rim,h+2*rim,d),k['bevel'])
    xf=np.eye(4); xf[1,2]=-rise/d; case.transform(xf)
    lights=[T.placed(case,c-(0,0,t/2))]
    for i in range(k['count']):
        lights.append(T.cbox(c+((i+.5)*dx-w/2,0,0),(dx-k['gap'],h,t),mat='headlight'))
    rx=w/2+rim; ry=h/2+rim; front=t+k['guard']+k['wire']
    lights.append(P.rod([c+q for q in ((-rx,rise/2-ry,-d/2),(-rx,ry,front),(rx,ry,front),(rx,rise/2-ry,-d/2))],k['wire'],'steel'))
    return _pair(T.combine('guarded lamps',lights))


def suspension(rg):
    """Mirrored static hardware, still separate Parts for the clearance audit."""
    k=S['arms']; checked=[]; stubs=[]; x0,x1=k['housing_x']; cx=rg.track_centre-rg.wheel_width/2
    for z,y,_ in rg.road:
        zz=z+k['lead']; yy=k['pivot_y']; r=k['r']; n=k['sides']
        housing=T.Part('pivot housing'); housing.revolve(T.PAINT,[(r,x1),(r,x0)],(0,yy,zz),
                                                         seg=n,cap0=True,cap1=True)
        for i in range(k['bolt_count']):
            a=i*2*np.pi/k['bolt_count']; orbit=k['bolt_circle']; br=k['bolt_r']
            housing.revolve(T.PAINT,[(br,x1+k['bolt_h']),(br,x1)],(0,yy+orbit*np.cos(a),zz+orbit*np.sin(a)),
                            seg=6,cap0=True,smooth=False)
        h0=k['hub_h']/2; h1=k['pivot_h']/2
        arm=T.prism([(z,y-h0),(zz,yy-h1),(zz,yy+h1),(z,y+h0)],*k['arm_x'])
        checked.extend((_pair(housing),_pair(arm)))
        stub=T.Part('static axle'); sr=k['stub_r']
        stub.revolve(T.PAINT,[(sr,cx),(sr,x0)],(0,y,z),seg=n,cap0=True,cap1=True)
        stubs.append(_pair(stub))
    return T.combine('fixed pivots and arms',checked),T.combine('axle stubs',stubs)


def hull(rg,marks,hardware):
    parts=_hull_skin()+list(hardware)+[_skirts(rg,marks),_pair(P.slat_cage(**S['cage'])),_lamp(),P.rod(*S['cable']),
                        _pair(P.rod(*S['handle'])),_pair(T.tow_hook(*S['nose_eye'])),T.periscope(*S['hood'])]
    k=S['lids']; y=k['y']; h=k['h']
    for x,z in (*k['rect'],k['circle']):
        circ=(x,z)==k['circle']; dim={'radius':k['r']} if circ else {'size':k['size']}
        parts.append(T.hatch((x,y,z),thickness=h,**dim))
        dz=k['r'] if circ else k['size'][1]/2
        parts.append(T.periscope((x,y+h-k['scope_drop'],z+dz),k['scope']))
    c,size,n=S['grilles']; parts.append(_pair(T.grille(c,size,n)))
    c,size,t=S['access']; parts.append(_pair(T.hatch(c,size=size,thickness=t)))
    k=S['box']; x,y,z=k['c']; w,h,d=k['size']; nw,nh=k['notch']; l=x-w/2; r=x+w/2; b=y-h/2; t=y+h/2
    profile=[(l+nw,b),(r,b),(r,t),(l,t),(l,b+nh),(l+nw,b+nh)]
    parts.append(_pair(T.loft([(zz,profile) for zz in (z-d/2,z+d/2)])))
    k=S['tail']; r=k['r']; stand=k['stand']; lamp=T.Part('tail lens')
    lamp.revolve('steel',[(r,0),(r+k['rim'],0),(r+k['rim'],-stand)],k['c'],axis=(0,0,-1),
                 seg=16,cap0='taillight',cap1=True); parts.append(_pair(lamp))
    k=S['rear_eye']; c=np.array(k['c']); w=k['w']/2; h=k['h']/2; d=k['d']; r=k['bar']
    parts.append(_pair(P.rod([c+q for q in ((-w+r,h-r,0),(-w+r,h-r,-d/2),(-w+r,0,-d+r),
                                             (0,-h+r,-d+r),(w-r,-h+r,-d/2),(w-r,0,0))],r,'recess')))
    return T.combine('hull_shell',parts)


def _panorama():
    k=S['commander']; x,y,z=k['c']; seat=y+k['pedestal']
    foot=T.Part('sight drum'); foot.revolve(T.PAINT,[(k['r'],seat-y),(k['r'],0)],(x,y,z),
                                            axis=(0,1,0),seg=32,cap0=True,cap1=True)
    # Material boundary on the actual cylindrical wall, not offset glazing.
    top=k['cyl_top']; hi=top-k['band_drop']; n=32; angles=np.arange(n)*2*np.pi/n
    rings=[[(x+k['cyl_r']*np.cos(a),level,k['cyl_z']-k['cyl_r']*np.sin(a)) for a in angles]
           for level in (seat,hi-k['band_h'],hi,top)]
    cyl=T.Part('forward optic'); cyl.loft(rings,T.PAINT,cap0=True,cap1=True,
        mats=lambda i,j: 'glass_dark' if j==1 and i>=n//2 else T.PAINT)
    w=k['box_w']; box=T.prism(k['box_profile'],x-w/2,x+w/2)
    a,b=k['back_box_z']; lo,hi=k['back_box_y']
    back=T.cbox((x,(lo+hi)/2,(a+b)/2),(k['back_box_w'],hi-lo,b-a),k['back_bevel'])
    # A short root seats the exposed front stub against the curved optic wall.
    a,b=k['stub_z']; r=k['stub_r']; root=k['cyl_z']+np.sqrt(k['cyl_r']**2-r**2)
    stub=T.Part('optic stub'); stub.revolve('steel',[(r,b),(r,a),(r,root)],(x,k['stub_y'],0),
                                          axis=(0,0,1),seg=16,cap0=True,cap1=True)
    return T.combine('panoramic sight',[foot,cyl,box,back,stub])


def turret(dims):
    rows=S['cheek']; parts=[P.notched_shroud(rows,S['slot'],S['window']),_panorama(),
                            P.mesh_panel(*S['mesh']),T.periscope(*S['gunner']),_pair(P.port_box(**S['decoy']))]
    # Upper 3-4 is split on C3-R4. Anchor the radar to that triangle's actual plane.
    k=S['side_panel']; i=k['edge']; t=k['along']; h=k['up']
    def at(level,j):
        y,loop=rows[level]; x,z=loop[j]; return np.array((x,y,z))
    a,b,c=at(1,i),at(1,i+1),at(2,i+1)
    normal=np.cross(b-a,c-a); pos=a+(b-a)*(t-h)+(c-a)*h
    parts.append(_pair(P.face_panel(pos,normal,k['size'],k['rim'],k['depth'])))
    k=S['bustle']; sections=k['sections']
    parts.append(T.loft([(z,list(half)+[(-x,y) for x,y in reversed(half[1:-1])]) for z,half in sections]))
    # Skin panels run along the tapered side. Fit both ends to the sidewall
    # rather than floating the aft box off the narrower rear section.
    skin_stations=[(z,half[2][0],half[-1][1]) for z,half in sections]
    for a,b in zip(k['skin_z'],k['skin_z'][1:]):
        rings=[]
        for z in (a+k['gap']/2,b-k['gap']/2):
            x=_at(skin_stations,z)-k['skin_overlap']; top=_at(skin_stations,z,2)
            w=k['skin_d']; lo=k['skin_bottom']; f=k['bevel']
            rings.append((z,[(x,lo),(x+w-f,lo),(x+w,lo+f),(x+w,top-f),(x+w-f,top),(x,top)]))
        parts.append(_pair(T.loft(rings)))
    centre,r,h=S['drum']; drum=T.Part('traverse drum')
    drum.revolve('recess',[(r,h/2),(r,-h/2)],centre,axis=(0,1,0),seg=48,cap0=True,cap1=True); parts.append(drum)
    k=S['aps']; axis=np.array(k['dir']); axis=axis/np.linalg.norm(axis); tubes=[]
    for x,z in zip(k['mouth_x'],k['mouth_z']):
        mouth=np.array((x,k['y'],z)); length=k['length']
        # Kit lips are 1.09 times their body radius; r is measured over the cap.
        tubes.append(T.smoke_dischargers(1,mouth-axis*length,axis,radius=k['r']/1.09,length=length))
    parts.append(_pair(T.combine('cap bank',tubes)))
    k=S['mast']; c=np.array(k['c']); top=c+(0,k['height'],0); base=top-(0,k['head_h'],0)
    parts.extend([T.antenna_mount(c,*k['socket']),P.rod([c,top],k['stem_r'])]); step=k['head_h']/k['count']
    for i in range(k['count']):
        parts.append(P.rod([base+(0,i*step+k['gap']/2,0),base+(0,(i+1)*step,0)],k['head_r']))
    k=S['whip']; c=np.array(k['c']); parts.append(_pair(T.combine('aerial',[
        T.antenna_mount(c,*k['socket']),P.rod([c,c+(0,k['height'],0)],k['r'],'steel')])))
    return T.placed(T.combine('turret_shell',parts),(0,0,dims['turretZ']))


def gun(dims):
    k=S['gun']; w,h,d=k['shield']; x=w/2; y=h/2; t=k['clip']; front=k['front']-dims['trunnionZ']
    loop=[(-x,-y+t),(-x+t,-y),(x-t,-y),(x,-y+t),(x,y-t),(x-t,y),(-x+t,y),(-x,y-t)]
    shield=T.loft([(front-d,[(a*k['rear_scale'],b*k['rear_scale']) for a,b in loop]),(front,loop)])
    shoulder=T.Part('collar'); shoulder.revolve(T.PAINT,k['collar'],(0,0,0),axis=(0,0,1),seg=32,cap0=True,cap1=True)
    p=T.combine('gun_shell',[T.cbox(*k['breech']),shield,shoulder,P.sleeved_tube(length=dims['barrel'],**k['tube'])])
    return T.placed(p,(0,dims['ringY']+dims['trunnion'],dims['turretZ']+dims['trunnionZ']))
