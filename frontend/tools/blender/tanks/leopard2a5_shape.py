"""Editable photo-fit table. Everything is in metres in the level, assembled hull
frame unless explicitly marked local. +X left, +Y up, +Z bow. No bpy objects
for individual fittings: the three builders return finished, unbuilt Parts.
"""
import math
import numpy as np
import tank_kit as T
import leopard2a5_parts as P

S = {
    # Measured/published silhouette locks. X widths and the sight height are provisional.
    'axis': dict(traverse_z=.40, ring_y=1.70, elevation_z=1.48, bore_y=2.12,
                 muzzle_z=5.69, limits=(-9.,20.), traverse_check=(0.,30.), recoil=.45),
    'gear': dict(track_centre=1.45, track_width=.635, track_thickness=.050, pitch=.185,
                 road_z=(2.46,1.57,.77,-.01,-.85,-1.67,-2.46), hub_y=(.40,.42), radius=.35,
                 wheel_width=.46, tyre_width=.14, tyre_depth=.041, dish_depth=.034, hub_bolts=6,
                 idler=(3.15,.93,.33,.45), sprocket=(-3.26,.79,.35,11,.46),
                 rollers=((2.05,1.14,.105),(.69,1.13,.105),(-.79,1.105,.105),(-2.16,1.085,.105)),
                 sag=.024, horns=2, horn_width=.037, horn_height=.067, pad_share=.72, skirt_outer=1.88),
    # Tub stations (z, keel y, deck y, bottom half-width, shoulder half-width).
    # Tiny truncated end edges avoid a zero-area cap at the prow.
    'tub': [(-3.98,1.64,1.70,.99,1.08),(-3.90,.77,1.70,.95,1.09),
            (-3.55,.50,1.69,.96,1.09),(-1.20,.515,1.70,.97,1.10),
            (1.25,.533,1.70,.98,1.10),(1.48,.535,1.66,.98,1.10),
            (2.88,.54,1.334,.95,1.10),(3.72,1.125,1.135,.98,1.07)],
    'bilge': .075,
    'well': dict(aft=-.30,front=.91,width=1.32,floor=1.43,rim=.025),
    'deck_seam': ((1.78,1.70,-3.79),(1.78,1.70,1.22)),
    # Sponson shelves (z, underside, roof, outer half-width); inner edge laps the tub.
    'shelf': [(-3.98,1.17,1.70,1.70),(-3.83,1.20,1.70,1.80),(-1.20,1.30,1.70,1.81),
              (1.25,1.30,1.70,1.81),(2.65,1.32,1.42,1.80),(3.19,1.30,1.325,1.77)],
    'shelf_inner':1.055,
    'skirt': dict(heavy=(3.28,2.60,1.92,1.25), light=(1.25,.34,-.55,-1.43,-2.25,-3.05,-3.66),
                  rail_y=1.35, heavy_low=.85, light_low=.92, tail_low=1.00, tail_top=1.20,
                  heavy_depth=.11, light_depth=.043, gap=.016, strip=.048, bevel_run=.28,
                  bevel_rise=.22, steps_z=(1.15,-.43,-2.07),step_x=1.823,step_low=.72,
                  step_span=.27,step_bar=.018,rail_r=.021, bolt=.020, bolt_inset=.09),
    'fender': dict(inner=1.105, outer=1.858, ribs=((2.76,1.412,1.41),(3.25,1.31,1.29),
                   (3.51,1.25,1.16),(3.55,1.10,.95)),thickness=.019,
                   rear=(1.45,.85,-3.82),flap=(.625,.78,.035)),
    'driver': dict(centre=(-.62,1.543,2.03), lid=(.69,.70), thick=.037, rail_x=.365,
                   rail_size=(.033,.043,.89),window_size=(.154,.096,.115),
                   windows=((- .22,.28),(0,.33),(.22,.28))), # hatch-local x,z
    'bow': dict(lens=(.98,1.28,3.50), lamp_r=.094,lamp_depth=.18,guard=(.26,.255,.215),rod=.012,
                eye=(.83,1.12,3.64),eye_r=.072, eye_bar=.022,marker=(1.69,1.29,3.28),marker_size=(.076,.046,.068),
                shoe_x=(0.,.39,-.39),shoe_z=3.17,shoe_size=(.345,.046,.215),pad_size=(.135,.028,.145)),
    'deck': dict(grilles=((.84,1.708,-3.37,1.40,.031,.72,12),(.87,1.706,-2.47,1.28,.028,.73,11)),
                 lids=((1.57,1.718,-1.18),(1.57,1.718,-.31),(1.57,1.718,.56)),lid_size=(.39,.032,.82),latch=(0,.019,.31),latch_size=(.09,.024,.042),
                 tool_x=1.71,tool_y=1.75,tool_z=(-3.48,-1.85), tool_r=.019),
    'stern': dict(grille=(.847,1.439,-3.983),size=(1.64,.030,.448),slats=8,
                  transom=((-3.972,1.01),(-3.91,.93),(-3.81,.93),(-3.81,1.27),(-3.972,1.27)),half=1.70,
                  lamp=(1.51,1.115,-3.979),case=(.30,.14,.081),r=.049,
                  eye=(.78,.93,-3.907),eye_r=.084,eye_bar=.023,camera=(.34,1.14,-3.959),
                  camera_size=(.13,.096,.11),cable_top=(1.56,1.61,-4.015), cable_low=(.83,.985,-3.984),cable_r=.019),
    # Solid rear turret stations (z, lower y, upper y, lower and upper half-width).
    # Front has two side walls and a thin roof bridge, NOT a wall through the gun.
    'bustle': [(-2.06,2.00,2.49,1.29,1.34),(-1.83,1.97,2.50,1.38,1.45),
               (-.68,1.79,2.54,1.46,1.50),(-.18,1.78,2.54,1.46,1.50)],
    'crown': dict(back=-.181,front=1.31,y=2.54,thick=.044,width=2.62,slot=.398),
    'race': dict(low=1.69,high=1.79,r=1.065,inner=.83),
    # Cheek tiers bottom/chine/chine highlight/top (x,z); last point closes at the slot.
    'cheeks': [(1.79,[(.43,2.28),(1.44,1.39),(1.53,.36),(1.46,-.17),(.43,-.17)]),
               (2.11,[(.40,2.99),(1.58,1.82),(1.65,.40),(1.55,-.17),(.40,-.17)]),
               (2.134,[(.40,2.98),(1.58,1.81),(1.65,.40),(1.55,-.17),(.40,-.17)]),
               (2.53,[(.40,2.32),(1.42,1.42),(1.52,.40),(1.50,-.17),(.40,-.17)])],
    'side_module':[(1.82,[(1.39,.38),(1.53,.38),(1.49,-.69),(1.39,-.69)]),
                   (2.12,[(1.39,.39),(1.647,.39),(1.57,-.70),(1.39,-.70)]),
                   (2.50,[(1.39,.39),(1.522,.39),(1.505,-.68),(1.39,-.68)])],
    'basket':dict(rear=-2.92,front=-1.98,top=2.17,low=1.82,width=2.72,bar=.017,pickets=13),
    'roof':dict(commander=(-.69,2.544,-.18),loader=(.69,2.544,-.20),hatch_r=.32,lid_h=.042,
                ring_r=.375,ring_h=.035,scope_r=.402,scope_size=(.127,.075,.10),scope_n=8,
                peri=(-.43,2.539,-.75),peri_top=3.03,peri_r=.19,
                window=(-.86,2.669,1.23),emes_size=(.50,.28,.54),door=(.418,.207,.018),door_open_deg=0.,
                fan=(.43,2.53,-.91),fan_r=.156,fan_h=.065,
                aerial=(1.16,2.502,-1.58),aerial_r=.062,aerial_h=.13,stub=.28,
                sensor=(.88,2.518,-1.23),sensor_h=.20, sensor_r=.018,
                eye=(1.15,2.532,1.28),eye_r=.063,eye_bar=.014),
    'bins': dict(centre=(1.46,2.23,-1.43),size=(.233,.38,1.04),lid_h=.030),
    'smoke':dict(banks=((1.555,2.095,-.63),(1.59,2.274,-1.34)),count=4,spacing=.139,
                 direction=(.66,.78,.37),radius=.046,length=.235, mount=(.14,.10,.57)),
    'cheek_rail':dict(path=((1.55,2.22,1.73),(1.62,2.23,1.69),(1.666,2.23,.54),(1.61,2.22,.50)),radius=.013),
    # Cosmetic moving shell: z axial stations, widths/heights. The breech is
    # just a blind animation plug; no internal mechanism or operating geometry.
    'cover':dict(profile=((1.38,1.976),(1.65,1.943),(2.36,1.952),(2.99,2.052),(3.01,2.174),
                          (2.34,2.388),(1.63,2.335),(1.38,2.268)), half=.362,
                 plug_z=.41,plug_end=1.60,plug_size=(.33,.17),round=.032),
    'tube':dict(profile=((1.46,.118),(2.91,.118),(2.94,.141),(3.045,.141),(3.052,.116),
                         (3.22,.113),(3.227,.122),(3.25,.122),(3.304,.147),(3.335,.150),
                         (3.864,.150),(3.902,.144),(3.930,.109),(4.43,.105),(4.438,.112),
                         (4.471,.112),(4.478,.103),(4.992,.095),(5.003,.103),(5.038,.103),
                         (5.046,.093),(5.47,.083),(5.486,.098)),
                muzzle_r=.098,bore_r=.060,recess=.12,segments=40,
                sensor=(0,.131,5.561),sensor_size=(.080,.095,.144)), # sensor y relative to bore
    # Projected artwork centre and size in surface metres; no decal meshes.
    'insignia':dict(side=(.77,2.275,.26),rear=(.0,1.093,.169),number=(.045,2.30,.216)),
}


def dims():
    a=S['axis']; w=S['roof']['window']
    return dict(turretZ=a['traverse_z'],ringY=a['ring_y'],trunnion=a['bore_y']-a['ring_y'],
                trunnionZ=a['elevation_z']-a['traverse_z'],barrel=a['muzzle_z']-a['elevation_z'],
                sight=(w[0],w[1]-a['ring_y'],w[2]-a['traverse_z']))


def running_spec():
    kw=S['gear'].copy(); zs=kw.pop('road_z'); y=np.linspace(*kw.pop('hub_y'),len(zs)); r=kw.pop('radius')
    return T.RunningGear(road=tuple((z,float(h),r) for z,h in zip(zs,y)),**kw)


def _signed(point,s):
    x,y,z=point; return (s*x,y,z)


def _shell():
    sections=[]
    t=np.asarray(S['tub']); well=S['well']; end=(well['aft'],well['front']); rim=well['rim']; half=well['width']/2
    for z in sorted(set(t[:,0])|{end[0]-rim,*end,end[1]+rim}):
        lo,hi,a,b=(np.interp(z,t[:,0],t[:,j]) for j in range(1,5))
        shelf=well['floor'] if end[0]<=z<=end[1] else hi
        cut=min(S['bilge'],(hi-lo)*.4)
        sections.append((z,[(-a,lo),(a,lo),(b,lo+cut),(b,hi),(half+rim,hi),(half,shelf),(-half,shelf),(-half-rim,hi),(-b,hi),(-b,lo+cut)]))
    p=T.loft(sections); a=S['shelf_inner']
    q=T.loft([(z,[(a,lo),(b,lo),(b,hi),(a,hi)]) for z,lo,hi,b in S['shelf']]); q.mirror_x()
    return [p,q]


def _skirts(rg,marks):
    k=S['skirt']; parts=[]; x=rg.skirt_outer; h=k['rail_y']; gap=k['gap']/2
    for heavy,seq in ((True,k['heavy']),(False,k['light'])):
        depth=k['heavy_depth' if heavy else 'light_depth']; strip=0 if heavy else k['strip']
        for i,(b,a) in enumerate(zip(seq,seq[1:])):
            a+=gap; b-=gap; last=not heavy and i==len(seq)-2
            low=k['heavy_low' if heavy else 'light_low']; la=k['tail_low'] if last else low
            ha=k['tail_top'] if last else h; hb=h
            # Stepped heavy front bays and a rising tail cut, not identical tiles.
            prof=[(a,la+strip),(b,low+strip),(b,hb),(a,ha)]
            if heavy and not i: prof[1:2]=[(b-k['bevel_run'],low),(b,low+k['bevel_rise'])]
            leaf=T.prism(prof,x-depth,x); leaf.mirror_x(); parts.append(leaf)
            # Sloped shoulder bridges the standing hinge to the outer deck edge.
            # Stop at the fender fold where the rail is higher than the deck.
            deck=np.asarray(S['shelf']); aa=max(a,deck[0,0]); bb=min(b,deck[-1,0]);
            if bb>aa:
                ribs=[]
                for zz,rail in ((aa,ha),(bb,hb)):
                    deck_y=np.interp(zz,deck[:,0],deck[:,2]); deck_x=np.interp(zz,deck[:,0],deck[:,3])
                    ribs.append(((deck_x,deck_y,zz),(x-depth*.52,min(rail,deck_y),zz)))
                shoulder=T.mudguard(ribs,min(depth*.42,gap*2)); shoulder.mirror_x(); parts.append(shoulder)
            if strip:
                lip=T.prism([(a,la),(b,low),(b,low+strip),(a,la+strip)],x-depth*.9,x-depth*.1,'rubber')
                lip.mirror_x(); parts.append(lip)
            for s in (-1,1):
                parts.append(P.piping([(s*(x-depth/2),ha,a),(s*(x-depth/2),hb,b)],k['rail_r']))
                for f in ((.17,.85) if heavy else (.79,)):
                    parts.append(T.bolt_row(marks,(s*x,la+(ha-la)*f,a+k['bolt_inset']),(s*x,low+(h-low)*f,b-k['bolt_inset']),
                                            3,radius=k['bolt'],normal=(s,0,0)))
    for z in k['steps_z']:
        half=k['step_span']/2; top=k['light_low']; bot=k['step_low']; x=k['step_x']
        q=P.piping([(x,top,z-half),(x,bot,z-half*.7),(x,bot,z+half*.7),(x,top,z+half)],k['step_bar'],'steel')
        q.mirror_x(); parts.append(q)
    return parts


def hull(rg,marks):
    parts=_shell()+_skirts(rg,marks); f=S['fender']; b=S['bow']; r=S['stern']; d=S['deck']
    parts.append(T.prism(r['transom'],-r['half'],r['half']))
    for s in (-1,1):
        parts.append(T.mudguard([[(s*f['inner'],yi,z),(s*f['outer'],yo,z)] for z,yi,yo in f['ribs']],f['thickness']))
        parts.append(T.cbox(_signed(f['rear'],s),f['flap'],.009,'rubber'))
        x,y,z=_signed(b['lens'],s); w,h,l=b['guard']; rod=b['rod']
        parts.append(P.bezel((x,y,z),(0,0,1),b['lamp_r'],b['lamp_depth'],'headlight'))
        for zz in (z-l*.8,z+rod):
            parts.append(P.piping([(x-w/2,y-h/2,zz),(x-w/2,y+h/2,zz),(x+w/2,y+h/2,zz),(x+w/2,y-h/2,zz)],rod))
        for xx in (x-w/2,x+w/2): parts.append(P.piping([(xx,y+h/2,z-l*.8),(xx,y+h/2,z+rod)],rod))
        parts.append(T.cbox(_signed(b['marker'],s),b['marker_size'],.01,'steel'))
        for t,axis in ((b,1),(r,-1)):
            parts.append(T.tow_hook(_signed(t['eye'],s),(0,0,axis),t['eye_r'],t['eye_bar']))
        for x,y,z,w,h,l,n in d['grilles']: parts.append(T.grille((s*x,y,z),(w,h,l),n))
        for c in d['lids']:
            parts.append(T.cbox(_signed(c,s),d['lid_size'],.012)); x,y,z=_signed(c,s)
            parts.append(T.cbox(np.array((x,y,z))+d['latch'],d['latch_size'],.005,'steel'))
        parts.append(P.piping([(s*d['tool_x'],d['tool_y'],z) for z in d['tool_z']],d['tool_r'],'steel'))
        T.weld_seam(marks,*[_signed(pt,s) for pt in S['deck_seam']])
        parts.append(P.face_grille(_signed(r['grille'],s),r['size'],r['slats'],-1))
        x,y,z=_signed(r['lamp'],s); w,h,l=r['case']
        parts.append(T.cbox((x,y,z+l/2),r['case'],.014,'recess'))
        for off in (-.23,.23): parts.append(P.bezel((x+w*off,y,z-.009),(0,0,-1),r['r'],l/2,'taillight'))
        parts.append(P.piping([(x-w*.57,y-h*.55,z),(x-w*.57,y+h*.66,z),(x+w*.57,y+h*.66,z),(x+w*.57,y-h*.55,z)],rod))
        a=_signed(r['cable_top'],s); c=_signed(r['cable_low'],-s)
        parts.append(P.piping([a,(0,(a[1]+c[1])/2,a[2]-s*rod),c],r['cable_r'],'steel'))
    parts.append(T.periscope(r['camera'],r['camera_size'],(0,0,-1)))
    # Rest frame on the upper glacis, Z rising toward the stern.
    tub=S['tub']; grad=(tub[-1][2]-tub[-3][2])/(tub[-1][0]-tub[-3][0]); norm=np.array((0,1,-grad)); norm/=np.linalg.norm(norm)
    forward=np.cross((1,0,0),norm); axes=((1,0,0),norm,forward); g=S['driver']; c=np.array(g['centre'])
    parts.append(T.hatch(c,norm,size=g['lid'],thickness=g['thick']))
    rails=T.Part('slide rails')
    for s in (-1,1): rails.obox('steel',c+(s*g['rail_x'],0,0),g['rail_size'],axes,bevel=.005)
    parts.append(rails)
    for dx,dz in g['windows']:
        parts.append(T.periscope(c+(dx,0,0)+dz*forward+norm*(g['thick']+.032),g['window_size'],forward))
    shoes=T.Part('stowed pads'); z=b['shoe_z']; y=tub[-1][2]+(z-tub[-1][0])*grad
    for x in b['shoe_x']:
        c=np.array((x,y,z))+norm*b['shoe_size'][1]/2
        shoes.obox('steel',c,b['shoe_size'],axes,bevel=.009)
        for s in (-1,1): shoes.obox('rubber',c+(s*b['shoe_size'][0]*.235,0,0)+norm*b['shoe_size'][1]*.72,b['pad_size'],axes,bevel=.008)
    return T.combine('hull_shell',parts+[shoes])


def turret(marks):
    b=S['basket']; c=S['crown']; r=S['roof']; a=S['axis']; race=S['race']; st=S['bins']; sm=S['smoke']
    parts=[T.loft([(z,[(-lo,y),(lo,y),(hi,h),(-hi,h)]) for z,y,h,lo,hi in S['bustle']]),
           P.ring((0,race['low'],a['traverse_z']),race['r'],race['inner'],race['high']-race['low'],'recess',56),
           T.cbox((0,c['y']-c['thick']/2,(c['front']+c['back'])/2),
                  (2*c['slot']+.01,c['thick'],c['front']-c['back']),.004)]
    for name in ('cheeks','side_module'):
        cheek=P.tiered_plate(S[name]); cheek.mirror_x(); parts.append(cheek)
    bar=b['bar']; dz=b['front']-b['rear']; dy=b['top']-b['low']; by=(b['top']+b['low'])/2; bz=(b['front']+b['rear'])/2
    parts.append(T.basket((0,by,bz),(b['width']-2*bar,dy-2*bar,dz-2*bar),b['pickets'],bar))
    for s in (-1,1):
        # Bridge from the after box to the angular cheek module.
        x0=c['slot']; x1=c['width']/2
        parts.append(T.cbox((s*(x0+x1)/2,c['y']-c['thick']/2,(c['front']+c['back'])/2),
                           (x1-x0,c['thick'],c['front']-c['back']),.004))
        x,y,z=_signed(st['centre'],s); w,h,l=st['size']
        parts.extend([T.cbox((x,y,z),(w,h,l),.018),T.cbox((x,y+h/2,z),(w*1.03,st['lid_h'],l),.01)])
        parts.append(P.piping([_signed(p,s) for p in S['cheek_rail']['path']],S['cheek_rail']['radius']))
        for base in sm['banks']:
            pt=np.array(_signed(base,s)); parts.append(T.cbox(pt,sm['mount'],.014))
            # Banks follow the hull Z direction, rather than running across X.
            for i in range(sm['count']):
                parts.append(T.smoke_dischargers(1,pt+(0,0,(i-(sm['count']-1)/2)*sm['spacing']),
                             _signed(sm['direction'],s),sm['spacing'],sm['radius'],sm['length']))
        eye=_signed(r['eye'],s); parts.append(T.tow_hook(eye,(0,1,0),r['eye_r'],r['eye_bar']))
        base=np.array(_signed(r['aerial'],s)); parts.append(T.antenna_mount(base,r['aerial_r'],r['aerial_h']))
        parts.append(P.turning(base,(0,1,0),[(r['aerial_h'],r['aerial_r']*.22),(r['aerial_h']+r['stub'],r['aerial_r']*.09)],'steel',12))
        tier=S['cheeks'][-1]; y,plan=tier
        T.weld_seam(marks,(s*plan[0][0],y,plan[0][1]),(s*plan[1][0],y,plan[1][1]))
        parts.append(T.bolt_row(marks,(s*plan[1][0],y,plan[1][1]),(s*plan[2][0],y,plan[2][1]),6))
        # A sheet strip halfway up the basket breaks up the open rail pattern.
        parts.append(T.cbox((s*(b['width']/2-bar),by,bz),(bar,dy*.38,dz*.96),.005))
    for key in ('commander','loader'):
        pt=np.array(r[key]); parts.append(P.ring(pt,r['ring_r'],r['hatch_r']*.94,r['ring_h']))
        parts.append(T.hatch(pt+(0,r['ring_h']*.5,0),radius=r['hatch_r'],thickness=r['lid_h']))
        if key=='commander':
            for i in range(r['scope_n']):
                t=math.tau*i/r['scope_n']; v=np.array([math.sin(t),0,math.cos(t)])
                parts.append(T.periscope(pt+r['scope_r']*v+(0,r['scope_size'][1]*.46,0),r['scope_size'],v))
        else:
            parts.append(P.ring(pt+(0,r['ring_h'],0),r['ring_r'],r['ring_r']*.945,r['ring_h']*.76,'steel'))
    parts.append(T.commander_sight(r['peri'],r['peri_top']-r['peri'][1],r['peri_r']))
    pt=np.array(r['window']); size=r['emes_size']; door=r['door']; thick=door[2]
    parts.append(T.periscope(pt-(0,0,size[2]/2),size))
    # Zero closes the door; negative X rotation swings its lower edge forward.
    hinge=pt+(0,door[1]/2,thick*.71); tilt=math.radians(-r['door_open_deg']); co,si=math.cos(tilt),math.sin(tilt)
    plate=T.cbox((0,-door[1]/2,0),door,.007); matrix=np.eye(4)
    matrix[:3,:3]=((1,0,0),(0,co,-si),(0,si,co)); matrix[:3,3]=hinge
    plate.transform(matrix); parts.append(plate)
    parts.append(P.turning(r['fan'],(0,1,0),[(0,r['fan_r']*.8),(r['fan_h']*.64,r['fan_r']),
                         (r['fan_h'],r['fan_r']*.96)],segments=24))
    parts.append(T.antenna_mount(r['sensor'],r['sensor_r']*2.3,r['sensor_h']))
    return T.combine('turret_shell',parts)


def gun():
    k=S['cover']; t=S['tube']; a=S['axis']; z=a['muzzle_z']; y=a['bore_y']; end=k['plug_end']; start=k['plug_z']
    plug=T.cbox((0,y,(start+end)/2),(*k['plug_size'],end-start),k['round'],'recess')
    cover=T.prism(k['profile'],-k['half'],k['half']); prof=list(t['profile'])
    prof.extend([(z,t['muzzle_r']),(z,t['bore_r']),(z-t['recess'],t['bore_r'])]); bands=[T.PAINT]*(len(prof)-1)
    bands[-3:]=['steel','steel','recess']
    tube=P.turning((0,y,0),(0,0,1),prof,segments=t['segments'],caps=(True,'recess'),bands=bands)
    x,dy,zz=t['sensor']; size=t['sensor_size']; ref=T.periscope((x,y+dy,zz),size)
    return T.combine('gun_shell',[plug,cover,tube,ref])


def carrier(r,width):
    """Low-detail paired carrier in axle-local game metres, for the screened upper run."""
    profile=[(-.50*width,.55*r),(-.47*width,r),(-.14*width,r),(-.12*width,.56*r),
             (.12*width,.56*r),(.14*width,r),(.47*width,r),(.50*width,.55*r)]
    return P.turning((0,0,0),(1,0,0),profile,segments=16,bands=[T.PAINT,'rubber',T.PAINT,'steel',T.PAINT,'rubber',T.PAINT])
