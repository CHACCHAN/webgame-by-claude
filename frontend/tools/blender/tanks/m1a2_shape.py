"""Photo-fit exterior stations. Lengths in metres; hull and turret are in
world rest space. Appliance internals are offsets from their named mounts;
only the gun uses trunnion-local stations. Positive x is vehicle left.
"""
import math

import tank_kit as T
import m1a2_parts as P


ST = dict(
    dims=dict(hull=(7.93,3.66,1.3), turretZ=.30, ringY=1.85, trunnion=.12,
              trunnionZ=1.79, barrel=3.72, turret=(5.6,3.7,.8)),
    gear=dict(road=tuple((z,.34) for z in (2.49,1.40,.66,-.08,-.86,-1.70,-2.49)),
              track_centre=1.42, track_width=.635, track_thickness=.09, pitch=.192,
              pad_share=.75, sag=.021, horns=1, horn_width=.048, horn_height=.075,
              wheel_width=.48, tyre_width=.14, tyre_depth=.05, dish_depth=.038, hub_bolts=8,
              sprocket=(-3.27,.80,.375,11,.40), idler=(3.47,.82,.30,.46),
              rollers=((1.0,1.02,.10,.28),(-1.4,1.02,.10,.28)), skirt_outer=1.83),
    discs=dict(hub_x=1.68,guide_clearance=.015,shoulder=.012,nut_r=.018,nut_h=.015),
    skirt=dict(cuts=(-3.58,-2.81,-2.09,-1.32,-.54,.28,1.20,3.62),
               top_z=(-3.58,1.20,3.62),top_y=(1.48,1.48,1.31),bottom=.72,
               heavy=.10,light=.036,setback=.045,gap=.016,lip=.003,rubber=.076,
               rear_cut=((0,.49),(.14,.478),(.29,.422),(.45,.301),(.60,.12),(.70,0)),nose_cut=.45,nose_lip=.042,
               hinges=(.17,.83),hinge_size=(.015,.158,.160),bevel=.010,inset=.10,
               bolt_drop=.093,bolt_r=.019,bolt_h=.005,knuckles=(-.064,0,.064),pin_len=.056,pin_r=.010,
               strap_bolts=(.025,.054),stud_r=.012,stud_h=.006),
    hull=dict(
        # (z,y) profiles for the tub and the central glacis. Separate over-track shelves.
        tub=([(-3.85,.86),(-3.41,.48),(3.34,.48),(3.565,.60),(3.965,1.15),(.763,1.60),(-3.85,1.60)],-1.06,1.06),
        shelf=([(-3.85,1.244),(-3.27,1.234),(-2.40,1.226),(1.0,1.222),(3.60,1.222),
                (3.90,1.131),(3.90,1.202),(3.51,1.235),(.763,1.60),(-3.85,1.60)],1.06,1.77),
        hanger=((1.685,1.434,-1.19),(.09,.075,4.76),.012),
        arm=([(-.37,.69),(-.28,.73),(.084,.47),(.076,.378),(-.054,.369)],1.02,1.23,'recess'),
        driver=((0,1.402,2.55),(.0,1.,.14),(.69,.57),.060),
        scopes=(((-.21,1.444,2.69),(.155,.09,.12),(-.39,0,1)),
                ((0,1.435,2.74),(.17,.09,.12),(0,0,1)),
                ((.21,1.444,2.69),(.155,.09,.12),(.39,0,1))),
        fender_x=(1.07,1.79),# Closed side profiles keep the downturned steel and flap in one front plane.
        front_steel=((3.51,1.235),(4.10,1.25),(4.12,1.24),(4.12,1.15),
                     (4.108,1.15),(4.108,1.233),(4.097,1.238),(3.51,1.223)),
        front_rubber=((4.12,1.15),(4.12,.99),(4.107,.99),(4.107,1.15)), rear_steel=((-3.57,1.61),(-3.85,1.61),(-3.931,1.586)),
        rear_rubber=((-3.924,1.58),(-3.894,.78)),steel_gauge=.021,flap_gauge=.013,
        # Axle along x. The 100 mm radius sets the aft tangent at z=-3.96.
        corner_axis=(1.80,1.60,-3.86),corner_profile=((.081,0),(.096,-.007),(.100,-.018),
                     (.100,-.105),(.088,-.117),(.071,-.122)),
        corner_foot=((1.725,1.538,-3.818),(.107,.090,.155),.014),
        headlights=dict(centre=(.89,1.113,4.009),bar=.012,
            feet=(((.032,.006,-.071),(.273,.025,.245),.006),((0,.055,-.019),(.103,.099,.11),.013)),
            lamps=(((0,.117,0),((.075,.079),(.089,.063),(.089,-.047),(.06,-.091)),('steel','tank_paint','tank_paint')),
                   ((.117,.108,0),((.044,.053),(.055,.040),(.055,-.048)),('steel','tank_paint'))),
            lenses=(((0,.117,0),((.069,.081),(.069,.078))),((.117,.108,0),((.040,.055),(.040,.052)))),
            guards=tuple(((-.115,0,z),(-.115,.206,z),(-.092,.229,z),(.159,.229,z),(.172,.208,z),(.172,0,z))
                         for z in (-.081,.086)) + (((-.107,.216,-.081),(-.107,.216,.086)),((.167,.217,-.081),(.167,.217,.086)))),
        tail=((1.55,1.44,-3.924),(.224,.128,.044),'taillight',(0,0,-1)),
        front_pin=(.92,.60,3.76),lug_x=(.862,.905),pin_span=.092,pin_r=.035,
        lug_zy=((- .073,-.049),(.006,-.053),(.048,-.016),(.047,.031),(-.008,.064),(-.144,.081)),
        eyes=((.78,1.05,-3.846),(0,0,-1),.093,.017),
        pintle=((0,.93,-3.85),(0,0,-1),.074,.026),
        exhaust=dict(centre=(0,1.291,-3.866),size=(1.32,.55,.062),frame=.045,
                     count=10,gauge=.012,angle=-28,cover=1.03),
        boxes=(((0,.94,-3.84),(.27,.14,.11),.02),((-.99,1.304,-3.855),(.33,.36,.17),.026),
               ((-.99,1.307,-3.94),(.292,.316,.029),.013),((-.90,1.31,-3.951),(.023,.064,.01),.004),
               ((1.454,1.718,-3.47),(.56,.249,.75),.037)),
        door_frame=dict(edge=.018,bar=.009,hinge_r=.023,hinge_span=.12,stand=.017),
        apu_grille=((1.454,1.846,-3.50),(.42,.024,.46),9),
        engine_panels=(((.54,1.607,-3.22),(.998,.040,1.06),16),
                       ((1.37,1.607,-2.32),(.62,.033,.98),13),
                       ((.55,1.607,-2.16),(.99,.030,.88),12)),
        deck_eyes=((1.65,1.61,-2.89),(0,1,0),.052,.013),
        bins=(((1.51,1.66,-1.34),(.42,.13,.64),.017),((1.51,1.732,-1.34),(.43,.029,.65),.006)),
        cap=((1.47,1.60,-.79),(0,1,0),((.09,.027),(.108,.018),(.108,0))),
        seam=((1.058,1.60,-3.65),(1.058,1.60,1.40),.011,.003)),
    turret=dict(
        race=((0,1.589,.30),(0,1,0),((1.05,.224),(1.13,.18),(1.13,.069),(1.155,.057),(1.155,0)),'recess',56),
        # Measured outer roof break; derive the inner corner at the same height.
        outer=(1.70,2.24,1.17),opening=.41,sweep=45.,rake=30.,batter=.13,bevel=.065,
        lower_line=((.40,1.71),(2.36,1.75)),notch_z=1.78,
        # Descending z: (z, half width at keel / chine / roof, bottom y, roof y).
        sides=((.40,(1.70,1.79,1.67),None,2.401),
               (-1.10,(1.62,1.70,1.61),1.79,2.44),(-2.25,(1.44,1.54,1.49),1.95,2.44)),
        side_bins=tuple(((1.696,2.171,z),(.183,.352,.892),.024) for z in (.12,-.812,-1.744)) +
                  tuple(((1.70,2.354,z),(.198,.032,.907),.007) for z in (.12,-.812,-1.744)),
        handles=tuple(((1.788,2.29,z),(1.815,2.29,z),(1.815,2.29,z+.24),(1.788,2.29,z+.24)) for z in (.13,-.78,-1.75)),
        bin_latch=dict(z=(.39,-.14,-.54,-1.09,-1.48,-1.99),base=(1.789,2.30),plate=(.019,.091,.068),bar=.009,reach=.024,span=.042),
        handle_r=.012, blowoff=((.68,2.452,-1.65),(1.26,.040,1.06),.015),
        blow_latches=tuple(((x,2.478,z),(.065,.021,.104),.005) for x in (.18,1.17) for z in (-2.05,-1.25)),
        rack=dict(outline=((-1.783,.60),(-1.81,.49),(-1.81,-2.25),(-1.74,-2.78),(-1.52,-3.0),
                           (.80,-3.0),(1.81,-2.0),(1.81,.49),(1.783,.60)),
                  rails=((1.990,.016),(2.207,.013),(2.440,.019)),upright=.013,bays=(1,8,3,2,12,7,8,1),
                  bearers=tuple(i*.188 for i in range(-8,9)),mount=-2.23,
                  floor_x=1.53,floor_z=tuple(-2.31-i*.077 for i in range(9)),wire=.008),
        # The front rim surrounds a real pocket. The glass box ends at the
        # measured window plane, 30 mm behind the door hinges.
        gps=dict(base=(-.77,2.275,.755),boxes=(
                 ((0,.142,-.022),(.760,.302,.566),.009),
                 ((0,.296,0),(.760,.018,.610),.004),
                 ((-.275,.140,.282),(.210,.294,.046),.003),
                 ((.315,.140,.282),(.130,.294,.046),.003),
                 ((.040,.035,.282),(.420,.086,.046),.003),
                 ((.040,.260,.282),(.420,.056,.046),.003),
                 ((.040,.155,.264),(.420,.154,.007),.002),
                 ((-.065,.155,.2705),(.170,.110,.009),.001,'glass_dark'),
                 ((.145,.155,.2705),(.170,.110,.009),.001,'glass_dark'),
                 ((.040,.155,.271),(.040,.121,.012),.001)),
                 plates=tuple(([(side*(.380+d*math.cos(math.radians(75))),y,.305+d*math.sin(math.radians(75)))
                                for d,y in ((0,.035),(.380,.035),(.380,.295),(0,.295))][::side],.014)
                              for side in (-1,1))),
        citv=dict(base=(.80,2.265,1.15),turnings=(
                 ((0,0,0),(0,1,0),((.226,.135),(.240,.126),(.240,.041),(.224,0))),
                 ((0,0,0),(0,1,0),((.185,.335),(.200,.322),(.200,.151),(.185,.135)),'tank_paint',40)),
                 optics=(((0,.238,.177),(.157,.102,.051)),)),
        commander=dict(base=(-.72,2.418,-.09),radius=.351,thick=.053,
                       profile=((.355,.117),(.386,.094),(.39,.041),(.362,0)),
                       scopes=8,scope_y=.086,scope_r=.366,scope_size=(.167,.101,.096)),
        loader=dict(base=(.91,2.417,-.20),radius=.335,lip=.041,lid_size=(.65,.64),thick=.049),
        # Keep the head in its fitted height frame. The column spans local
        # y=-.040..+.160 (deck to underside of the ring).
        crows=dict(base=(-.745,2.62,.76),turnings=(
                ((0,0,0),(0,1,0),((.151,.160),(.155,.155),(.155,-.035),(.151,-.040))),
                ((0,0,0),(0,1,0),((.202,.280),(.216,.263),(.216,.179),(.201,.160))),
                ((0,.380,.070),(0,0,1),((.026,1.140),(.029,1.135),(.029,1.053),(.023,1.046),
                                        (.026,.169),(.038,.152),(.040,0)),'steel',24),
                # Tan bezels and separate opaque glass faces on the right-hand sensor.
                ((-.515,.360,.390),(0,0,1),((.086,.049),(.091,.041),(.095,-.006))),
                ((-.515,.360,.390),(0,0,1),((.080,.051),(.080,.048)),'glass_dark',32),
                ((-.225,.340,.390),(0,0,1),((.050,.037),(.054,.030),(.055,-.006))),
                ((-.225,.340,.390),(0,0,1),((.045,.039),(.045,.036)),'glass_dark',24)),
            # Narrow crosspiece and two upright cheeks leave the receiver sides visible.
            boxes=(((0,.261,-.021),(.447,.052,.235),.009),
                   ((-.200,.305,-.026),(.047,.250,.270),.014),((.200,.305,-.026),(.047,.250,.270),.014),
                   ((0,.380,-.180),(.160,.180,.500),.012,'steel'),
                   ((0,.318,-.082),(.404,.048,.081),.009),
                   ((-.385,.345,.215),(.460,.310,.350),.016),
                   ((.251,.276,.056),(.079,.048,.150),.005),
                   ((.335,.280,.090),(.120,.200,.300),.010)),
            # Dark patches on the end collar suggest slots at game scale.
            # Each patch lies on one facet of the closed exterior cylinder.
            plates=tuple(([(.0293*math.cos(a+da),.380+.0293*math.sin(a+da),z)
                           for da,z in ((-.088,1.131),(.088,1.131),(.088,1.193),(-.088,1.193))],.001,'recess')
                         for a in (math.pi/24+i*math.pi/3 for i in range(6)))),
        pintle=dict(base=(.95,2.419,.393),turnings=(
                ((0,0,0),(0,1,0),((.071,.230),(.049,.189),(.049,.061),(.091,.043),(.091,0))),
                ((0,.284,.14),(0,0,1),((.013,.534),(.021,.520),(.014,.491),(.019,.18),(.028,.168),(.028,0)),'steel',12)),
            boxes=(((0,.221,-.007),(.145,.067,.183),.013),((0,.286,-.024),(.071,.085,.349),.005,'steel'),
                   ((0,.264,-.222),(.054,.062,.129),.009,'recess'),((-.107,.223,-.024),(.129,.129,.175),.012))),
        shield=dict(base=(.92,2.417,.18),panes=((-.403,-.13,-.306,.18),(-.277,.203,-.086,.263),
                       (.092,.263,.275,.206),(.302,.183,.404,-.128)),bottom=.18,top=.585,
                    frame=.029,glass=.014,post=.016,depth=.025),
        antenna=((1.32,2.434,-1.10),.058,.142),
        smoke=dict(rows=((1.604,2.115,.895),(1.577,2.216,.861)),direction=(.47,.81,.63),n=3,spacing=.094,r=.041,length=.233,
                   bracket=((1.625,2.147,.873),(.238,.204,.319),.035))),
    gun=dict(mantlet=((0,-.004,.021),(.744,.487,.466)),
             boot=(((0,-.009,-.101),(.790,.510,.244),.043,'rubber'),
                   ((0,-.010,-.048),(.796,.516,.033),.012,'recess')),
             breech=((0,-.01,-.422),(.709,.39,.84),.048),port=((- .267,.014,.254),.034),
             collar=((.124,.388),(.161,.368),(.178,.312),(.178,.245)),
             # World z measured at taper centres. Other stations below are (z,r).
             taper_z=(3.42,4.08),taper_half=.056,fat_r=.165,
             rear=((2.38,.117),(2.94,.116),(2.96,.122),(3.012,.122),(3.024,.116)),
             forward=((4.24,.098),(4.70,.093),(4.708,.099),(4.734,.099),(4.745,.092),
                      (5.22,.084),(5.228,.091),(5.255,.091),(5.266,.083),(5.59,.078),
                      (5.606,.090)),bore=.060,bore_depth=.125,seg=48,
             ref=(((0,.107,3.55),(.092,.083,.16),.006),((0,.110,3.632),(.064,.047,.006),.002,'glass_dark'))))


def hull(marks):
    s=ST['hull']; p=[T.prism(*s['tub']),P.pair(T.prism(*s['shelf'])),P.pair(T.cbox(*s['hanger'])),
                      P.skirt(ST['skirt'],ST['gear']['skirt_outer'],marks),P.guarded_lamp(s['headlights']),
                      P.pair(T.lamp_box(*s['tail'])),P.pair(T.tow_hook(*s['eyes'])),T.tow_hook(*s['pintle']),
                      P.exhaust(s['exhaust']),T.grille(*s['apu_grille']),P.pair(P.turned(*s['cap'])),
                      P.pair(T.tow_hook(*s['deck_eyes'])),P.pair(T.cbox(*s['corner_foot'])),
                      P.pair(P.turned(s['corner_axis'],(1,0,0),s['corner_profile'],seg=32))]
    x,y,z=s['front_pin']
    ear=T.prism([(z+a,y+b) for a,b in s['lug_zy']],*s['lug_x'])
    pin=P.turned((x,y,z),(1,0,0),[(s['pin_r'],0),(s['pin_r'],-s['pin_span'])],'steel',20)
    p.append(P.pair(T.combine('tow fittings',[ear,pin])))
    p.extend(P.boxes(s['boxes'])); p.extend(P.pair(b) for b in P.boxes(s['bins']))
    for centre,size,count in s['engine_panels']:
        p.append(P.pair(P.deck_door(centre,size,count,s['door_frame'])))
    for z,*_ in ST['gear']['road']:
        p.append(T.placed(P.pair(T.prism(*s['arm'])),(0,0,z)))
    c,n,wh,t=s['driver']; p.append(T.hatch(c,n,size=wh,thickness=t))
    p.extend(T.periscope(*spec) for spec in s['scopes'])
    for kind,mat in (('steel',T.PAINT),('rubber','rubber')):
        p.append(P.pair(T.prism(s['front_'+kind],*s['fender_x'],mat=mat)))
        ribs=[[(x,y,z) for x in s['fender_x']] for z,y in s['rear_'+kind]]
        p.append(P.pair(T.mudguard(ribs,s['steel_gauge' if kind=='steel' else 'flap_gauge'],mat)))
    a,b,r,h=s['seam']
    for sign in (-1,1): T.weld_seam(marks,(sign*a[0],*a[1:]),(sign*b[0],*b[1:]),r,h)
    return T.combine('hull_shell',p)


def cheek_rings():
    s=ST['turret']; x,y,z=s['outer']; inner=s['opening']; tip=z+(x-inner)*math.tan(math.radians(s['sweep']))
    (a,b),(c,d)=s['lower_line']; floor=lambda zz: b+(zz-a)*(d-b)/(c-a)
    h=floor(z); bevel=s['bevel']; dz=(y-h-bevel)*math.tan(math.radians(s['rake']))
    corners=((inner,h,s['notch_z']),(inner,h,tip+dz-bevel),(x,h,z+dz-bevel))
    rings=[]
    for i,start in enumerate((corners,((inner,h+bevel,s['notch_z']),(inner,h+bevel,tip+dz),(x+s['batter'],h+bevel,z+dz)),
                              ((inner,y+.06,s['notch_z']),(inner,y,tip),(x,y,z)))):
        half=list(start)
        for zz,width,base,roof in s['sides']:
            bottom=floor(zz) if base is None else base
            half.append((width[i],(bottom,bottom+bevel,roof)[i],zz))
        rings.append(half+[(-xx,yy,zz) for xx,yy,zz in reversed(half)])
    return rings


def turret():
    s=ST['turret']; rings=cheek_rings()
    p=[P.skin(rings),P.turned(*s['race']),P.bustle_rack(s['rack']),
       P.pair(T.cbox(*s['blowoff'])),P.pair(T.antenna_mount(*s['antenna'])),P.shield(s['shield'])]
    p.extend(P.pair(b) for b in P.boxes((*s['side_bins'],*s['blow_latches'])))
    p.extend(P.pair(P.rail(path,s['handle_r'],'steel')) for path in s['handles'])
    latch=s['bin_latch']; x,y=latch['base']; dx=latch['reach']; dz=latch['span']/2
    for z in latch['z']:
        bracket=T.cbox((x,y,z),latch['plate'],latch['bar']/2)
        bail=P.rail([(x,y,z-dz),(x+dx,y-dx,z-dz),(x+dx,y-dx,z+dz),(x,y,z+dz)],latch['bar'],'steel')
        p.append(P.pair(T.combine('bin latch',[bracket,bail])))
    p.extend(P.outfit(s[key]) for key in ('citv','gps','pintle','crows'))
    q=s['commander']; base=q['base']; up=(0,1,0)
    p.append(P.turned(base,up,q['profile'])); x,y,z=base
    p.append(T.hatch((x,y+q['profile'][0][1],z),radius=q['radius'],thickness=q['thick']))
    for k in range(q['scopes']):
        phi=math.tau*k/q['scopes']; u,v=math.sin(phi),math.cos(phi)
        p.append(T.periscope((x+q['scope_r']*u,y+q['scope_y'],z+q['scope_r']*v),q['scope_size'],(u,0,v)))
    lid=s['loader']; c=lid['base']; r=lid['radius']; lip=lid['lip']
    p.append(P.turned(c,up,[(r-lip,lip),(r,lip),(r,0)],'recess'))
    p.append(T.hatch((c[0],c[1]+lip,c[2]),up,size=lid['lid_size'],thickness=lid['thick']))
    smoke=s['smoke']; p.append(P.pair(T.cbox(*smoke['bracket'])))
    for c in smoke['rows']:
        p.append(P.pair(T.smoke_dischargers(smoke['n'],c,smoke['direction'],smoke['spacing'],smoke['r'],smoke['length'])))
    return T.combine('turret_shell',p)


def gun():
    s=ST['gun']; d=ST['dims']
    origin=(0,d['ringY']+d['trunnion'],d['turretZ']+d['trunnionZ']); z0=origin[2]
    a,b=s['taper_z']; half=s['taper_half']; fat=s['fat_r']; rear=s['rear']; fore=s['forward']
    profile=[*rear,(a-half,rear[-1][1]),(a+half,fat),(b-half,fat),(b+half,fore[0][1]),*fore]
    profile=[(r,z-z0) for z,r in profile]+[(fore[-1][1],d['barrel']),(s['bore'],d['barrel']),
                                         (s['bore'],d['barrel']-s['bore_depth'])]
    shell=T.Part('thermal jacket'); shell.revolve(T.PAINT,profile[::-1],(0,0,0),axis=(0,0,1),seg=s['seg'],
             cap0='recess',cap1=True,mat_of=lambda k:'recess' if k==0 else ('steel' if k<3 else T.PAINT))
    p=[T.mantlet(*s['mantlet']),T.coax_port(*s['port']),T.cbox(*s['breech']),*P.boxes(s['boot']),
       P.turned((0,0,0),(0,0,1),s['collar'],seg=s['seg']),shell,*P.boxes(s['ref'])]
    return T.placed(T.combine('gun_shell',p),origin)
