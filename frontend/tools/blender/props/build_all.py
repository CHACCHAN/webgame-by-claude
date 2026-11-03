"""
Builds all eight props in one Blender process (and, with --render, their check renders plus a contact sheet).

    ~/.local/bin/blender -t 4 --background --factory-startup --python frontend/tools/blender/props/build_all.py -- --out <dir> [--render <dir>]

Writes street_light.glb, wind_turbine.glb, curve_mirror.glb, vending_machine.glb, torii.glb, stone_lantern.glb,
bus_stop.glb, traffic_cone.glb into <dir> (textures in <dir>/tex), and <render>/*.png + <render>/contact_sheet.png.
"""
import importlib
import os
import subprocess
import sys

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import prop_kit as K  # noqa: E402

NAMES = ['street_light', 'wind_turbine', 'curve_mirror', 'vending_machine', 'torii', 'stone_lantern', 'bus_stop', 'traffic_cone']

if __name__ == '__main__':
    out, render = K.parse_args()
    for n in NAMES:
        K.run(importlib.import_module(n).SPEC, out, render)
    if render:
        py = K.host_python()
        if py:
            subprocess.run([py, '-I', os.path.join(HERE, 'contact_sheet.py'), render], check=False)
