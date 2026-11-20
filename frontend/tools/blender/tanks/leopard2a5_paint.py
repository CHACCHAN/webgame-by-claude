"""One rest-pose Bundeswehr skin; lettering is projected in metres, not UV pixels."""
from pathlib import Path

import numpy as np
import bpy
import tank_atlas as A
import jet_atlas as JA
from leopard2a5_shape import S

GREEN='#505A41'; BROWN='#605044'; BLACK='#272926'; DUST='#918770'


def _field(p, lattice):
    # Two reproducible periodic 3-D value-noise fields. Smooth interpolation
    # keeps the lobes round even where a panel crosses a lattice boundary.
    cell=np.floor(p).astype(np.int32); t=p-cell; t=t*t*(3-2*t); n=len(lattice)
    value=np.zeros(len(p),np.float32)
    for i in (0,1):
        for j in (0,1):
            for k in (0,1):
                sample=lattice[(cell[:,0]+i)%n,(cell[:,1]+j)%n,(cell[:,2]+k)%n]
                value+=sample*(t[:,0] if i else 1-t[:,0])*(t[:,1] if j else 1-t[:,1])*(t[:,2] if k else 1-t[:,2])
    return value


def _cross(u,v,size):
    # Flared cross with scooped sides. Return outer and inset coverage.
    a,b=np.maximum(abs(u),abs(v))*2/size,np.minimum(abs(u),abs(v))*2/size
    # Erode the SAME outline by a fixed stroke; scaling the shape instead
    # pinches the white edging away halfway along each arm.
    dist=np.maximum(a-1,b-(.19+.23*a*a))
    return 1-A._step(-.018,.018,dist),1-A._step(-.113,-.077,dist)


_DIGITS={
    '2':[((.10,.82),(.23,.94)),((.23,.94),(.70,.94)),((.70,.94),(.85,.78)),
         ((.85,.78),(.84,.62)),((.84,.62),(.13,.12)),((.13,.12),(.86,.12))],
    '4':[((.71,.96),(.09,.39)),((.09,.39),(.94,.39)),((.72,.96),(.72,.06))],
    '1':[((.20,.75),(.56,.95)),((.56,.95),(.56,.08)),((.23,.08),(.87,.08))]}


def _number(u,v,h):
    v=v/h+.5; line=np.zeros_like(u); width=h*.63
    for i,digit in enumerate('241'):
        x=(u-(i-1)*width*1.17)/width+.5
        for (ax,ay),(bx,by) in _DIGITS[digit]:
            dx=(bx-ax)*width/h; dy=by-ay; px=(x-ax)*width/h; py=v-ay
            t=np.clip((px*dx+py*dy)/(dx*dx+dy*dy),0,1)
            dist=np.hypot(px-t*dx,py-t*dy)
            line=np.maximum(line,1-A._step(.042,.061,dist))
    return line


def _stencils(rgb,p,n,oid,objs):
    st=S['insignia']; x,y,z=p.T
    hull=objs.index('hull_shell'); turret=objs.index('turret_shell'); white=A._rgb('#E9E7D9'); ink=A._rgb('#262822')
    for side in (True,False):
        u=z if side else x; uc,yc,size=st['side' if side else 'rear']
        facing=((oid==turret)&(n[:,0]*np.sign(x)>.72)) if side else ((oid==hull)&(n[:,2]<-.75)&(z<S['stern']['transom'][0][0]+.01))
        mask=facing&(abs(u-uc)<size*.53)&(abs(y-yc)<size*.53)
        if mask.any():
            outline,inside=_cross(u[mask]-uc,y[mask]-yc,size)
            rgb[mask]=A._mix(A._mix(rgb[mask],white,outline),ink,inside)
    lamp=S['stern']; lx,ly,lz=lamp['lamp']; w,h,d=lamp['strip_size']; xc=lx-lamp['strip_dx']+.25*w
    lens=(oid==hull)&(abs(abs(x)-xc)<w*.25)&(abs(y-ly)<h*.51)&(abs(z-lz)<d)&(n[:,2]<-.8)
    rgb[lens]=A._rgb('#B77C49')
    zc,yc,h=st['number']; mask=(oid==turret)&(n[:,0]*np.sign(x)>.72)&(abs(z-zc)<h*1.3)&(abs(y-yc)<h*.55)
    if mask.any():
        # +Z is screen-left when viewed from +X; read correctly from either flank.
        rgb[mask]=A._mix(rgb[mask],white,_number(-(z[mask]-zc)*np.sign(x[mask]),y[mask]-yc,h))


def _maps(tris,raster,ao,names,marks,ppm):
    # Reuse the kit's plate edges, signed mark relief, AO, ORM and normal
    # exactly once. Neutral white, no kit colour or dust: its output for a
    # painted texel is then the scalar wear/relief/light modulation.
    sc=dict(A.DEFAULT_SCHEME,base='#ffffff',green='#ffffff',brown='#ffffff',dust_strength=0.)
    base,orm,normal=A._hull_maps(tris,raster,ao,sc,{},marks,ppm)
    fill=raster['fill']; zone=raster['zone']; pid=tris[-1].index('tank_paint'); gid=tris[-1].index('glass_dark')
    rng=np.random.default_rng(295); grids=rng.random((3,32,32,32),dtype=np.float32)
    wheel=np.array([name.startswith('disc_') for name in names]); dust=A._rgb(DUST)
    for row in range(0,len(fill),96):
        sl=slice(row,row+96); valid=fill[sl]; zz=zone[sl][valid]; p=raster['pos'][sl][valid]; oid=raster['obj'][sl][valid]
        if not len(p): continue
        rgb=base[sl][valid]; painted=zz==pid; q=p[painted]; ids=oid[painted]; norm=raster['nrm'][sl][valid][painted]
        om=orm[sl][valid]
        if len(q):
            # Rotate the sampling frame to avoid rectangular alignment with plates.
            coord=np.column_stack((.80*q[:,0]+.60*q[:,2],q[:,1],-.60*q[:,0]+.80*q[:,2]))
            # Independent, broad fields with a low-amplitude domain warp. No
            # periodic longitudinal phase, so roof patches can end or branch.
            coord*=S['camo_frequency']
            warp=_field(coord*.93,grids[2])-.5
            coord=coord*np.array([.88,1.13,.86])+warp[:,None]*np.array([.39,-.27,.31])
            umber=.84*_field(coord,grids[0])+.16*_field(coord*1.85,grids[1])
            tar=.88*_field(coord*.94,grids[1])+.12*_field(coord*1.72,grids[2])
            brown=A._step(.557,.566,umber); black=A._step(.625,.635,tar)
            brown[wheel[ids]]=0; black[wheel[ids]]=0
            om[painted,1]+=(.89-om[painted,1])*black
            col=A._mix(A._rgb(GREEN),A._rgb(BROWN),brown); col=A._mix(col,A._rgb(BLACK),black)
            _stencils(col,q,norm,ids,names); rgb[painted]*=col
        dirt=.078*(1-A._step(.19,1.54,p[:,1]))*(.7+.3*_field(p*2.39,grids[2])); dirt[zz==gid]=0
        base[sl][valid]=A._mix(rgb,dust,dirt); om[:,1]+=(.95-om[:,1])*dirt; om[:,2]*=1-dirt; orm[sl][valid]=om
    return base,orm,normal


def paint(objects,mats,workdir,marks,size=2048):
    body=[o for o in objects if not o.name.startswith('band_')]; names=[o.name for o in body]
    bpy.context.view_layer.update()
    ppm=JA.unwrap(body,density=lambda o,zone:.67 if o.name.startswith('disc_') else 1.,angle=52.)
    tris=JA.triangles(body,skip=A.KEEP); low=JA.raster(tris,min(512,size//4),pad=3)
    ao=JA.occlusion(JA.triangles(objects),low,reach=1.1,rays=16,floor=0.); del low
    ao=JA.blur(JA.resize(ao,size),1); raster=JA.raster(tris,size)
    files=A._save(workdir,'leo_',*_maps(tris,raster,ao,names,marks,ppm))
    sizes={k:Path(im.filepath_raw).stat().st_size for k,im in files.items()}
    print('ATLAS_PNG_BYTES',*(f'{k}={v}' for k,v in sizes.items()),f'total={sum(sizes.values())}')
    mat=JA.material('armor',files); mat.diffuse_color=A.K.srgb(GREEN)
    mat.node_tree.nodes.active=next(n for n in mat.node_tree.nodes if getattr(n,'image',None)==files['base'])
    mats.mats['armor']=mat; JA.apply(body,mat,keep=A.KEEP)
    return mat
