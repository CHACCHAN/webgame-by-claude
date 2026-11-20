"""Build the Abrams in its neutral game pose. Pass script arguments after --.
Use --stage shape --quick for fitting; default full bakes the delivery atlas.
"""
import argparse
import sys
from pathlib import Path

import bpy
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import tank_kit as T
import jet_kit as J
import m1a2_shape as S
import m1a2_parts as P

DIMS = S.ST['dims']
ELEV = (-10., 20.)
SCHEME = dict(base='#b89c64', green='#b0945c', brown='#bca16e', dust='#c7ac79',
              dust_strength=.10, scale=1.6, seed=11)


def build():
    J.clear_scene()
    mats = T.materials()
    root, body, turret, gun = T.tank_nodes('m1a2', DIMS)
    rg = T.RunningGear(**S.ST['gear'])
    marks = []
    objects = [S.hull(marks).build(body,mats), S.turret().build(turret,mats), S.gun().build(gun,mats)]
    gear = T.running_gear(body,rg,mats)
    # Keep the kit's pivots, radius properties and both UV-mapped belts. Swap
    # only the axle-local mesh data, leaving no extra objects or draw calls.
    roles={z:'road' for z,r in rg.road}; roles.update({rg.sprocket[0]:'sprocket',rg.idler[0]:'idler'})
    roles.update({r[0]:'roller' for r in rg.rollers}); st=S.ST['discs']
    for axle in gear['nodes']:
        x,y,z=T.G(axle.location); kind=roles[min(roles,key=lambda v:abs(v-z))]
        obj=axle.children[0]; temp=P.disc(kind,1 if x>0 else -1,rg,st).build(None,mats)
        old=obj.data; obj.data=temp.data; bpy.data.objects.remove(temp,do_unlink=True)
        bpy.data.meshes.remove(old); obj.data.name=obj.name
        n=J.tris_of(obj)
        if n>{'road':1300,'idler':1400,'sprocket':1800,'roller':500}[kind]:
            raise ValueError(f'{obj.name} ({kind}): {n} triangles')
        if kind=='road' and abs(max(abs(x+v.co.x) for v in obj.data.vertices)-st['hub_x'])>1e-4:
            raise ValueError(f'{obj.name}: outer cap station mismatch')
    objects.extend(gear['objects'])
    bpy.context.view_layer.update()
    return root,objects,mats,rg,marks


def _stations(root,rg):
    nodes = {o.name:o for o in root.children_recursive}
    gun, shell = nodes['gun'], nodes['gun_shell']
    pts=np.asarray([T.G(shell.matrix_world @ v.co) for v in shell.data.vertices])
    tip=pts[:,2].max(); rim=pts[np.abs(pts[:,2]-tip)<1e-5]; muzzle=(rim.min(0)+rim.max(0))/2
    datum=(0,DIMS['ringY']+DIMS['trunnion'],DIMS['turretZ']+DIMS['trunnionZ']+DIMS['barrel'])
    if not np.allclose(muzzle,datum,rtol=0,atol=1e-4): raise ValueError(f'Muzzle centre {muzzle} != {datum}')
    print('STATIONS road_z',*[f'{z:.3f}' for z,r in rg.road], 'cap_abs_x',S.ST['discs']['hub_x'],
          'hub_y',round(rg.road[0][-1]+rg.track_thickness,3))
    print('STATIONS sprocket_zyr',rg.sprocket[:3],'idler_zyr',rg.idler[:3])
    print('STATIONS muzzle_xyz',tuple(np.round(muzzle,4).tolist()),'bore_y',round(T.G(gun.matrix_world.translation)[1],4),
          'evacuator_taper_z',S.ST['gun']['taper_z'])
    rings=S.cheek_rings()
    for label,row in zip(('keel','bevel','roof'),rings):
        for side in (-1,1):
            corners=[tuple(round(v,4) for v in (side*x,y,z)) for x,y,z in row[1:3]]
            print('STATIONS cheek',label,'L' if side>0 else 'R','inner_outer_xyz',*corners)


def _contract(root,objects,full):
    nodes = {o.name:o for o in root.children_recursive}
    body,turret,gun = (nodes[n] for n in ('body','turret','gun'))
    if (root.name!='m1a2' or root.parent or body.parent!=root or turret.parent!=body or gun.parent!=turret):
        raise ValueError('Unexpected m1a2/body/turret/gun hierarchy')
    for node,loc in ((root,(0,0,0)),(body,(0,0,0)),(turret,(0,DIMS['ringY'],DIMS['turretZ'])),
                     (gun,(0,DIMS['trunnion'],DIMS['trunnionZ']))):
        if not np.allclose(T.G(node.location),loc,rtol=0,atol=1e-5):
            raise ValueError(f'{node.name}: incorrect pivot {T.G(node.location)}')
    for name,parent in (('hull_shell',body),('turret_shell',turret),('gun_shell',gun)):
        if nodes[name].type!='MESH' or nodes[name].parent!=parent:
            raise ValueError(f'{name}: incorrect assembly')
    mesh = nodes['gun_shell']; m = gun.matrix_world.inverted() @ mesh.matrix_world
    muzzle = max(T.G(m @ v.co)[2] for v in mesh.data.vertices)
    if abs(muzzle-DIMS['barrel'])>.0001:
        raise ValueError(f'Muzzle at {muzzle}, expected {DIMS["barrel"]}')
    n = len(S.ST['gear']['road'])+2+len(S.ST['gear']['rollers'])
    expected = {'body','turret','gun','hull_shell','turret_shell','gun_shell'}
    for side in ('l','r'):
        belt=nodes['band_'+side]; expected.add(belt.name)
        if belt.type!='MESH' or belt.parent!=body or [m.name for m in belt.data.materials]!=['track_'+side]:
            raise ValueError(f'{belt.name}: track contract')
        for i in range(n):
            suffix = side+str(i); roll=nodes['roll_'+suffix]; disc=nodes['disc_'+suffix]
            expected.update((roll.name,disc.name))
            if roll.type!='EMPTY' or roll.parent!=body or list(roll.children)!=[disc] or disc.type!='MESH':
                raise ValueError(f'{roll.name}: axle hierarchy')
            if full and [m.name for m in disc.data.materials]!=['armor']:
                raise ValueError(f'{disc.name}: not mergeable into armor draw')
    if set(nodes)!=expected or set(objects)!={o for o in nodes.values() if o.type=='MESH'}:
        raise ValueError('Unexpected nodes or mesh inventory')
    if full:
        keep={'armor','track_l','track_r','headlight','taillight'}
        used={m.name for o in objects for m in o.data.materials}
        if used!=keep: raise ValueError(f'Unexpected delivered materials: {used}')
        for name in ('hull_shell','turret_shell','gun_shell'):
            want={'armor','headlight','taillight'} if name=='hull_shell' else {'armor'}
            if {m.name for m in nodes[name].data.materials}!=want:
                raise ValueError(f'{name}: shell material slots')


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out',type=Path,required=True); ap.add_argument('--render',type=Path)
    ap.add_argument('--quick',action='store_true'); ap.add_argument('--dump',type=Path)
    ap.add_argument('--sheet',type=Path); ap.add_argument('--stage',choices=('shape','full'),default='full')
    args=ap.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
    root,objects,mats,rg,marks=build()
    _contract(root,objects,False)
    _stations(root,rg)
    if args.dump: T.dump(objects,args.dump)
    if args.stage=='full':
        wd=args.out.resolve().parent/'tex-m1a2'
        T.paint_tracks(mats,rg,wd,metal_tint='#6a5a43')
        T.paint_tank(objects,mats,SCHEME,2048,wd,
                     density=lambda ob,zone: .72 if ob.name.startswith('disc_') else 1.,marks=marks)
        _contract(root,objects,True)
    total,_=T.report(root)
    if total>80000: raise ValueError(f'{total} triangles exceeds the round-2 80k budget')
    T.export(root,args.out); print('GLB',args.out,'raw_bytes',args.out.stat().st_size)
    renderdir=args.render or (args.sheet.parent/'m1a2-views' if args.sheet else None)
    if renderdir:
        T.render_check(root,renderdir,elev=ELEV,quick=args.quick)
        if args.sheet: T.sheet(renderdir,args.sheet)


if __name__=='__main__':
    main()
