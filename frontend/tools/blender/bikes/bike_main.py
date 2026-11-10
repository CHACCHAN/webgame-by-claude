"""
Command line shared by the bike entry scripts (nsr250r.py, ninjah2.py, hayabusa.py):

  blender -t 6 -b --factory-startup --python tools/blender/bikes/<id>.py -- [--out <file.glb>]
      [--render <dir> --views side,front34,rear34,front,rear --samples N --size WxH] [--night] [--paint #rrggbb]
                                                   (a view photo:r01 with --cams <cams.json>: that photo's solved camera;
                                                   --sun offset,elevation[,energy] sets its sun)
      [--wb <dir> --views ...]                     quick Workbench renders (grey studio, material colours)
      [--fit <cams.json> --photos r01,r02 --fitout <dir>]   silhouette / material-id / shaded renders from solved
                                                   photo cameras (rider hidden, front wheel steered as in the photo)
      [--pick <cams.json> --photos r01 --pts <in.json> --ptsout <out.json>]   photo pixels → points on the model
      [--norider]
"""
import os
import sys

import bike_kit as K


def run(build):
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []

    def opt(name, default=None):
        return argv[argv.index(name) + 1] if name in argv else default

    K.clear_scene()
    o = {'rider': '--norider' not in argv}
    if opt('--paint'):
        o['paint'] = opt('--paint')
    root, mats, lamps = build(o)
    if opt('--out'):
        K.export_glb(opt('--out'), root)
        print('EXPORTED', opt('--out'))
    import bike_scene as S
    if opt('--fit'):
        S.fit_renders(root, opt('--fit'), opt('--photos').split(','), opt('--fitout'), shade='--noshade' not in argv)
    if opt('--pick'):
        S.pick(opt('--pick'), opt('--photos'), opt('--pts'), opt('--ptsout'))
    if opt('--wb'):
        S.workbench(opt('--views', 'side,front34,rear34').split(','), opt('--wb'),
                    size=tuple(int(v) for v in opt('--size', '1280x720').split('x')))
    if opt('--render'):
        night = '--night' in argv
        S.scene(night=night)
        if night:
            S.night_lights(mats, lamps)
        os.makedirs(opt('--render'), exist_ok=True)
        size = tuple(int(v) for v in opt('--size', '1280x720').split('x'))
        for v in opt('--views', 'front34').split(','):
            out = os.path.join(opt('--render'), f'{v.replace(":", "_")}{"_night" if night else ""}.png')
            if v.startswith('photo:'):        # photo:<name> with --cams <cams.json>: the solved photo camera
                sun = [float(x) for x in opt('--sun', '40,42').split(',')]     # azimuth offset from the camera, elevation [, energy]
                S.render_photo(opt('--cams'), v[6:], out, width=size[0], samples=int(opt('--samples', '24')),
                               sun_offset=sun[0], sun_elevation=sun[1], sun_energy=sun[2] if len(sun) > 2 else None)
            else:
                S.render(v, out, size=size, samples=int(opt('--samples', '24')))
