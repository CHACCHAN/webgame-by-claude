"""Build the Type 16 game asset; pass build options after Blender's -- separator."""
import argparse
import os
import sys

HERE=os.path.dirname(os.path.abspath(__file__))
sys.path[:0]=[HERE,os.path.abspath(os.path.join(HERE,'..','jets'))]

import bpy
import numpy as np
import jet_kit as K
import jet_atlas as JA
import type16_shape as S
import type16_wheels as W
import type16_paint as P


def build():
    K.clear_scene()
    mats=P.materials()
    root=K.node('type16'); body=K.node('body',root)
    turret=K.node('turret',body,S.RING); gun=K.node('gun',turret,S.TRUN)
    objs=S.build(body,turret,gun,mats)+W.build(body,mats)
    bpy.context.view_layer.update()
    return root,objs


def geometry_check(objs,path):
    # One rest-space triangle pass serves both the rig preflight and optional dump.
    pos,_,_,zone,owner,zones=JA.triangles(objs)
    classes=np.array([3 if o.parent.name.startswith('spin_') else {'body':0,'turret':1,'gun':2}[o.parent.name] for o in objs],np.int8)
    cl=classes[owner]
    nose=pos[cl==2,:,2].max()
    if abs(nose-S.TRUN[2]-4.15)>1e-4: raise ValueError(f'Gun subtree ends at {nose}, expected 4.64')
    if len(pos)>90000: raise ValueError(f'Triangle budget exceeded: {len(pos)}')
    wheels=[o for o in objs if o.parent.name.startswith('spin_')]
    if len(wheels)!=8 or len({o.data.as_pointer() for o in wheels})!=1: raise ValueError('Expected eight linked wheels')
    per_wheel=int(np.count_nonzero(owner==objs.index(wheels[0])))
    if per_wheel>4000: raise ValueError(f'Wheel master exceeds 4000 triangles: {per_wheel}')
    def pivot(node,xyz):
        if not np.allclose(K.G(node.matrix_world.translation),xyz,atol=1e-5,rtol=0):
            raise ValueError('Wrong pivot position: '+node.name)
        if not np.allclose(np.array(node.matrix_world.to_3x3()),np.eye(3),atol=1e-5,rtol=0):
            raise ValueError('Non-identity pivot axes: '+node.name)
    pivot(bpy.data.objects['turret'],S.RING); pivot(bpy.data.objects['gun'],S.TRUN)
    for o in wheels:
        y=pos[owner==objs.index(o),:,1]; spin=o.parent; key=spin.name[5:]
        c=(W.TRACK_HALF*(1 if key[1]=='l' else -1),W.CY,S.AXLES[int(key[0])-1])
        pivot(spin,c); pivot(spin.parent,c)
        if abs(y.max()-(W.CY+.56))>1e-4 or abs(y.min()-(W.CY-.56))>1e-4: raise ValueError('Bad wheel extent: '+o.name)
    print(f'WHEELS {per_wheel} tris/instance x8 = {8*per_wheel} (limit 4000 each)')
    print(f'RIG type16: wheels=8 radius=0.560 muzzle_world_z={nose:.3f} muzzle_local_z={nose-S.TRUN[2]:.3f}')
    if path:
        os.makedirs(os.path.dirname(os.path.abspath(path)),exist_ok=True)
        np.savez_compressed(path,P=pos.astype(np.float32),O=owner.astype(np.int16),names=np.array([o.name for o in objs]),
                            N=cl,Z=zone.astype(np.int16),zones=np.array(zones),turret_origin=np.array(S.RING,np.float32),gun_origin=np.array(S.TRUN,np.float32))
        print('DUMP',path,len(pos),'triangles')


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out'); ap.add_argument('--render'); ap.add_argument('--dump')
    ap.add_argument('--stage',choices=('shape','full'),default='full')
    ap.add_argument('--views',default='',help='comma-separated check view names')
    ap.add_argument('--sheet',metavar='FILE',help='shared tank contact sheet (default for all views: contact.jpg)')
    ap.add_argument('--quick',action='store_true',help='use Workbench for check renders')
    ap.add_argument('--size',type=int,default=2048,help='square atlas size in pixels')
    a=ap.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
    if a.sheet and not a.render: ap.error('--sheet requires --render')
    if a.size<64: ap.error('--size must be at least 64')
    root,objs=build()
    geometry_check(objs,a.dump)
    full=a.stage=='full'
    if full:
        anchor=os.path.abspath(a.out or a.render or a.dump or 'type16.glb')
        P.paint(objs,a.size,os.path.join(os.path.dirname(anchor),'tex-type16'))
    total,used=K.report(root); K.lamp_report(root)
    if full and used!=['armor','headlight','taillight']:
        raise ValueError(f'Unexpected game materials: {used}')
    if a.out:
        out=os.path.abspath(a.out); os.makedirs(os.path.dirname(out),exist_ok=True)
        K.export_glb(out,root); print('GLB',out)
    if a.render:
        import type16_scene
        type16_scene.render_all(root,a.render,[v.strip() for v in a.views.split(',') if v.strip()],quick=a.quick or not full,painted=full,sheet=a.sheet)


if __name__=='__main__': main()
