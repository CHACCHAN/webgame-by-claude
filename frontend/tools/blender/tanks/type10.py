"""Type 10 pipeline article: final rig dimensions, provisional hull and turret.

blender --background --factory-startup --python type10.py -- --out type10.glb \
    --stage full --dump type10.npz --render checks --sheet checks/type10.jpg

Use --stage shape --quick for the unpainted geometry review. Exported glTF V
increases aft on the bottom run. Eight 0.165 m pitches = 1.320 m per V unit;
TankInfo.trackV must match this for metric scrolling. The raw GLB is not the
meshopt/WebP delivery asset.
"""
import argparse
import sys
from pathlib import Path

import bpy
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import tank_kit as T
import jet_kit as J


DIMS = dict(hull=(7.5, 3.24, 1.3), turretZ=.2, ringY=1.75, trunnion=.35,
            trunnionZ=1.47, barrel=4., turret=(4.6, 3., .6))
SCHEME = dict(base='#51553a', green='#3b4a2e', brown='#6b5236',
              dust='#aa9471', dust_strength=.12, scale=1.18, seed=10)
ELEV = (-7., 10.)


def _hull(rg, marks):
    # Lower tub stays between the bands. Sponsons clear the loaded upper
    # runs; no great full-width cube occupying the wheel wells underneath.
    parts = [T.prism([(-3.60,.80),(-3.10,.45),(2.90,.45),(3.86,1.14),
                      (3.45,1.29),(-3.60,1.29)],-1.005,1.005),
             T.prism([(-3.60,1.14),(3.76,1.14),(3.90,1.27),(1.78,1.65),
                      (-3.44,1.65),(-3.60,1.54)],-1.56,1.56)]
    skirt = T.side_skirt(rg,-3.30,3.40,1.15,.42,.039,7,.17)
    skirt.mirror_x(); parts.append(skirt)
    for side in (-1,1):
        x = side*rg.skirt_outer
        # Hanger rail and line of skirt fasteners. No per-fastener draw calls.
        parts.append(T.cbox((side*1.565,1.151,.05),(.110,.048,6.68),.009))
        parts.append(T.bolt_row(marks,(x,1.073,-3.13),(x,1.073,3.22),21,
                                radius=.017,height=.005,normal=(side,0,0)))
        for z,r in rg.road:
            arm = [(z-.37,.66),(z-.28,.73),(z+.065,.474),(z+.063,.383),(z-.063,.365)]
            parts.append(T.prism(arm,*sorted((side*.98,side*1.135)),mat='recess'))
        # Lens enclosures sit on the glacis near the outer roof edges, and
        # on the transom. The aft tow eyes carry the overall length datum.
        parts.append(T.lamp_box((side*1.38,1.405,3.55),(.246,.155,.205),'headlight'))
        parts.append(T.lamp_box((side*1.36,1.39,-3.60),(.205,.122,.074),'taillight',(0,0,-1)))
        parts.append(T.tow_hook((side*.79,1.29,-3.60),(0,0,-1),radius=.132,bar=.018))
        T.weld_seam(marks,(side*1.49,1.65,-3.39),(side*1.49,1.65,1.73))
    return T.combine('hull_shell',parts)


def build():
    J.clear_scene()
    mats = T.materials()
    root, body, turret, gun = T.tank_nodes('type10',DIMS)
    rg = T.RunningGear(track_centre=1.30,track_width=.55,track_thickness=.10,pitch=.165,
                       road=((1.95,.33),(.95,.33),(-.05,.33),(-1.05,.33),(-2.05,.33)),
                       wheel_width=.42,tyre_width=.13,tyre_depth=.044,dish_depth=.034,hub_bolts=8,
                       sprocket=(-3.,.62,.32,11,.43),idler=(2.95,.58,.30),
                       rollers=((1.2,.90,.10),(-1.4,.90,.10)),sag=.03,
                       horns=2,horn_height=.075,horn_width=.041,pad_share=.70,skirt_outer=1.62)
    marks=[]
    objects=[_hull(rg,marks).build(body,mats)]
    gear=T.running_gear(body,rg,mats); objects.extend(gear['objects'])
    # Block out the turret behind the trunnion. Its base overlaps the top
    # of a shallow, visible race; it doesn't hover 0.10 m over the deck.
    race=T.Part('traverse_race')
    race.revolve('recess',[(.97,.115),(1.065,.079),(1.065,.034),(1.09,.029),(1.09,0.)],
                 (0,1.624,DIMS['turretZ']),axis=(0,1,0),seg=56,cap0=True,cap1=True)
    # Use a cylindrical race rather than a second box in the silhouette.
    length,width,height=DIMS['turret']; front=DIMS['turretZ']+DIMS['trunnionZ']-.08
    center=(0,2.30-height/2,front-length/2)
    turret_parts=[race,T.cbox(center,(width,height,length),.054)]
    for x in (-1.34,1.34):
        T.weld_seam(marks,(x,2.30,front-length+.13),(x,2.30,front-.13),radius=.010,height=.0028)
    objects.append(T.combine('turret_shell',turret_parts).build(turret,mats))
    trunnion=(0,DIMS['ringY']+DIMS['trunnion'],DIMS['turretZ']+DIMS['trunnionZ'])
    barrel=T.combine('gun_shell',[T.mantlet((0,0,.05),(.73,.39,.43)),
                                  T.gun_barrel(.120,DIMS['barrel'],4,True)])
    objects.append(T.placed(barrel,trunnion).build(gun,mats))
    bpy.context.view_layer.update()
    return root,objects,mats,rg,marks


def _contract(root,objects,full):
    nodes={o.name:o for o in root.children_recursive}; body=nodes['body']; turret=nodes['turret']; gun=nodes['gun']
    if turret.parent!=body or gun.parent!=turret or body.parent!=root:
        raise ValueError('body/turret/gun hierarchy mismatch')
    poses=[(turret,(0,DIMS['ringY'],DIMS['turretZ'])),(gun,(0,DIMS['trunnion'],DIMS['trunnionZ']))]
    for node,expected in poses:
        if not np.allclose(T.G(node.location),expected,atol=1e-5): raise ValueError(f'{node.name}: incorrect pivot')
    mu=max(T.G(gun.matrix_world.inverted() @ o.matrix_world @ v.co)[2]
           for o in gun.children_recursive if o.type=='MESH' for v in o.data.vertices)
    if abs(mu-DIMS['barrel'])>.0001: raise ValueError(f'muzzle not at barrel datum: {mu}')
    for side in ('l','r'):
        belt=nodes['band_'+side]
        if belt.parent!=body or [m.name for m in belt.data.materials]!=['track_'+side]:
            raise ValueError(f'{side}: track mesh/material contract')
        for i in range(9):
            axle=nodes[f'roll_{side}{i}']
            if axle.parent!=body or len(axle.children)!=1 or axle.children[0].type!='MESH':
                raise ValueError(f'{axle.name}: invalid spin hierarchy')
            if full and [m.name for m in axle.children[0].data.materials]!=['armor']:
                raise ValueError(f'{axle.name}: not mergeable into one armor draw')
    if full:
        used={m.name for o in objects for m in o.data.materials}
        if used!={'armor','track_l','track_r','headlight','taillight'}: raise ValueError(f'Unexpected delivered materials: {used}')


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out',type=Path,required=True); ap.add_argument('--render',type=Path)
    ap.add_argument('--quick',action='store_true'); ap.add_argument('--dump',type=Path)
    ap.add_argument('--sheet',type=Path); ap.add_argument('--stage',choices=('shape','full'),default='full')
    args=ap.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
    root,objects,mats,rg,marks=build()
    if args.dump: T.dump(objects,args.dump)
    if args.stage=='full':
        wd=args.out.resolve().parent/'tex-type10'
        T.paint_tracks(mats,rg,wd)
        T.paint_tank(objects,mats,SCHEME,2048,wd,density=lambda ob,zone: .72 if ob.name.startswith('disc_') else 1.,marks=marks)
    _contract(root,objects,args.stage=='full')
    total,_=T.report(root)
    if total>90000: raise ValueError(f'{total} triangles exceeds the 90k budget')
    T.export(root,args.out); print('GLB',args.out)
    renderdir=args.render or (args.sheet.parent/'type10-views' if args.sheet else None)
    if renderdir:
        T.render_check(root,renderdir,elev=ELEV,quick=args.quick)
        if args.sheet: T.sheet(renderdir,args.sheet)


if __name__=='__main__':
    main()
