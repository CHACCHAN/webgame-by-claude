"""Build the T-14. Use --stage shape for photo fitting; full bakes the delivery atlas.
The belt scroll is eight 0.17 m pitches per UV tile. Use the report for actual
bounding dimensions; hull length in DIMS is not length over the level gun.
"""
import argparse
import sys
from pathlib import Path

import bpy
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import tank_kit as T
import jet_kit as J
import t14_shape as shape


DIMS = dict(hull=(8.7,3.9,1.5), turretZ=0.0, ringY=2.05, trunnion=.10,
            trunnionZ=1.41, barrel=4.96, turret=(4.25,2.72,.68))
SCHEME = dict(base='#4d5242', green='#4a5140', brown='#525443', dust='#9b8f74',
              dust_strength=.10, scale=1.6, seed=14)
ELEV = (-7., 15.)


def _carrier_lod(gear,rg):
    """Retain the kit's rig and silhouette; spend fewer triangles on hidden carrier discs."""
    carrier_z = [q[0] for q in rg.rollers]
    for axle in gear['nodes']:
        if not any(abs(T.G(axle.location)[2]-z)<1e-5 for z in carrier_z):
            continue
        ob=next(iter(axle.children)); original=ob.data
        mod=ob.modifiers.new('carrier LOD','DECIMATE'); mod.ratio=.25
        dg=bpy.context.evaluated_depsgraph_get()
        mesh=bpy.data.meshes.new_from_object(ob.evaluated_get(dg),depsgraph=dg)
        ob.modifiers.remove(mod); ob.data=mesh
        if not original.users: bpy.data.meshes.remove(original)


def _arm_clearance(rg,hardware):
    # Inspect exactly the Parts which will be consumed into hull_shell. Absolute
    # x folds right onto left; radii and axial spans are the rolling mesh data.
    k=shape.S['arms']; fixed,stubs=hardware
    pts=np.array([T.G(v.co) for v in fixed.bm.verts]); ax=np.abs(pts[:,0])
    extent=max(ax.max(),max(abs(T.G(v.co)[0]) for v in stubs.bm.verts))
    wheels=[(f'road{i+1}',z,y,r,rg.wheel_width) for i,(z,y,r) in enumerate(rg.road)]
    iz,iy,ir,iw=rg.idler; sz,sy,sr,_,sw=rg.sprocket
    wheels.extend((('idler',iz,iy,ir,iw),('sprocket',sz,sy,sr,sw)))
    worst=float('inf'); nearest=None; eps=1e-6
    for name,z,y,r,width in wheels:
        within=np.abs(ax-rg.track_centre)<=width/2+eps
        if not within.any(): continue
        clearance=np.hypot(pts[within,1]-y,pts[within,2]-z).min()-r-k['margin']
        if clearance<worst: worst,nearest=clearance,name
    # Stub ends intentionally contact the wheel's inner face. They participate
    # in the x-limit check, not the radial exclusion for the arms and housings.
    ok=worst>0 and extent<=k['x_limit']+eps
    print(f'ARM_CLEARANCE {"PASS" if ok else "FAIL"} nearest={nearest} after_margin={worst:.4f} max_abs_x={extent:.4f}')
    if not ok: raise ValueError('static suspension exceeds envelope or intersects a rolling cylinder')


def build():
    J.clear_scene()
    mats=T.materials(); root,body,turret,gun=T.tank_nodes('t14',DIMS)
    rg=shape.gear_spec(); marks=[]
    hardware=shape.suspension(rg); _arm_clearance(rg,hardware)
    objects=[shape.hull(rg,marks,hardware).build(body,mats)]
    gear=T.running_gear(body,rg,mats); _carrier_lod(gear,rg)
    objects.extend(gear['objects'])
    objects.append(shape.turret(DIMS).build(turret,mats))
    objects.append(shape.gun(DIMS).build(gun,mats))
    bpy.context.view_layer.update()
    return root,objects,mats,rg,marks


def _contract(root,objects,full):
    nodes={o.name:o for o in root.children_recursive}
    body=nodes['body']; turret=nodes['turret']; gun=nodes['gun']
    if root.name!='t14' or body.parent!=root or turret.parent!=body or gun.parent!=turret:
        raise ValueError('t14/body/turret/gun hierarchy mismatch')
    for node,pos in ((body,(0,0,0)),(turret,(0,DIMS['ringY'],DIMS['turretZ'])),
                     (gun,(0,DIMS['trunnion'],DIMS['trunnionZ']))):
        if not np.allclose(T.G(node.location),pos,atol=1e-5): raise ValueError(f'{node.name}: incorrect pivot')
    for node,want in ((body,{'hull_shell','band_l','band_r'}),(turret,{'turret_shell'}),(gun,{'gun_shell'})):
        if {c.name for c in node.children if c.type=='MESH'}!=want:
            raise ValueError(f'{node.name}: unexpected mesh children')
    mu=max(T.G(gun.matrix_world.inverted() @ o.matrix_world @ v.co)[2]
           for o in gun.children_recursive if o.type=='MESH' for v in o.data.vertices)
    if abs(mu-DIMS['barrel'])>.0001: raise ValueError(f'muzzle not at barrel datum: {mu}')
    # Same body-frame bore-axis point printed by T.report in its DIMS line.
    muzzle=T.G(body.matrix_world.inverted() @ gun.matrix_world @ T.B(0,0,mu))
    expected=(0,DIMS['ringY']+DIMS['trunnion'],DIMS['turretZ']+DIMS['trunnionZ']+DIMS['barrel'])
    if not np.allclose(muzzle,expected,atol=1e-4,rtol=0): raise ValueError(f'level muzzle: {muzzle} != {expected}')
    for side in ('l','r'):
        belt=nodes['band_'+side]
        if belt.parent!=body or [m.name for m in belt.data.materials]!=['track_'+side]:
            raise ValueError(f'{side}: track mesh/material contract')
        pivots=[f'roll_{side}{i}' for i in range(12)]
        if set(pivots)!={k for k in nodes if k.startswith('roll_'+side)}:
            raise ValueError(f'{side}: expected twelve spin pivots')
        previous=float('inf')
        for name in pivots:
            axle=nodes[name]; z=T.G(axle.location)[2]
            if axle.parent!=body or len(axle.children)!=1 or axle.children[0].type!='MESH' or z>=previous:
                raise ValueError(f'{name}: invalid spin hierarchy or axle order')
            previous=z
            if full and [m.name for m in axle.children[0].data.materials]!=['armor']:
                raise ValueError(f'{name}: not mergeable into one armor draw')
    if full:
        used={m.name for o in objects for m in o.data.materials}
        if used!={'armor','track_l','track_r','headlight','taillight'}:
            raise ValueError(f'Unexpected delivered materials: {used}')
        if any(len(o.data.color_attributes) for o in objects): raise ValueError('unexpected vertex colours')


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out',type=Path,required=True); ap.add_argument('--render',type=Path)
    ap.add_argument('--quick',action='store_true'); ap.add_argument('--dump',type=Path)
    ap.add_argument('--sheet',type=Path); ap.add_argument('--stage',choices=('shape','full'),default='full')
    args=ap.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
    root,objects,mats,rg,marks=build()
    if args.dump: T.dump(objects,args.dump)
    if args.stage=='full':
        wd=args.out.resolve().parent/'tex-t14'
        T.paint_tracks(mats,rg,wd)
        # The shared atlas always mixes three camo fields. Equalise their pigments
        # for this parade finish, retaining the specified dust, AO and steel wear.
        solid={**SCHEME,'green':SCHEME['base'],'brown':SCHEME['base']}
        T.paint_tank(objects,mats,solid,2048,wd,marks=marks,
                     density=lambda ob,zone: .72 if ob.name.startswith('disc_') else 1.)
    _contract(root,objects,args.stage=='full')
    total,_=T.report(root)
    if total>=85000: raise ValueError(f'{total} triangles: build must be under 85k')
    T.export(root,args.out); print('GLB',args.out)
    renderdir=args.render or (args.sheet.parent/'t14-views' if args.sheet else None)
    if renderdir:
        T.render_check(root,renderdir,elev=ELEV,quick=args.quick)
        if args.sheet: T.sheet(renderdir,args.sheet)


if __name__=='__main__':
    main()
