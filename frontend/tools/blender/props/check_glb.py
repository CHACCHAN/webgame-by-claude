#!/usr/bin/env python3
"""python3 -I check_glb.py <dir>: triangles, materials, textures, size and bounding box (game frame) of every prop GLB"""
import json
import os
import struct
import sys


def read(path):
    b = open(path, 'rb').read()
    n = struct.unpack('<I', b[12:16])[0]
    return json.loads(b[20:20 + n])


for f in sorted(os.listdir(sys.argv[1])):
    if not f.endswith('.glb'):
        continue
    p = os.path.join(sys.argv[1], f)
    j = read(p)
    tris = 0
    for me in j['meshes']:
        for pr in me['primitives']:
            tris += j['accessors'][pr['indices']]['count'] // 3
    lo, hi = [1e9] * 3, [-1e9] * 3
    for nd in j['nodes']:
        if 'mesh' not in nd:
            continue
        t = nd.get('translation', [0, 0, 0])
        for pr in j['meshes'][nd['mesh']]['primitives']:
            a = j['accessors'][pr['attributes']['POSITION']]
            for k in range(3):
                lo[k] = min(lo[k], a['min'][k] + t[k])
                hi[k] = max(hi[k], a['max'][k] + t[k])
    mats = [m['name'] for m in j['materials']]
    emis = [m['name'] for m in j['materials'] if 'emissiveTexture' in m]
    print(f"{f}: {tris} tris, {os.path.getsize(p) / 1024:.0f} KiB, materials {mats}, images {len(j.get('images', []))}, emissiveTexture {emis}, "
          f"extensions {j.get('extensionsUsed', [])}, nodes {[n['name'] for n in j['nodes']]}")
    print(f"    bbox x {lo[0]:.2f}..{hi[0]:.2f}  y {lo[1]:.2f}..{hi[1]:.2f}  z {lo[2]:.2f}..{hi[2]:.2f}  (size {hi[0]-lo[0]:.2f} x {hi[1]-lo[1]:.2f} x {hi[2]-lo[2]:.2f})")
