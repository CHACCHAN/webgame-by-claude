"""Spatial camouflage and projected service markings, evaluated on the packed atlas."""
import math
import os

import bpy
import numpy as np
import jet_atlas as JA
import jet_kit as K
from f15_paint import Sheet
from tank_atlas import DEFAULT_SCHEME
from type16_shape import AXLES, TRUN, BUSTLE_DOORS, DECK
from type16_wheels import CY, TRACK_HALF, TREAD_COUNT

BASE,GREEN,BROWN,DUST=(DEFAULT_SCHEME[k] for k in ('base','green','brown','dust'))
PALETTE = dict(bustle=GREEN, door=GREEN, plate=GREEN, cheek=BROWN, shield=GREEN, sleeve=GREEN, brake=BROWN,
               keel='#353b2c', chin='#4b4637', rib=GREEN, iron='#363a35',
               grille='#202521', rubber='#30302c', tyre='#2b2c29', tread='#2b2c29',
               disc_b=BROWN, disc_g=GREEN, nut='#5a594b', optic='#223a41',
               tool='#555443', bore='#121412', amber='#ce831f', clear='#c2c8b9',
               headlight='#e1e3d7', taillight='#a92c27')


def materials():
    m=K.Materials()
    for zone,col in PALETTE.items(): m.add(zone,col,roughness=.8)
    return m


def lin(c): return np.array(K.srgb(c)[:3],np.float32)


def sat(x): return np.clip(x,0,1)


def sheets():
    brow=Sheet(-1.18,1.18,1.12,1.50,ppm=260)
    brow.text('00-0000',(-.58,1.34),.114,lin('#ecebd9'),weight=.135)
    pts=[]
    for a in np.linspace(0,math.tau,90,endpoint=False):
        r=.080+.025*math.cos(5*a)-.008*math.cos(10*a)
        pts.append((.55+r*math.sin(a),1.32+r*.86*math.cos(a)))
    brow.stroke(pts,.012,lin('#ecebd9'),closed=True)
    for s in (-1,1): brow.groove([(s*1.15,1.458),(s*.89,1.159)],width=.016)
    rear=Sheet(-.48,.48,1.0,1.27,ppm=320)
    rear.text('00-0000',(0,1.114),.073,lin('#d7d8c9'),direction=-1,weight=.14)
    return brow,rear


def smooth(t):
    t=sat(t)
    return t*t*(3-2*t)


def camouflage(x,y,z):
    # Brown fields anchored in rest-space (nose, first wheel, middle, high
    # stern, upper cheeks). The field and its feather use metre units.
    u=x+.107*np.sin(2.7*z+.9*y)+.076*np.sin(3.2*y-1.4*z)
    v=y+.053*np.sin(2.1*x-1.6*z)
    w=z+.131*np.sin(1.8*x+1.31*y)+.061*np.sin(3.9*x-1.92*y)
    f=np.full_like(x,-4.)
    for cx,cy,cz,rx,ry,rz,skew in (
        (1.37,1.45,2.55,.94,.75,.61,.21),(.60,1.84,2.51,.76,.57,.61,-.30),
        (-1.28,1.37,3.22,1.19,.95,1.01,.29),(-.38,1.68,3.54,.77,.64,.65,-.30),
        (1.35,1.48,-.79,.90,.69,1.17,.33),(.49,1.78,-.89,.92,.57,.93,-.30),
        (-1.28,1.48,-.68,.95,.78,1.14,-.40),(-.41,1.71,-.59,.91,.62,.95,.34),
        (1.37,1.79,-2.95,.76,.21,.32,.31),(-1.43,1.59,-2.99,.89,.37,.56,-.27),
        (-.39,1.52,-3.43,1.12,.57,.84,.15),(-.69,1.76,-3.03,.79,.45,.75,-.24),
        (1.13,2.36,.52,.88,.48,.85,.20),(-1.10,2.35,.48,.89,.46,.90,-.18),
        (.48,2.49,.09,.97,.56,1.08,.29),(-.53,2.35,-.37,.99,.56,.92,-.17),
        (1.03,2.28,-.88,.77,.51,.78,-.31),(-1.11,2.26,-1.02,.79,.55,.81,.26),
        (.06,2.29,3.89,.77,.58,.66,.26)):
        dx=u-cx; dz=w-cz+skew*dx; dy=v-cy
        field=1-(dx/rx)**2-(dy/ry)**2-(dz/rz)**2
        # Normalize by the local gradient; a small stern fleck shouldn't have
        # a thinner paint edge than the large patch across the wheel station.
        grad=2*np.sqrt((dx/rx**2+skew*dz/rz**2)**2+(dy/ry**2)**2+(dz/rz**2)**2)
        f=np.maximum(f,field/np.maximum(grad,.25))
    # Shape the transom edge in metres: a brown sheet over the door/deck
    # joint, with the +X third and the two low outer corners left green.
    stern=smooth((-z-3.10)/.23)
    f=np.minimum(f,(.49+.09*np.sin(5*y)-x)+(1-stern)*4)
    f=np.minimum(f,(y-.966-.30*smooth((abs(x)-.40)/.89))+(1-stern)*4)
    # Keep the lower surfaces under the forward cheek points green. Do this in
    # space, not by material, so the colour still crosses the belt naturally.
    forward=smooth((z+.23)/.43)*smooth((1.57-z)/.34)*smooth((y-1.76)/.06)
    f=np.minimum(f, (y-2.047-.031*np.sin(3*x+2*z))+(1-forward)*3.0)
    c=lin(GREEN)+(lin(BASE)-lin(GREEN))*smooth((f+.043)/.040)[:,None]
    return c+(lin(BROWN)-c)*smooth((f+.003)/.042)[:,None]


def bolts(rgb,height,mask,distance,r=.013):
    # Rounded cap in the height channel; thin dirty seat just outside the head.
    cap=sat(1-(distance/r)**2)
    seat=np.exp(-((distance-r)/.0045)**2)
    rgb[mask]*=(1+.075*cap-.22*seat)[:,None]
    height[mask]+=.0050*cap-.0013*seat


def deck_inlays(x,z,rgb,h,rough):
    # Paint recesses below the skin without placing a second mesh on the deck.
    # All masks use deck plan coordinates, so they cross the slope breaks.
    def panel(x0,x1,z0,z1):
        inside=(x>=x0)&(x<=x1)&(z>=z0)&(z<=z1)
        edge=np.minimum(np.minimum(x-x0,x1-x),np.minimum(z-z0,z1-z))
        groove=inside*smooth((.013-edge)/.007)
        rgb[:]*=1-.47*groove[:,None]; h[:]-=.003*groove
    panel(-.81,-.20,2.18,2.91)
    for cx in (-.70,-.51,-.32):
        mount=(abs(x-cx)<.084)&(abs(z-2.774)<.050)
        lens=(abs(x-cx)<.069)&(abs(z-2.789)<.027)
        rgb[mount]*=.75; h[mount]-=.002
        rgb[lens]=lin(PALETTE['optic']); rough[lens]=.26
    for xa,xb,za,zb,n in ((.106,1.285,1.30,1.84,12),(.106,.765,1.855,2.53,9),
                           (.780,1.285,1.855,2.86,16),(.112,.765,2.545,3.17,0),(.780,1.285,2.875,3.17,0)):
        panel(xa,xb,za,zb)
        if not n: continue
        k=(x>xa+.052)&(x<xb-.052)&(z>za+.049)&(z<zb-.049)
        pitch=(zb-za-.098)/n
        blade=smooth((.012-abs(((z[k]-za-.049)/pitch)%1-.5)*pitch)/.006)
        rgb[k]=lin(PALETTE['grille'])*(1-blade[:,None])+rgb[k]*blade[:,None]*.89
        h[k]-=.0035*(1-blade)
    return rgb,h,rough


def shade(R,ppm,size):
    # Work in horizontal strips: peak memory stays bounded even on the 2048 atlas.
    base=np.zeros((size,size,3),np.float32); base[:]=lin(GREEN)
    orm=np.ones_like(base); orm[...,2]=0
    emit=np.zeros_like(base); height=np.zeros((size,size),np.float32)
    brow,rear=sheets()
    zones=R['zones']; ids={name:i for i,name in enumerate(zones)}
    for start in range(0,size,96):
        sl=slice(start,start+96); iy,ix=np.nonzero(R['fill'][sl]); iy+=start
        if not len(ix): continue
        x,y,z=R['pos'][iy,ix].T; nx,ny,nz=R['nrm'][iy,ix].T
        zi=R['zone'][iy,ix]
        def zone(*ns): return np.isin(zi,[ids[n] for n in ns if n in ids])
        rgb=np.empty((len(x),3),np.float32); h=np.zeros_like(x); rough=np.full_like(x,.8); metal=np.full_like(x,.08)
        for name,col in PALETTE.items(): rgb[zone(name)]=lin(col)
        cam=zone('bustle','door','plate','cheek','shield','sleeve','brake','keel','chin','rib')
        rgb[cam]=camouflage(x[cam],y[cam],z[cam])
        k=zone('plate')&(ny>.86)&(z>1.28)&(z<3.20)
        if k.any(): rgb[k],h[k],rough[k]=deck_inlays(x[k],z[k],rgb[k],h[k],rough[k])
        muzzle=zone('brake'); rgb[muzzle]*=(1-.22*smooth((z[muzzle]-TRUN[2]-3.78)/.37))[:,None]
        rgb[zone('chin','keel')]*=.73
        # Construction joints on the shoulder and at actual armour station
        # breaks, never inset rounded boxes drawn over an uninterrupted face.
        k=zone('plate')&(abs(nx)>.84)&(abs(x)>1.446)&(y>1.235)
        if k.any():
            zz=z[k]; yy=y[k]; roof=np.interp(zz,[q[0] for q in DECK],[q[1] for q in DECK])
            foot=np.interp(zz,[-3.25,-3.06,-2.85,2.74,3.15,3.52],[.98,1.13,1.32,1.32,1.28,1.24])
            d=np.abs(yy-foot-.014)
            for seam_z in (-2.92,-.56,1.92,3.57): d=np.minimum(d,abs(zz-seam_z))
            seam=smooth((.010-d)/.006); rgb[k]*=(1-.54*seam[:,None]); h[k]-=.0035*seam
            dz=abs((zz+.175)%.4-.2)
            db=np.hypot(dz,np.minimum(abs(yy-(foot+.049)),abs(yy-(roof-.041))))
            bolts(rgb,h,k,db)
        k=zone('bustle')&(abs(nx)>.50)
        if k.any():
            zz=z[k]; yy=y[k]; d=np.full_like(yy,10.)
            for back,front in BUSTLE_DOORS:
                for zc in np.linspace(back+.043,front-.043,max(2,1+round((front-back)/.4))):
                    d=np.minimum(d,np.hypot(zz-zc,np.minimum(abs(yy-2.045),abs(yy-2.425))))
            bolts(rgb,h,k,d)
        k=zone('plate')&(nz>.43)&(z>3.25)&(abs(x)<1.43)
        if k.any():
            xx=x[k]; yy=y[k]
            dx=abs((xx+.20)%.40-.20)
            d=np.hypot(dx,np.minimum(abs(yy-1.20),abs(yy-1.416))*1.28)
            bolts(rgb,h,k,d,.012)
        k=zone('door')&(nz<-.85)
        if k.any():
            _,ink,alpha,_=rear.sample(x[k]+.19,y[k]); rgb[k]=rgb[k]*(1-alpha[:,None])+ink
        k=zone('plate')&(z>3.49)&(nz>.35)
        if k.any():
            seam,ink,a,_=brow.sample(x[k],y[k]); rgb[k]=rgb[k]*(1-.48*seam[:,None])*(1-a[:,None])+ink; h[k]-=.003*seam
        k=zone('brake')&(np.abs(nz)<.5)
        if k.any():
            a=np.arctan2(y[k]-TRUN[1],x[k])/math.tau; dist=z[k]-TRUN[2]-3.484
            row=np.floor(dist/.059+.5); axial=dist-row*.059
            angular=((a*10+.5*(row%2)+.5)%1-.5)*math.tau*.070/10
            dot=sat((.0135-np.hypot(axial,angular))/.004)*(row>=0)*(row<8)
            rgb[k]*=1-.89*dot[:,None]; h[k]-=.003*dot
        # Sample the master wheel in radial coordinates. Nothing is shaded by
        # world height on the rubber: that would rotate through the contact patch.
        ry=y-CY; rz=z-AXLES[0]; rad=np.hypot(ry,rz); ang=np.arctan2(rz,ry)
        xx=x-TRACK_HALF; across=abs(xx)
        dust=sat((1.43-y)/.78)*.115
        step=zone('iron','rib')&(abs(x)>1.36)&((abs(z+.10)<.23)|(abs(z-1.49)<.20))&(y<1.24)
        dust[step]+=.044
        disc=zone('disc_b','disc_g','nut'); dust[disc]=.016
        k=zone('disc_b','disc_g')&(abs(nx)>.8)&(across>.163)
        if k.any():
            dy=rad[k]-.095; da=((ang[k]*8/math.tau+.5)%1-.5)*math.tau*.095/8
            d=np.hypot(da,dy); bolt=smooth((.014-d)/.005)
            rgb[k]*=(1+.24*bolt-.23*np.exp(-((d-.014)/.0035)**2))[:,None]
            h[k]+=.0048*bolt
        k=zone('tyre','tread'); rough[k]=.93; metal[k]=0
        if k.any():
            r=rad[k]; a=ang[k]; ax=across[k]; outer=np.sign(xx[k])
            # Embossed concentric mould bands only: linked mirrored instances
            # have no lettering to read backwards. Rubber stays charcoal here.
            bands=np.maximum(sat(1-abs(r-.349)/.004),sat(1-abs(r-.431)/.004))
            h[k]+=.0016*bands; rgb[k]*=(1+.055*bands[:,None])
            shoulder=smooth((ax-.080)/.061)*smooth((r-.477)/.045)
            lug=zone('tread')[k]; dust[k]=.067*shoulder*(.22+.78*lug)
            # Narrow sipes on the actual raised lugs only. Between them the
            # casing and the modelled groove already carry the depth change.
            center=ax<.052
            turn=(a/math.tau*TREAD_COUNT)%TREAD_COUNT
            mid_skew=np.where(np.floor(turn)%2==0,.16,-.16)*(xx[k]+.047)/.094
            outer_phase=np.where(outer<0,.36,.70)+np.where(outer<0,-.24,.24)*np.where(outer<0,(.171-ax)/.115,(ax-.056)/.115)
            phase=(turn-np.where(center,mid_skew,outer_phase))%1
            sipe=lug*smooth((.050-abs(phase-.36))/.033)*smooth((r-.50)/.03)
            h[k]-=.0022*sipe; rgb[k]*=(1-.12*sipe[:,None])
        grain=np.sin(73*z+13*x+31*y)*np.sin(67*x-41*y+37*z)
        rgb=rgb*(1-dust[:,None])+lin(DUST)*dust[:,None]
        rgb*=1+.032*grain[:,None]; h+=.00022*grain
        panel=zone('cheek','bustle')|(zone('plate')&(ny>.75))
        grit=np.sin(117*x+69*y-91*z)*np.sin(83*x-111*y+53*z)
        rough[panel]+=.037*grit[panel]; h[panel]+=.00065*grit[panel]
        k=zone('optic'); rough[k]=.22; metal[k]=.33
        rgb[k]*=(1.18+.23*np.sin(55*y[k]))[:,None]
        k=zone('headlight','taillight','amber','clear'); rough[k]=.24; metal[k]=.11
        if k.any():
            # Moulded lens fluting catches the light without transmission.
            ribs=.5+.5*np.cos(890*x[k]+233*y[k]); rgb[k]*=(.85+.21*ribs[:,None]); h[k]+=.0013*ribs
        k=zone('headlight'); localx=np.minimum(abs(abs(x)-1.208),abs(abs(x)-1.390)); localy=np.minimum(abs(y-.976),abs(y-1.104))
        core=np.exp(-((localx/.039)**2+(localy/.028)**2)); rgb[k]=rgb[k]*(1-.33*core[k,None])+.33*core[k,None]
        emit[iy[k],ix[k]]=rgb[k]*(.035+.31*core[k,None]); k=zone('taillight'); emit[iy[k],ix[k]]=rgb[k]*.24
        base[iy,ix]=rgb; height[iy,ix]=h; orm[iy,ix,1]=rough; orm[iy,ix,2]=metal
    normal=JA.normal_from_height(JA.blur(height,1),1/max(1,ppm*size),1.7)
    normal[~R['fill']]=(.5,.5,1)
    return dict(base=base,orm=orm,emit=emit,normal=normal)


def paint(all_objects,size,workdir):
    # Do not unwrap eight overlapping copies, or assign a material eight times to the same data.
    objs=[]; seen=set()
    for ob in all_objects:
        if ob.data.as_pointer() not in seen:
            objs.append(ob); seen.add(ob.data.as_pointer())
    def density(ob,name):
        if name in ('headlight','taillight','brake','amber','clear'): return 1.6
        if name in ('keel','iron','bore','nut'): return .54
        return 1.0
    os.makedirs(workdir,exist_ok=True)
    ppm=JA.unwrap(objs,density=density,angle=60,margin=.00095)
    tris=JA.triangles(objs)
    small=JA.raster(tris,max(32,size//8),pad=2)
    ao=JA.occlusion(JA.triangles(all_objects),small,reach=.78,rays=12,floor=None)
    del small
    R=JA.raster(tris,size,pad=5)
    arrays=shade(R,ppm,size)
    arrays['orm'][...,0]=.38+.62*JA.resize(ao,size)
    # The wheel is free to spin: suppress directional shadows on the master.
    k=R['obj']==objs.index(bpy.data.objects['tyre_1l']); arrays['orm'][...,0][k]=.92+.08*arrays['orm'][...,0][k]
    files={key:JA.save(arr,os.path.join(workdir,key+'.png'),key in ('base','emit')) for key,arr in arrays.items()}
    armor=JA.material('armor',files)
    keep=('headlight','taillight')
    JA.apply(objs,armor,keep=keep)
    for name in keep:
        old=bpy.data.materials[name]; old.name='build_'+name
        new=JA.material(name,files)
        old.user_remap(new)
    for name in ('armor',*keep):
        nt=bpy.data.materials[name].node_tree
        nt.nodes.active=next(n for n in nt.nodes if n.type=='TEX_IMAGE' and n.image==files['base'])
    print(f'PAINT type16 {size}x{size}, {ppm*size:.0f} px/m, {workdir}')
