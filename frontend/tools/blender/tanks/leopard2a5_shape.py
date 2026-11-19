"""Editable photo-fit table. Everything is in metres in the level, assembled hull
frame unless explicitly marked local. +X left, +Y up, +Z bow. No bpy objects
for individual fittings: the three builders return finished, unbuilt Parts.
"""
import math
import numpy as np
import tank_kit as T
import leopard2a5_parts as P

S = {
    # Rig datums (unchanged); roof.window is the centre of the exposed glass.
    'axis': dict(traverse_z=.40, ring_y=1.70, elevation_z=1.48, bore_y=2.12,
                 muzzle_z=5.69, limits=(-9.,20.), traverse_check=(0.,30.), sweep_step=10, gap=.020, recoil=.45),
    'gear': dict(track_centre=1.45, track_width=.635, track_thickness=.050, pitch=.185,
                 road_z=(2.46,1.61,.83,.06,-.79,-1.64,-2.46), hub_y=(.40,.42), radius=.35,
                 wheel_width=.46, tyre_width=.14, tyre_depth=.041, dish_depth=.034, hub_bolts=6,
                 idler=(3.08,.92,.315,.45), sprocket=(-3.26,.79,.35,11,.46),
                 rollers=((2.035,1.14,.105),(.445,1.13,.105),(-1.215,1.105,.105),(-2.05,1.085,.105)),
                 sag=.024, horns=2, horn_width=.037, horn_height=.044, pad_share=.84, skirt_outer=1.88),
    'road_seg':36,
    'track_tint':'#494943',
    # Tub stations (z, keel y, deck y, bottom half-width, shoulder half-width).
    # Tiny truncated end edges avoid a zero-area cap at the prow.
    'tub': [(-4.005,1.17,1.73,1.04,1.08),(-3.90,.77,1.70,.95,1.09),
            (-3.55,.50,1.69,.96,1.09),(-1.20,.515,1.70,.97,1.10),
            (1.25,.533,1.70,.98,1.10),(1.48,.535,1.66,.98,1.10),
            (2.80,.54,1.35,.70,1.10),(3.72,1.125,1.135,1.035,1.09)],
    'bilge': .075,
    'well': dict(aft=-.30,front=.91,width=1.32,floor=1.43,rim=.025),
    'deck_seam': ((1.78,1.70,-3.79),(1.78,1.70,1.22)),
    # Sponson shelves (z, underside, roof, outer half-width); inner edge laps the tub.
    'shelf': [(-4.03,1.17,1.73,1.70),(-3.83,1.20,1.70,1.80),(-1.20,1.30,1.70,1.81),
              (1.25,1.30,1.70,1.81),(2.65,1.32,1.42,1.80),(3.19,1.30,1.325,1.77)],
    'shelf_inner':1.055,
    'skirt': dict(heavy=(3.28,2.60,1.92,1.25), light=(1.25,.34,-.55,-1.43,-2.25,-3.05,-3.86),
                  rail_y=1.35, heavy_low=.85, light_low=.86, tail_low=1.00, tail_top=1.24, tail_toe=-3.95,
                  heavy_depth=.11, light_depth=.043, gap=.016, strip=.048, bevel_run=.28,
                  bevel_rise=.22, steps_z=(1.22,-.365,-2.05),step_x=1.866,step_low=(.695,.72,.705),
                  step_span=(.45,.39,.48),step_bar=.018,rail_r=.021, bolt=.020, bolt_inset=.09),
    'fender': dict(inner=1.105, outer=1.90, ribs=((2.76,1.412,1.41),(3.32,1.33,1.32),
                   (3.45,1.085,1.035)),track_lip_x=1.782,thickness=.019,
                   apron_x=1.45, apron_w=.69, flap_y=(.565,.855,1.19),
                   flap_z=(-3.954,-3.994), flap_skin=.032, step=.058, hinge_r=.023),
    'driver': dict(centre=(-.62,1.543,2.03), lid=(.69,.70), thick=.037, rail_x=.365,
                   rail_size=(.033,.043,.89),window_size=(.154,.096,.115),
                   windows=((- .22,.28),(0,.33),(.22,.28))), # hatch-local x,z
    'bow': dict(lens=(1.018,1.365,3.238), lamp_r=.087,lamp_depth=.144,guard=(.242,.189,.16),rod=.012,
                eye=(.83,1.12,3.64),eye_r=.091, eye_bar=.027,marker=(1.69,1.345,3.21),marker_size=(.076,.046,.068),
                clip=(.029,.054,.245), pin_r=.022, shoe_x=(0.,.40,-.40),shoe_z=3.17,shoe_size=(.345,.069,.215),pad_size=(.135,.028,.145)),
    'deck': dict(grilles=((.72,1.818,-3.64,1.36,.026,.62,14),(.87,1.708,-2.52,1.28,.028,.62,11)),
                 # Raised plinth only under the aft pair; narrow outer cowls start
                 # beyond the low-angle window. Rear shelf corners remain at 1.73.
                 surround=(.72,1.754,-3.645),surround_size=(1.44,.121,.68),
                 cowl_x=(1.30,1.675),cowl_profile=((-3.99,1.71),(-3.20,1.69),(-3.24,1.837),(-3.41,1.88),(-3.91,1.88)),
                 lids=((1.57,1.695,-1.18),(1.57,1.695,-.31),(1.57,1.695,.56)),lid_size=(.39,.016,.82),latch=(0,.007,.31),latch_size=(.09,.008,.042),
                 tool_x=1.71,tool_y=1.739,tool_z=(-3.48,-2.06), tool_r=.019,
                 vent=(1.834,1.517,-2.69),vent_size=(.64,.029,.144),vent_slats=5),
    'stern': dict(grille=(0,1.453,-4.034),size=(3.45,.047,.544),slats=15,
                  uprights=(-1.695,-1.13,-.56,0.,.56,1.13,1.695), post_w=.026,frame_h=.021,
                  transom=((-3.984,.733),(-3.84,.685),(-3.80,1.25),(-3.997,1.25)),half=1.095,
                  lamp=(1.478,1.085,-4.015),case=(.365,.153,.082),r=.061,
                  strip_size=(.139,.061,.013),strip_dx=.078,round_dx=.091,
                  screen=(.536,.953,-4.019),screen_r=.163,screen_depth=.022,screen_pitch=.030,screen_bar=.005,
                  reflector=(.964,.838,-3.995),reflector_size=(.13,.044,.019),
                  eye=(.835,.792,-3.982),eye_r=.096,eye_bar=.028,camera=(.34,1.127,-3.998),camera_size=(.13,.096,.092),
                  # From corner saddle to the opposite tow eye; crossing is below blade field.
                  cable=((1.63,1.74,-3.86),(1.734,1.66,-4.077),(1.753,1.38,-4.087),
                         (1.713,1.205,-4.091),(1.55,1.148,-4.101),(1.18,1.094,-4.10),
                         (.70,.994,-4.084),(.21,.906,-4.078),(-.31,.827,-4.074),(-.713,.805,-4.066)),
                  cross_offset=.050,cable_r=.019,cable_lay=.19,loop_x=.069,loop_y=.036),
    # Solid rear turret stations (z, lower y, upper y, lower and upper half-width).
    # Front has two side walls and a thin roof bridge, NOT a wall through the gun.
    'bustle': [(-2.06,2.07,2.436,1.29,1.34),(-1.69,2.00,2.454,1.40,1.47),
               (-.68,1.77,2.482,1.46,1.50),(-.18,1.728,2.49,1.46,1.50)],
    'crown': dict(back=-.181,front=1.31,y=2.49,thick=.041,width=2.89,slot=.392,
                  eave_drop=.028,front_drop=.011),
    'race': dict(low=1.69,high=1.79,r=1.065,inner=.83,guard_inner=1.093,guard_r=1.196,guard_base=1.692,guard_top=1.705),
    # Chin / lip underside / lip edge / shoulder. The lip sweep and the two
    # returns can be fitted independently without disturbing the shield slot.
    'cheeks': [(1.728,[(.386,2.52),(1.44,1.62),(1.52,.37),(1.46,-.20),(.386,-.20)]),
               (2.142,[(.379,3.015),(1.583,2.075),(1.645,.40),(1.55,-.20),(.379,-.20)]),
               (2.153,[(.379,3.010),(1.583,2.070),(1.645,.40),(1.55,-.20),(.379,-.20)]),
               (2.425,[(.389,1.73),(1.478,1.09),(1.55,.40),(1.50,-.20),(.389,-.20)]),
               (2.461,[(.395,1.285),(1.431,.967),(1.445,.40),(1.445,-.20),(.395,-.20)])],
    'side_module':[(1.729,[(1.39,.42),(1.544,.42),(1.526,-.70),(1.39,-.70)]),
                   (2.45,[(1.39,.42),(1.563,.42),(1.535,-.70),(1.39,-.70)])],
    # Bottom/top rear corner (half-width, y, z); solid stowage inside the rim.
    'basket':dict(base=(1.59,1.86,-2.96),rim=(1.50,2.22,-3.07),front=-1.895,
                  splits=(-1.,-.49,0.,.51,1.),gap=.014,lid_h=.034,lip=.012,
                  ribs=(.14,.30,.46,.62),rib_span=.255, rib_r=.011,
                  pull_r=.087,pull_bar=.012,catch_w=.071,catch_drop=.058,catch_relief=(.009,.004),
                  # Plan widths vary with height; the forward side lockers join
                  # the last rear station at the same widths, without a shelf.
                  flank_front=-.695,flank_low=2.031,flank_high=2.424,flank_inner=1.32),
    'roof':dict(commander=(-.69,2.487,-.18),loader=(.69,2.487,-.20),hatch_r=.32,lid_h=.042,
                ring_r=.375,ring_h=.055,scope_r=.402,scope_size=(.127,.075,.10),scope_n=8,
                handle=(.095,.075,.035),handle_r=.012,loader_rail=.305,
                peri=(-.62,2.48,-.79),peri_top=3.018,peri_r=.214,peri_head=(.35,.168,.30),
                window=(-.86,2.516,1.435),emes_width=.48,emes_base=2.415,
                emes_top=((.89,2.61),(1.43,2.57)),door_tip=(1.64,2.53),door_skin=.014,
                glass=(.371,.067,.005), jamb=.029,
                fan=(.43,2.478,-.91),fan_r=.156,fan_h=.065,
                aerial=(1.16,2.455,-1.58),aerial_r=.062,aerial_h=.13,stub=.96,
                sensor=(.88,2.465,-1.23),sensor_h=.20, sensor_r=.018,
                eye=(1.19,2.459,1.10),eye_r=.063,eye_bar=.014),
    'smoke':dict(banks=((1.653,2.255,-1.03,6),(1.665,2.065,-1.32,2)),spacing=.145,
                 direction=(.66,.78,.37),radius=.055,length=.247, mount=(.043,.042),
                 feet=(.166,.054,.055),rail_lift=.038,rail_r=.012),
    'cheek_rail':dict(paths=(((1.561,2.255,1.47),(1.625,2.269,1.45),(1.644,2.269,1.13),(1.58,2.255,1.11)),
                             ((1.604,2.255,.86),(1.666,2.269,.84),(1.672,2.269,.55),(1.608,2.255,.53))),
                      radius=.013,hinge=(1.567,2.264,.355),plate=(.028,.154,.108),pin=.025, panel_inset=.062,panel_skin=.009),
    # Cosmetic moving shell: z axial stations, widths/heights. The breech is
    # just a blind animation plug; no internal mechanism or operating geometry.
    'cover':dict(profile=((1.38,1.976),(1.65,1.943),(2.36,1.952),(2.99,2.052),(3.01,2.174),
                          (2.34,2.388),(1.63,2.335),(1.38,2.268)), half=.362,
                 plug_z=.41,plug_end=1.60,plug_size=(.33,.17),round=.032),
    'tube':dict(profile=((1.46,.118),(2.91,.118),(2.94,.141),(3.045,.141),(3.052,.116),
                         (3.22,.113),(3.227,.122),(3.25,.122),(3.304,.152),(3.335,.161),
                         (3.864,.155),(3.902,.148),(3.918,.126),(3.930,.119),(3.956,.119),(3.963,.109),(4.43,.105),(4.438,.112),
                         (4.471,.112),(4.478,.103),(4.992,.095),(5.003,.103),(5.038,.103),
                         (5.046,.093),(5.47,.083),(5.486,.098)),
                muzzle_r=.098,bore_r=.060,recess=.12,segments=40,
                collar=(5.525,5.573,.105),sensor=(.050,.100,5.554),sensor_size=(.066,.052,.083)), # sensor y relative to bore
    # Projected artwork centre and size in surface metres; no decal meshes.
    'insignia':dict(side=(-.18,2.295,.236),rear=(.0,1.037,.133),number=(.812,2.31,.184)),
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
            last=not heavy and i==len(seq)-2
            a+=0 if last else gap; b-=0 if heavy and not i else gap
            toe=k['tail_toe'] if last else a
            low=k['heavy_low' if heavy else 'light_low']; la=k['tail_low'] if last else low
            ha=k['tail_top'] if last else h; hb=h
            # Stepped heavy front bays and a rising tail cut, not identical tiles.
            prof=[(toe,la+strip),(b,low+strip),(b,hb),(a,ha)]
            if heavy:
                scale=1 if not i else .32
                prof[1:2]=[(b-scale*k['bevel_run'],low),(b,low+scale*k['bevel_rise'])]
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
                lip=T.prism([(toe,la),(b,low),(b,low+strip),(toe,la+strip)],x-depth*.9,x-depth*.1,'rubber')
                lip.mirror_x(); parts.append(lip)
            for s in (-1,1):
                parts.append(P.piping([(s*(x-depth/2),ha,a),(s*(x-depth/2),hb,b)],k['rail_r']))
                for f in ((.17,.85) if heavy else (.79,)):
                    parts.append(T.bolt_row(marks,(s*x,la+(ha-la)*f,a+k['bolt_inset']),(s*x,low+(h-low)*f,b-k['bolt_inset']),
                                            3,radius=k['bolt'],normal=(s,0,0)))
    for z,span,bot in zip(k['steps_z'],k['step_span'],k['step_low']):
        half=span/2; top=k['light_low']+.023; x=k['step_x']
        q=P.piping([(x,top,z-half),(x,bot,z-half*.7),(x,bot,z+half*.7),(x,top,z+half)],k['step_bar'],'steel')
        q.mirror_x(); parts.append(q)
    return parts


def hull(rg,marks):
    parts=_shell()+_skirts(rg,marks); f=S['fender']; b=S['bow']; r=S['stern']; d=S['deck']
    race=S['race']; parts.append(P.ring((0,race['guard_base'],S['axis']['traverse_z']),race['guard_r'],
                                       race['guard_inner'],race['guard_top']-race['guard_base'],'steel',56))
    parts.append(T.prism(r['transom'],-r['half'],r['half']))
    # The backing bridges the slanted tub and both rear shelves; the dark grille face is proud of it.
    _,y,z=r['grille']; width,depth,height=r['size']
    parts.append(T.cbox((0,y,z+depth),(width,height,depth*1.9),.008))
    parts.append(P.face_grille(r['grille'],r['size'],r['slats'],-1))
    _,gy,gz=r['grille']; _,gd,gh=r['size']
    for xx in r['uprights']: parts.append(T.cbox((xx,gy,gz-gd/2),(r['post_w'],gh,gd),.004))
    for sign in (-1,1):
        parts.append(T.cbox((0,gy+sign*(gh-r['frame_h'])/2,gz-gd/2),(r['size'][0],r['frame_h'],gd),.004))
    for s in (-1,1):
        # Opaque locker behind the folded track flap. The sloping lower side clears the idler arc.
        ribs=f['ribs']; x0=f['inner']; x1=f['outer']; t=f['thickness']
        flank=T.prism([(ribs[0][0],ribs[0][2]-t),(ribs[-1][0],ribs[-1][2]),
                       (ribs[-2][0],ribs[-2][2]),(ribs[0][0],ribs[0][2])],
                      min(s*x1,s*(x1-t)),max(s*x1,s*(x1-t)))
        parts.append(flank)
        # Full-width fold clears the reduced idler wrap; only the outer ear drops further.
        for left,right in ((x0,f['track_lip_x']),(f['track_lip_x'],x1)):
            def height(x,i):
                _,yi,yo=ribs[i]
                if i==len(ribs)-1 and x<=f['track_lip_x']: return yi
                if i==len(ribs)-1: return yo
                return yi+(yo-yi)*(x-x0)/(x1-x0)
            parts.append(T.mudguard([[(s*x,height(x,i),z) for x in (left,right)]
                                     for i,(z,_,_) in enumerate(ribs)],t))
        # Overlapping stepped leaves, with a hinge between them rather than a single plank.
        x=f['apron_x']; w=f['apron_w']; step=f['step']; bot,joint,top=f['flap_y']; za,zb=f['flap_z']
        for lo,hi,z,width,zone in ((joint,top,za,w,'tank_paint'),(bot,joint+step/2,zb,w-step,'rubber')):
            parts.append(T.loft([(zz,[(s*(x-width/2+step),lo),(s*(x+width/2),lo),(s*(x+width/2),hi),
                               (s*(x-width/2),hi),(s*(x-width/2),lo+step)]) for zz in (z-f['flap_skin']/2,z+f['flap_skin']/2)],zone))
        for off in (-.30,0.,.30):
            parts.append(P.turning((s*(x+w*off),joint,zb),(1,0,0),[(-w*.09,f['hinge_r']),(w*.09,f['hinge_r'])],segments=10))
        x,y,z=_signed(b['lens'],s); w,h,l=b['guard']; rod=b['rod']
        parts.append(P.bezel((x,y,z),(0,0,1),b['lamp_r'],b['lamp_depth'],'headlight'))
        # One bowed guard, below the lens centre at its feet; two short returns into the deck.
        for side in (-1,1):
            parts.append(P.piping([(x+side*w*.5,y-h*.48,z-l*.8),(x+side*w*.5,y+h*.23,z),
                                   (x+side*w*.38,y+h*.39,z+l*.12),(x,y+h*.39,z+l*.12)],rod))
        parts.append(T.cbox(_signed(b['marker'],s),b['marker_size'],.01,'steel'))
        for t,axis in ((b,1),(r,-1)):
            parts.append(T.tow_hook(_signed(t['eye'],s),(0,0,axis),t['eye_r'],t['eye_bar']))
        parts.append(T.cbox(_signed(d['surround'],s),d['surround_size'],.016))
        parts.append(T.prism(d['cowl_profile'],*sorted(s*v for v in d['cowl_x'])))
        vent=T.grille((0,0,0),d['vent_size'],d['vent_slats']); matrix=np.eye(4)
        # Mount flush with the sloping shoulder, not a vertical plane through it.
        shelf=np.asarray(S['shelf']); sz=d['vent'][2]; sh=np.interp(sz,shelf[:,0],shelf[:,2]); sw=np.interp(sz,shelf[:,0],shelf[:,3])
        skirt=S['skirt']; up=sh-skirt['rail_y']; run=rg.skirt_outer-skirt['light_depth']*.52-sw; hyp=math.hypot(up,run)
        matrix[:3,:3]=((0,s*up/hyp,-s*run/hyp),(0,run/hyp,up/hyp),(s,0,0)); matrix[:3,3]=_signed(d['vent'],s)
        vent.transform(matrix); parts.append(vent)
        for x,y,z,w,h,l,n in d['grilles']: parts.append(T.grille((s*x,y,z),(w,h,l),n))
        for c in d['lids']:
            parts.append(T.cbox(_signed(c,s),d['lid_size'],.012)); x,y,z=_signed(c,s)
            parts.append(T.cbox(np.array((x,y,z))+d['latch'],d['latch_size'],.005,'steel'))
        parts.append(P.piping([(s*d['tool_x'],d['tool_y'],z) for z in d['tool_z']],d['tool_r'],'steel'))
        T.weld_seam(marks,*[_signed(pt,s) for pt in S['deck_seam']])
        x,y,z=_signed(r['lamp'],s); w,h,l=r['case']
        parts.append(T.cbox((x,y,z+l*.72),r['case'],.014,'recess'))
        parts.append(P.bezel((x+s*r['round_dx'],y,z-l*.13),(0,0,-1),r['r'],l/2,'taillight'))
        # Split lens: the amber/clear segment is pigmented on the atlas, not an extra material.
        sx,sy,sz=r['strip_size']; xc=x-s*r['strip_dx']
        for off,zone in ((-.25,'taillight'),(.25,T.PAINT)):
            parts.append(T.cbox((xc+s*off*sx,y,z-sz/3),(.48*sx,sy,sz),.004,zone))
        parts.append(P.piping([(x-w*.52,y-h*.44,z),(x-w*.52,y+h*.50,z),(x+w*.52,y+h*.50,z),(x+w*.52,y-h*.44,z)],rod))
        parts.append(P.round_screen(_signed(r['screen'],s),r['screen_r'],r['screen_depth'],r['screen_pitch'],r['screen_bar']))
        parts.append(T.cbox(_signed(r['reflector'],s),r['reflector_size'],.004,'taillight'))
        path=[np.array(_signed(pt,s)) for pt in r['cable']]
        if s<0:
            for pt in path: pt[2]-=r['cross_offset']*max(0.,1-abs(pt[0])/r['eye'][0])
        parts.append(P.laid_cable(path,r['cable_r'],r['cable_lay']))
        end=path[-1]; rx=r['loop_x']; ry=r['loop_y']
        loop=[end+(-s*rx*(1-math.cos(t)),ry*math.sin(t),0) for t in np.linspace(0,math.tau,17)]
        parts.append(P.piping(loop,r['cable_r']*.83,'steel'))
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
        for sign in (-1,1):
            shoes.obox(T.PAINT,c+(sign*b['shoe_size'][0]*.46,0,0)+norm*b['clip'][1]*.35,b['clip'],axes)
        pin=c-forward*b['shoe_size'][2]*.47
        parts.append(P.turning(pin,(1,0,0),[(-b['shoe_size'][0]*.53,b['pin_r']),(b['shoe_size'][0]*.53,b['pin_r'])],'steel',10))
    return T.combine('hull_shell',parts+[shoes])


def turret(marks):
    b=S['basket']; c=S['crown']; r=S['roof']; a=S['axis']; race=S['race']; sm=S['smoke']
    parts=[T.loft([(z,[(-lo,y),(lo,y),(hi,h),(-hi,h)]) for z,y,h,lo,hi in S['bustle']]),
           P.ring((0,race['low'],a['traverse_z']),race['r'],race['inner'],race['high']-race['low'],'recess',56)]
    # One crowned bridge, falling shallowly both towards the eaves and towards the bow.
    ribs=[]
    for z,drop in ((c['back'],0),(c['front'],c['front_drop'])):
        h=c['y']-drop; side=h-c['eave_drop']; x=c['width']/2; t=c['thick']; k=c['slot']
        ribs.append((z,[(-x,side-t),(-k,h-t),(k,h-t),(x,side-t),(x,side),(k,h),(-k,h),(-x,side)]))
    parts.append(T.loft(ribs))
    for name in ('cheeks','side_module'):
        cheek=P.tiered_plate(S[name]); cheek.mirror_x(); parts.append(cheek)
    xb,low,zb=b['base']; xt,top,zt=b['rim']; front=b['front']; lip=b['lip']; gap=b['gap']
    # Four independent closed bins. Their actual lid outer corners (not the
    # centre of a projecting bar) are the surveyed rim stations.
    def section(left,right,t,inset=0.):
        width=xb+t*(xt-xb); back=zb+t*(zt-zb)
        x0=left*width+(gap/2 if left>-1 else 0)+inset; x1=right*width-(gap/2 if right<1 else 0)-inset
        return [(x0,back+inset),(x1,back+inset),(x1,front-inset),(x0,front-inset)]
    t0=1-b['lid_h']/(top-low)
    for i,(left,right) in enumerate(zip(b['splits'],b['splits'][1:])):
        parts.append(P.tiered_plate([(low,section(left,right,0)),(top-b['lid_h'],section(left,right,t0,lip))]))
        parts.append(P.tiered_plate([(top-b['lid_h'],section(left,right,t0)),(top,section(left,right,1))]))
        def face(u,v):
            w=xb+(xt-xb)*v
            return np.array([(left+(right-left)*u)*w,low+(top-low)*v,zb+(zt-zb)*v+lip*v-b['rib_r']/2])
        if i==1:
            for u in b['ribs']: parts.append(P.piping([face(u,.11),face(u+b['rib_span'],.79)],b['rib_r']))
        if i==2:
            pt=face(.5,.38); rad=b['pull_r']; angles=np.linspace(0,math.pi,13)
            parts.append(P.piping([pt+(rad*math.cos(t),rad*math.sin(t),-rad*.22*math.sin(t)) for t in angles],b['pull_bar'],'steel'))
        for u in (.22,.78):
            pt=face(u,t0); foot=face(u,t0-b['catch_drop']/(top-low)); radius,height=b['catch_relief']
            for dx in (-b['catch_w']/2,b['catch_w']/2):
                T.weld_seam(marks,pt+(dx,0,0),foot+(dx,0,0),radius,height)
            T.weld_seam(marks,foot-(b['catch_w']/2,0,0),foot+(b['catch_w']/2,0,0),radius,height)
    for s in (-1,1):
        inner=b['flank_inner']; zf=b['flank_front']
        parts.append(T.loft([(front,[(s*inner,low),(s*xb,low),(s*xt,top),(s*inner,top)]),
                             (zf,[(s*inner,b['flank_low']),(s*xb,b['flank_low']),(s*xt,b['flank_high']),(s*inner,b['flank_high'])])]))
        rail=S['cheek_rail']; centre=np.array(_signed(rail['hinge'],s)); plate=rail['plate']
        # Floating hinge detail alone reads as a handle. Overlay the actual
        # four-corner end facet, leaving a narrow reveal round its perimeter.
        cheek=S['cheeks']; panel=[]
        for row,corner in ((0,1),(0,2),(1,2),(1,1)):
            yy,plan=cheek[row]; xx,zz=plan[corner]; panel.append([s*xx,yy,zz])
        poly=np.array(panel); poly+=rail['panel_inset']*(poly.mean(axis=0)-poly)
        poly[:,0]+=s*rail['panel_skin']; orient=np.cross(poly[1]-poly[0],poly[2]-poly[0])[0]
        parts.append(T.slab(poly if orient*s>0 else poly[::-1],rail['panel_skin']))
        parts.append(T.cbox(centre,plate,.006))
        parts.append(P.turning(centre+(s*plate[0]/2,0,0),(0,1,0),[(-plate[1]/2,rail['pin']),(plate[1]/2,rail['pin'])],'steel',12))
        for path in rail['paths']: parts.append(P.piping([_signed(p,s) for p in path],rail['radius']))
        for x,y,z,count in sm['banks']:
            pt=np.array((s*x,y,z)); span=count*sm['spacing']; w,h=sm['mount']
            parts.append(T.cbox(pt,(w,h,span),.007)); fw,fh,fl=sm['feet']
            for end in (-1,1): parts.append(T.cbox(pt+(-s*fw/2,0,end*span*.36),(fw,fh,fl),.006))
            lift=sm['rail_lift']; rr=sm['rail_r']; outer=s*w*.54
            parts.append(P.piping([pt+(outer,0,-span/2),pt+(outer,-lift,-span/2),pt+(outer,-lift,span/2),pt+(outer,0,span/2)],rr))
            for i in range(count):
                parts.append(T.smoke_dischargers(1,pt+(0,0,(i-(count-1)/2)*sm['spacing']),
                             _signed(sm['direction'],s),sm['spacing'],sm['radius'],sm['length']))
        eye=_signed(r['eye'],s); parts.append(T.tow_hook(eye,(0,1,0),r['eye_r'],r['eye_bar']))
        base=np.array(_signed(r['aerial'],s)); parts.append(T.antenna_mount(base,r['aerial_r'],r['aerial_h']))
        parts.append(P.turning(base,(0,1,0),[(r['aerial_h'],r['aerial_r']*.22),(r['aerial_h']+r['stub'],r['aerial_r']*.09)],'steel',12))
        tier=S['cheeks'][-2]; y,plan=tier
        T.weld_seam(marks,(s*plan[0][0],y,plan[0][1]),(s*plan[1][0],y,plan[1][1]))
        parts.append(T.bolt_row(marks,(s*plan[1][0],y,plan[1][1]),(s*plan[2][0],y,plan[2][1]),6))
    for key in ('commander','loader'):
        pt=np.array(r[key]); parts.append(P.ring(pt,r['ring_r'],r['hatch_r']*.94,r['ring_h']))
        parts.append(T.hatch(pt+(0,r['ring_h']*.5,0),radius=r['hatch_r'],thickness=r['lid_h']))
        dx,dy,dz=r['handle']; top=pt+(0,r['ring_h']*.5+r['lid_h'],0)
        parts.append(P.piping([top+q for q in ((-dx,0,dz),(-dx,dy*.55,dz),(dx,dy*.55,dz),(dx,0,dz))],r['handle_r']))
        if key=='commander':
            for i in range(r['scope_n']):
                t=math.tau*i/r['scope_n']; v=np.array([math.sin(t),0,math.cos(t)])
                parts.append(T.periscope(pt+r['scope_r']*v+(0,r['scope_size'][1]*.46,0),r['scope_size'],v))
        else:
            parts.append(P.ring(pt+(0,r['ring_h'],0),r['ring_r'],r['ring_r']*.945,r['ring_h']*.76,'steel'))
            rad=r['loader_rail']; rail=[(rad*math.sin(v),dy,rad*math.cos(v)) for v in np.linspace(-1.3,1.3,8)]
            parts.append(P.piping([pt+q for q in [(rail[0][0],0,rail[0][2]),*rail,(rail[-1][0],0,rail[-1][2])]],r['handle_r']))
    pt=np.array(r['peri']); rad=r['peri_r']; w,h,l=r['peri_head']; lift=r['peri_top']-pt[1]-h
    parts.append(P.turning(pt,(0,1,0),[(0,rad),(.18*lift,rad),(.21*lift,.77*rad),
                         (.72*lift,.77*rad),(.77*lift,.87*rad),(lift,.87*rad)],segments=28))
    head=pt+(0,lift+h*.47,0); parts.append(T.periscope(head,(w,h*.94,l)))
    parts.append(T.cbox(pt+(0,lift+h*.95,l*.07),(w*1.08,h*.10,l*1.18),.005))
    # The glass is the front face datum, not the head centre. The armoured
    # visor extends beyond that face; its narrow cheeks leave the glazing open.
    x,y,z=r['window']; width=r['emes_width']; (back,bh),(nose,nh)=r['emes_top']; tip,th=r['door_tip']; floor=r['emes_base']
    parts.append(T.prism([(back,floor),(nose,floor),(nose,nh),(back,bh)],x-width/2,x+width/2))
    w,h,t=r['glass']; parts.append(T.cbox((x,y,z-t/2),(w,h,t),t*.25,'glass_dark'))
    skin=r['door_skin']; parts.append(T.prism([(nose,nh-skin),(tip,th-skin),(tip,th),(nose,nh)],x-width/2,x+width/2))
    for side in (-1,1):
        a,b=sorted((x+side*width/2,x+side*(width/2-r['jamb'])))
        parts.append(T.prism([(nose,floor),(tip,th-2*skin),(tip,th-skin),(nose,nh-skin)],a,b))
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
    lo,hi,rr=t['collar']; collar=P.turning((0,y,0),(0,0,1),[(lo,rr),(hi,rr)],segments=t['segments'])
    return T.combine('gun_shell',[plug,cover,tube,collar,ref])

