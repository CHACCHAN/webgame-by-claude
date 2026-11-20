"""Shared tank review pictures, plus fixed-scale measuring views of the Type 16."""
import math
from pathlib import Path
from shutil import copyfile

import bpy
from mathutils import Vector
import jet_kit as K
import tank_scene as T

# Separate directory: the kit also writes o_side, o_front and o_top, but its
# black silhouettes are fitted to frame, not calibrated to a metric lattice.
ORTHO={'o_side':((20,2,0),(0,2,0),1200,700),
       'o_front':((0,2,20),(0,2,0),800,700),
       'o_rear':((0,2,-20),(0,2,0),800,700),
       'o_top':((0,20,0),(0,0,0),1200,1100)}
EXTRA={'side_r':((-15.4,2.45,.20),(0,2.05,.20),50),
       'turret':((5.9,4.75,6.5),(0,2.45,.61),48),
       'limits':((8.6,5.4,9.0),(.9,2.12,0),39)}
ALIAS={'front34':'front34_l','side_l':'side','wheels':'gear'}


def grid(sc,keep,cam):
    verts=[]; faces=[]
    def quad(x0,x1,y0,y1,z):
        k=len(verts); verts.extend([(x0,y0,z),(x1,y0,z),(x1,y1,z),(x0,y1,z)])
        faces.append((k,k+1,k+2,k+3))
    quad(-12,12,-12,12,-28.02)
    for i in range(-20,21):
        a=.5*i; w=.006 if i%2==0 else .004
        quad(a-w,a+w,-10,10,-28); quad(-10,10,a-w,a+w,-27.999)
    ob=T._object(sc,keep,bpy.data.meshes.new('Measurement grid')); ob.parent=cam
    ob.data.from_pydata(verts,[],faces); ob.data.update()
    for name,col in [('Paper',(.69,.71,.72)),('Ruler',(.39,.42,.43))]:
        mat=keep(bpy.data.materials.new(name)); mat.diffuse_color=(*col,1)
        ob.data.materials.append(mat)
    for face in list(ob.data.polygons)[1:]: face.material_index=1
    return ob


def supplemental(root,directory,views,quick,painted):
    if not views: return
    (directory/'metric').mkdir(parents=True,exist_ok=True)
    turret=bpy.data.objects['turret']; gun=bpy.data.objects['gun']
    with T._stage() as (sc,keep), T._poses(turret,gun):
        for ob in [root,*root.children_recursive]: sc.collection.objects.link(ob)
        sc.render.engine='BLENDER_WORKBENCH' if quick else 'CYCLES'
        if not quick: sc.cycles.device='CPU'; sc.cycles.samples=32
        sc.view_settings.view_transform='Standard'; sc.view_settings.exposure=0.; sc.view_settings.gamma=1.
        sc.render.resolution_percentage=100; sc.render.pixel_aspect_x=sc.render.pixel_aspect_y=1
        sc.render.image_settings.file_format='PNG'
        cam=T._object(sc,keep,bpy.data.cameras.new('Metric camera')); sc.camera=cam
        cam.data.sensor_width=36; cam.data.sensor_fit='HORIZONTAL'
        board=grid(sc,keep,cam)
        sc.world=keep(bpy.data.worlds.new('Check sky')); sc.world.use_nodes=True
        bg=(.35,.4,.48); sc.world.node_tree.nodes['Background'].inputs['Color'].default_value=(*bg,1); sc.world.color=bg
        sun=T._object(sc,keep,bpy.data.lights.new('Check sun','SUN'))
        sun.data.energy=2.2; sun.data.angle=math.radians(12)
        sh=sc.display.shading; sh.background_type='WORLD'; sh.light='STUDIO'
        sh.color_type='TEXTURE' if painted else 'MATERIAL'; sh.show_cavity=sh.show_shadows=True
        floor=T._object(sc,keep,bpy.data.meshes.new('Check floor'))
        floor.data.from_pydata([(-80,-80,-.018),(80,-80,-.018),(80,80,-.018),(-80,80,-.018)],[],[(0,1,2,3)])
        floor_mat=keep(bpy.data.materials.new('Check concrete')); floor_mat.diffuse_color=(.27,.27,.26,1); floor.data.materials.append(floor_mat)
        for v in views:
            ortho=v in ORTHO; board.hide_render=not ortho; floor.hide_render=ortho
            if ortho:
                eye,target,w,h=ORTHO[v]; cam.data.type='ORTHO'; cam.data.ortho_scale=w/100
            else:
                eye,target,lens=EXTRA[v]; w,h=1600,900; cam.data.type='PERSP'; cam.data.lens=lens
            sc.render.resolution_x=w; sc.render.resolution_y=h
            cam.location=K.B(*eye); back=(cam.location-K.B(*target)).normalized()
            cam.rotation_euler=(0,0,math.pi) if v=='o_top' else (-back).to_track_quat('-Z','Y').to_euler()
            sun.rotation_euler=(-(back+Vector((.35,-.45,1)))).to_track_quat('-Z','Y').to_euler()
            from mathutils import Quaternion
            for name,pitch in ([('limits_up',15),('limits_down',-6)] if v=='limits' else [(v,0)]):
                turret.rotation_quaternion=Quaternion((0,0,1),math.pi/2 if v=='limits' else 0)
                gun.rotation_quaternion=Quaternion((1,0,0),-math.radians(pitch))
                sc.view_layers[0].update()
                path=(directory/'metric' if ortho else directory)/(name+'.png')
                sc.render.filepath=str(path); bpy.ops.render.render(scene=sc.name,write_still=True)
            if ortho: print(f'METRIC {v} 100 px/m, grid 0.5 m: {path}')


def render_all(root,outdir,views=None,quick=False,painted=True,sheet=None):
    directory=Path(outdir).resolve(); directory.mkdir(parents=True,exist_ok=True)
    requested=list(dict.fromkeys(views or [*T.VIEWS,*ORTHO,*EXTRA]))
    unknown=set(requested)-set(T.VIEWS)-set(ALIAS)-set(ORTHO)-set(EXTRA)
    if unknown: raise ValueError('Unknown view: '+', '.join(sorted(unknown)))
    kit=list(dict.fromkeys(ALIAS.get(v,v) for v in requested if v in T.VIEWS or v in ALIAS))
    if kit:
        T.render_check(root,directory,elev=(-6,15),views=kit if views else None,quick=quick)
        for alias,canonical in ALIAS.items():
            if canonical in kit and (alias in requested or not views):
                copyfile(directory/(canonical+'.png'),directory/(alias+'.png'))
        if sheet or not views: T.sheet(directory,sheet or directory/'contact.jpg')
    elif sheet:
        raise ValueError('--sheet needs at least one shared tank check view')
    supplemental(root,directory,[v for v in requested if v in ORTHO or v in EXTRA],quick,painted)
