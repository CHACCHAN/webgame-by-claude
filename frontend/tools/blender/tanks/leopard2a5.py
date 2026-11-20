"""Round-four Leopard 2A5. Blender background entry point, arguments after --.
--out leo.glb --stage shape --dump leo.npz --render checks --quick --views o_side,o_front
Raw GLB is the input to the game's mesh/texture optimization, not the delivery size.
"""
import argparse
import math
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Matrix
from mathutils.kdtree import KDTree
from mathutils.bvhtree import BVHTree

sys.path.insert(0,str(Path(__file__).resolve().parent))
import tank_kit as T
import jet_kit as J
from tank_scene import VIEWS
import leopard2a5_shape as L
import leopard2a5_paint as skin

DIMS=L.dims()


def build():
    J.clear_scene(); mats=T.materials(); marks=[]
    root,body,turret,gun=T.tank_nodes('leopard2a5',DIMS); rg=L.running_spec()
    objects=[L.hull(rg,marks).build(body,mats)]
    gear=T.running_gear(body,rg,mats); objects.extend(gear['objects'])
    L.add_guides(gear,rg)
    # running_gear supplies the complete assembly but not per-kind seg overrides.
    # Keep its band UVs, nodes and non-road discs; refine just the exposed road rims.
    road={round(z,5):r for z,y,r in rg.road}
    for pivot in gear['nodes']:
        r=road.get(round(T.G(pivot.location)[2],5))
        if r is None: continue
        wheel=pivot.children[0]; old=wheel.data
        part=T.road_wheel(r,rg.wheel_width,rg.tyre_width,rg.tyre_depth,rg.dish_depth,rg.hub_bolts,seg=L.S['road_seg'])
        tmp=part.build(None,mats); wheel.data=tmp.data
        bpy.data.objects.remove(tmp,do_unlink=True); bpy.data.meshes.remove(old)
    objects.extend((L.turret(marks).build(turret,mats),L.gun().build(gun,mats)))
    bpy.context.view_layer.update()
    return root,objects,mats,rg,marks


def _dump(objects,path):
    path=Path(path); path=path if str(path).endswith('.npz') else Path(str(path)+'.npz')
    T.dump(objects,path)
    with np.load(path,allow_pickle=False) as archive: data=dict(archive)
    data['axis']=np.array([DIMS['turretZ'],DIMS['ringY']+DIMS['trunnion'],DIMS['turretZ']+DIMS['trunnionZ']])
    np.savez_compressed(path,**data)


def _pose_check(nodes):
    # Actual posed triangle surfaces, including muzzle reference head, moving
    # cover, fixed cheeks, sight furniture, hatches, fenders and upper deck.
    # Collision is between assemblies, not between joined detail islands.
    turret=nodes['turret']; gun=nodes['gun']; gt=gun.matrix_basis.copy(); tt=turret.matrix_basis.copy()
    # Identify only the authored skirt vertices in the rest mesh, before yaw.
    # The rim is allowed to enter the roof, like the seated race; neither is
    # exempt from the moving gun test. Do not skip a rectangular hull region.
    rim=L.under_skirt(); index=KDTree(len(rim.bm.verts))
    for i,v in enumerate(rim.bm.verts): index.insert(v.co,i)
    index.balance(); rim.bm.free()
    shell=nodes['turret_shell']
    rim_ids={v.index for v in shell.data.vertices if index.find(shell.matrix_world@v.co)[2]<1e-5}
    def tree(key,exclude_seats=False,drop=0.):
        o=nodes[key]; me=o.data; me.calc_loop_triangles(); m=Matrix.Translation(T.B(0,-drop,0))@o.matrix_world
        triangles=me.loop_triangles
        if exclude_seats:
            # The race test uses turret-local coordinates, so it is yaw independent.
            race=L.S['race']; pts=[T.G(v.co) for v in me.vertices]
            def seat(i):
                x,y,z=pts[i]; radius=math.hypot(x,z)
                return (race['low']-DIMS['ringY']-1e-4<=y<=race['high']-DIMS['ringY']+1e-4 and
                        race['inner']-1e-4<=radius<=race['r']+1e-4)
            triangles=[t for t in triangles if not (me.materials[t.material_index].name=='recess' and
                       (all(i in rim_ids for i in t.vertices) or all(seat(i) for i in t.vertices)))]
        return BVHTree.FromPolygons([m@v.co for v in me.vertices],[tuple(t.vertices) for t in triangles],all_triangles=True)
    def check(moving,fixed,label):
        hit=moving.overlap(fixed)
        if hit: raise ValueError(f'{label}: intersecting triangles {hit[:3]}')
    hull=tree('hull_shell'); a=L.S['axis']
    try:
        # Probe both actual surfaces and the deck gap, not just the AABBs
        # (those would incorrectly fill the opening under the bustle).
        for yaw in range(0,360,a['sweep_step']):
            turret.matrix_basis=tt@Matrix.Rotation(math.radians(yaw),4,'Z'); bpy.context.view_layer.update()
            for drop in (0.,a['gap']):
                check(tree('turret_shell',exclude_seats=True,drop=drop),hull,f'yaw={yaw:g} turret/deck gap={drop:g}')
        for yaw in a['traverse_check']:
            turret.matrix_basis=tt@Matrix.Rotation(math.radians(yaw),4,'Z'); bpy.context.view_layer.update()
            fixed=tree('turret_shell')
            for pitch in a['limits']:
                for recoil in (0.,a['recoil']):
                    gun.matrix_basis=gt@Matrix.Rotation(math.radians(-pitch),4,'X')@Matrix.Translation(T.B(0,0,-recoil))
                    bpy.context.view_layer.update(); moving=tree('gun_shell'); pose=f'yaw={yaw:g} elev={pitch:g} recoil={recoil:g}'
                    check(moving,fixed,pose+' gun/turret'); check(moving,hull,pose+' gun/hull')
    finally:
        turret.matrix_basis=tt; gun.matrix_basis=gt; bpy.context.view_layer.update()
    print('POSECHECK gun/turret gun/hull clear at elevation and recoil endpoints, yaw 0/30')


def _contract(root,objects,rg,full):
    n={o.name:o for o in root.children_recursive}; body=n['body']; gun=n['gun']; turret=n['turret']
    if root.name!='leopard2a5' or body.parent!=root or turret.parent!=body or gun.parent!=turret:
        raise ValueError('rig hierarchy mismatch')
    for node,expected in [(turret,(0,DIMS['ringY'],DIMS['turretZ'])),(gun,(0,DIMS['trunnion'],DIMS['trunnionZ']))]:
        if not np.allclose(T.G(node.location),expected,atol=1e-5): raise ValueError('incorrect pivot: '+node.name)
    for name,parent in [('hull_shell',body),('turret_shell',turret),('gun_shell',gun)]:
        if n[name].parent!=parent: raise ValueError('incorrect parent: '+name)
    m=gun.matrix_world.inverted()@n['gun_shell'].matrix_world
    pts=np.array([T.G(m@v.co) for v in n['gun_shell'].data.vertices]); tip=pts[:,2].max()
    if abs(tip-DIMS['barrel'])>1e-4 or np.linalg.norm(pts[abs(pts[:,2]-tip)<1e-5,:2].mean(0))>1e-4:
        raise ValueError(f'muzzle face off datum: {tip}')
    zs=sorted([c[0] for c in (*rg.road,rg.sprocket,rg.idler,*rg.rollers)],reverse=True)
    if len(objects)!=5+2*len(zs) or set(objects)!={o for o in n.values() if o.type=='MESH'}:
        raise ValueError('unexpected mesh census')
    for side in 'lr':
        belt=n['band_'+side]
        if belt.parent!=body or [m.name for m in belt.data.materials]!=['track_'+side]: raise ValueError(belt.name+' contract')
        for i,z in enumerate(zs):
            axle=n[f'roll_{side}{i}']; ch=axle.children
            if axle.parent!=body or len(ch)!=1 or ch[0].type!='MESH' or abs(T.G(axle.location)[2]-z)>1e-5:
                raise ValueError(axle.name+' spin order/hierarchy')
            if full and [m.name for m in ch[0].data.materials]!=['armor']: raise ValueError(axle.name+' material')
    if full:
        used={m for o in objects for m in o.data.materials}
        if {m.name for m in used}!={'armor','track_l','track_r','headlight','taillight'}: raise ValueError('delivery materials mismatch')
        for m in used:
            if any(t.type=='TEX_IMAGE' and t.image is None for t in m.node_tree.nodes): raise ValueError('empty texture in '+m.name)
    return n


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out',type=Path,required=True); ap.add_argument('--dump',type=Path)
    ap.add_argument('--render',type=Path); ap.add_argument('--sheet',type=Path); ap.add_argument('--quick',action='store_true')
    ap.add_argument('--stage',choices=('shape','full'),default='full'); ap.add_argument('--views',help='comma-separated tank_scene view names')
    args=ap.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
    views=[v.strip() for v in args.views.split(',')] if args.views else None
    if views and set(views)-set(VIEWS): ap.error('unknown views; choose from '+', '.join(VIEWS))
    root,objects,mats,rg,marks=build(); nodes=_contract(root,objects,rg,False)
    if args.dump: _dump(objects,args.dump)
    _pose_check(nodes)
    tri={}
    for obj in objects:
        obj.data.calc_loop_triangles(); count=len(obj.data.loop_triangles)
        kind=obj.name
        if kind.startswith('disc_'):
            z=T.G(obj.parent.location)[2]
            kind=('idler' if abs(z-rg.idler[0])<1e-5 else 'drive' if abs(z-rg.sprocket[0])<1e-5
                  else 'carrier' if any(abs(z-c[0])<1e-5 for c in rg.rollers) else 'road')
        tri.setdefault(kind,[]).append(count)
    print('PART_TRIS '+ ' '.join(f'{k}={sum(v)}({len(v)}x)' for k,v in tri.items()))
    if sum(map(sum,tri.values()))>72000: raise ValueError('shape exceeds round-four 72000 triangle budget')
    if args.stage=='full':
        wd=args.out.resolve().parent/'tex-leopard2a5'; T.paint_tracks(mats,rg,wd,metal_tint=L.S['track_tint']); skin.paint(objects,mats,wd,marks)
        _contract(root,objects,rg,True)
    total,_=T.report(root)
    if total>72000: raise ValueError(f'{total} triangles exceeds budget')
    sight=', '.join(f'{x:.3f}' for x in DIMS['sight'])
    print('CONTRACT '+' '.join(f'{k}={DIMS[k]:.3f}' for k in ('turretZ','ringY','trunnion','trunnionZ','barrel'))+f' sight=({sight})')
    T.export(root,args.out); print('GLB',args.out)
    directory=args.render or (args.sheet.parent/'leopard2a5-views' if args.sheet else None)
    if directory:
        T.render_check(root,directory,elev=L.S['axis']['limits'],views=views,quick=args.quick)
        if args.sheet: T.sheet(directory,args.sheet)


if __name__=='__main__':
    main()
