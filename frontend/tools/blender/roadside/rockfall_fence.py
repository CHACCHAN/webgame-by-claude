"""
Rockfall fence (落石防護柵): one 3 m bay. An H-beam post with its base plate, five wire ropes with their clips, the wire
net behind them (a sheet the game cuts out with its mesh texture; uv in units of 0.5 m). It stands on a wall's coping.
Module: z 0..3, post at z = 1.5, 2 m tall; the ropes and the net on the mountain's side of the post (x > 0).

    blender -t 4 --background --factory-startup --python rockfall_fence.py -- --out <dir> [--render <dir>]
"""
import os
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import roadside_kit as R  # noqa: E402
from roadside_kit import K  # noqa: E402

H = 2.0


def build(out):
    mt = R.mats()
    g, rust = mt['galvanised'], mt['rust']
    m = K.M('rockfall_fence')
    # H-150 post: two flanges and the web, a base plate with four anchor bolts
    for x0, x1 in ((-0.075, -0.068), (0.068, 0.075)):
        m.box(rust, x0, x1, 0.0, H, 1.425, 1.575)
    m.box(rust, -0.068, 0.068, 0.0, H, 1.4965, 1.5035)
    m.box(rust, -0.13, 0.13, 0.0, 0.016, 1.37, 1.63)
    for x in (-0.1, 0.1):
        for z in (1.4, 1.6):
            m.cyl(g, (x, 0.016, z), (x, 0.045, z), 0.012, seg=6)
    # wire ropes on the mountain side of the post, their clips on the flange
    for k in range(5):
        y = 0.25 + k * 0.4
        m.tube(g, [(0.085, y, 0.0), (0.085, y, 1.5), (0.085, y, 3.0)], 0.007, seg=5, cap0=False, cap1=False)
        m.box(g, 0.075, 0.1, y - 0.02, y + 0.02, 1.47, 1.53)
    # the net: one sheet behind the ropes
    net = mt['net']
    m.quad(net, [(0.094, 0.08, 0.0), (0.094, 0.08, 1.5), (0.094, H - 0.04, 1.5), (0.094, H - 0.04, 0.0)])
    m.quad(net, [(0.094, 0.08, 1.5), (0.094, 0.08, 3.0), (0.094, H - 0.04, 3.0), (0.094, H - 0.04, 1.5)])
    m.uv(net, lambda p, n: (p.z / 0.5, p.y / 0.5))
    return [m.build(sharp=40)]


SPEC = K.Spec('rockfall_fence.glb', build, [
    dict(name='main', eye=(-4.5, 1.8, -1.0), target=(0, 1.0, 1.5), lens=38),
])

if __name__ == '__main__':
    K.run(SPEC)
