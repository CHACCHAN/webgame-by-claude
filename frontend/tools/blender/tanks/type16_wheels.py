"""Single two-sided wheel master; only the mesh child changes facing, never the rig."""
import math

import bpy
import jet_kit as K
from type16_shape import AXLES, finish

CY = .545
TRACK_HALF = 1.28
TREAD_COUNT = 40


def wheel_mesh(mats):
    p = K.Part('tyre_1l')
    # Rounded casing and three rows of independently staggered short shoes.
    # A shoe is only .021-.024 m above the local crown, including the shoulder.
    half=[(.303,.131),(.330,.164),(.406,.185),(.466,.180),(.499,.171),(.530,.115),(.5375,.049)]
    profile=[(r,-x) for r,x in half]+list(reversed(half))+[(half[0][0],-half[0][1])]
    p.revolve('tyre',profile,(0,0,0),seg=36)
    pitch=math.tau/TREAD_COUNT
    for i in range(TREAD_COUNT):
        # Axial edges, casing radius and outer radius at each edge, phase,
        # skew, and angular width (in fractions of one pitch).
        for x0,x1,r0,r1,h0,h1,phase,skew,span in (
                (-.171,-.056,.499,.537,.521,.559,.36,-.24,.68),
                (-.047,.047,.5375,.5375,.560,.560,0,.16 if i%2==0 else -.16,.64),
                (.056,.171,.537,.499,.559,.521,.70,.24,.68)):
            rows=[]
            for x,r,h,k in ((x0,r0,h0,0),(x1,r1,h1,skew)):
                row=[]
                for rad,delta in ((r-.004,-.035),(h,0),(h,span),(r-.004,span+.035)):
                    a=(i+phase+k+delta)*pitch
                    row.append((x,rad*math.cos(a),rad*math.sin(a)))
                rows.append(row)
            p.loft(rows,'tread',cap0=True,cap1=True,cap_centre=False,smooth=False)
    # Raised folded lip, dished steel web and a distinct stepped hub. Captive
    # hub screws are painted relief; keep real hex nuts on the .40 m circle.
    for s,zone in ((1,'disc_g'),(-1,'disc_b')):
        prof=[(0,.085),(.309,.115),(.310,.161),(.289,.161),(.257,.098),
              (.146,.102),(.139,.152),(.118,.179),(0,.179)]
        p.revolve(zone,[(r,s*x) for r,x in prof],(0,0,0),seg=32)
        for i in range(20):
            a=i*math.tau/20
            y,z=.20*math.cos(a),.20*math.sin(a)
            hexagon=[(y+.016*math.cos(b*math.tau/6+a),z+.016*math.sin(b*math.tau/6+a)) for b in range(6)]
            # Embedded base is invisible; no cap at that end.
            p.loft([[(s*x,yy,zz) for yy,zz in hexagon] for x in (.098,.128)],'nut',cap1=True,cap_centre=False,smooth=False)
    return finish(p,None,mats)


def build(body,mats):
    master=wheel_mesh(mats)
    wheels=[]
    for i,z in enumerate(AXLES,1):
        for s,side in ((1,'l'),(-1,'r')):
            key=f'{i}{side}'
            c=(s*TRACK_HALF,CY,z)
            pivot=K.node('wheel_'+key,body,c)
            spin=K.node('spin_'+key,pivot,c)
            if wheels:
                ob=bpy.data.objects.new('tyre_'+key,master.data)
                bpy.context.scene.collection.objects.link(ob)
            else:
                ob=master
            ob.parent=spin
            if s*(-1 if i==4 else 1)<0:
                ob.scale.x=-1  # reflect the mesh only; all node rotations remain identity
            wheels.append(ob)
    bpy.context.view_layer.update()
    return wheels
