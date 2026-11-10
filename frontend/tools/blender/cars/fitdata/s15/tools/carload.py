"""carload.py (Blender): build one of the own cars through its repo scripts.

  load(car, night=False) -> dict: root, mats (name -> material), scene() (the car's check scene; night lamps lit),
  light(eye, target) (sun placement), fold(closed) (pop-ups), export(path) (GLB), inv_ffd(G) (game-frame points on the
  built, deformed body -> the design frame before the fitted FFD field)
"""
import sys

import numpy as np

CARS = '/home/dev/Desktop/service/internal/webgame-by-claude/frontend/tools/blender/cars'
if CARS not in sys.path:
    sys.path.insert(0, CARS)
import bpy  # noqa: E402


def _fixed_point(G, disp, it=40):
    G = np.asarray(G, float)
    X = G.copy()
    for _ in range(it):
        X = G - disp(X)
    return X


def load(car, night=False, paint=None):
    R = {'fold': lambda closed: None}
    if car == 'raijin':
        import raijin
        import raijin_ffd
        import raijin_kit as K
        import raijin_scene as S
        K.clear_scene()
        root, mats, lamprep = raijin.build({'paint': paint or '#1f47a8'})

        def scene():
            S.scene(night=night)
            if night:
                S.night_lights(mats, lamprep)
        R.update(root=root, mats=mats, scene=scene, light=lambda e, t: S.light_from(e, t, 40.0),
                 export=lambda p: K.export_glb(p, root))
        L = raijin_ffd.Lattice.load()
        R['inv_ffd'] = (lambda G: _fixed_point(G, L.displace)) if L is not None else (lambda G: np.asarray(G, float))
    elif car == 's15':
        import s15
        import s15_ffd
        import s15_kit as K
        K.clear_scene()
        root, m = s15.build({'paint': paint or '#9a9ea4'})
        mats = m.mats if hasattr(m, 'mats') else m

        def scene():
            K.scene(night=night)
            if night:
                s15.night(m, True)
        R.update(root=root, mats=mats, scene=scene, light=lambda e, t: K.sun_from(e, t, 40.0),
                 export=lambda p: K.export_glb(p, root))
        L = s15_ffd.Lattice.load()
        R['inv_ffd'] = (lambda G: _fixed_point(G, L.displace)) if L is not None else (lambda G: np.asarray(G, float))
    elif car == 'hayate':
        argv0 = sys.argv
        sys.argv = [sys.argv[0]]
        import hayate_ffd
        import hayate_kit as K
        import hayate_parts as P
        import hayate_stage as S
        sys.argv = argv0
        K.clear_scene()
        mats, _tex = P.materials()
        root = K.empty('hayate')
        body0 = K.empty('body', root)
        parts = P.build_all(body0, root, mats, {})

        def scene():
            S.scene(night=night)
            P.lamps_on(mats, night)
        R.update(root=root, mats=mats, scene=scene, light=lambda e, t: S.light_from(e, t, 40.0),
                 export=lambda p: K.export_glb(p, root), fold=lambda closed: P.fold_popups(parts, closed=closed),
                 parts=parts)
        L = hayate_ffd.Lattice.load()
        R['inv_ffd'] = (lambda G: _fixed_point(G, L.displace)) if L is not None else (lambda G: np.asarray(G, float))
    elif car == 'shiden':
        import shiden
        import shiden_ffd
        import shiden_parts as PARTS
        import shiden_scene as S
        if paint:
            PARTS.MATS['paint'] = (paint, 0.55, 0.28)
        root, mats, _c = shiden.build_car(night=False)

        def scene():
            S.scene(night=night)
            if night:
                PARTS.lamps_on(mats)

        def fold(closed):
            for n in ('popup_l', 'popup_r'):
                o = bpy.data.objects.get(n)
                if o is not None and 'popupClosed' in o:
                    o.rotation_euler[0] = o['popupClosed'] if closed else 0.0
        R.update(root=root, mats=mats, scene=scene, light=lambda e, t: S.light_from(e, t, 40.0),
                 export=lambda p: shiden.export(p, root), fold=fold)
        ops = shiden_ffd._ops(True)
        R['inv_ffd'] = lambda G: _fixed_point(G, lambda X: shiden_ffd._deform(X, ops) - X)
    else:
        raise SystemExit('car?')
    return R
