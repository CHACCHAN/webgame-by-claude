"""glbcheck.py <file.glb> : the GLB contract: node tree, steer axis (rake), wheel centres, tyre radii, materials
(alpha / transmission), triangle count, the exhaust meshes, lamp material positions"""
import sys, json, struct, math
import numpy as np
raw = open(sys.argv[1], 'rb').read()
L = struct.unpack('<I', raw[12:16])[0]
G = json.loads(raw[20:20 + L])
bin_off = 20 + L + 8
def q2m(q):
    x, y, z, w = q
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                     [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                     [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])
def local(n):
    M = np.eye(4)
    if 'matrix' in n: return np.array(n['matrix']).reshape(4, 4).T
    S = np.diag(n.get('scale', [1, 1, 1]))
    M[:3, :3] = q2m(n.get('rotation', [0, 0, 0, 1])) @ S
    M[:3, 3] = n.get('translation', [0, 0, 0])
    return M
nodes = G['nodes']; W = {}
def acc_data(i):
    a = G['accessors'][i]; bv = G['bufferViews'][a['bufferView']]
    comp = {5126: ('f', 4), 5125: ('I', 4), 5123: ('H', 2), 5121: ('B', 1)}[a['componentType']]
    n = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4}[a['type']]
    off = bin_off + bv.get('byteOffset', 0) + a.get('byteOffset', 0)
    stride = bv.get('byteStride', comp[1] * n)
    out = np.array([struct.unpack_from('<' + comp[0] * n, raw, off + k * stride) for k in range(a['count'])])
    if a.get('normalized'):
        pass
    return out
tris = 0; matpos = {}
def walk(i, P, depth):
    global tris
    n = nodes[i]; M = P @ local(n); W[n.get('name', str(i))] = M
    info = ''
    if 'mesh' in n:
        me = G['meshes'][n['mesh']]
        t = 0
        for pr in me['primitives']:
            t += (G['accessors'][pr['indices']]['count'] // 3) if 'indices' in pr else G['accessors'][pr['attributes']['POSITION']]['count'] // 3
            mn = G['materials'][pr['material']]['name'] if 'material' in pr else '-'
            if mn in ('headlight', 'taillight', 'indicator') or 'exhaust' in n.get('name', ''):
                pos = acc_data(pr['attributes']['POSITION'])
                if 'extensions' in G['accessors'][pr['attributes']['POSITION']] or G['accessors'][pr['attributes']['POSITION']]['componentType'] != 5126:
                    pass
                pw = (M[:3, :3] @ pos.T).T + M[:3, 3]
                matpos.setdefault(mn if mn in ('headlight', 'taillight', 'indicator') else 'exhaust-mesh', []).append(pw)
        tris += t; info = f' mesh tris {t}'
    if depth < 3 or 'mesh' not in n:
        print('  ' * depth + n.get('name', str(i)) + info)
    for c in n.get('children', []):
        walk(c, M, depth + 1)
for r in G['scenes'][G.get('scene', 0)]['nodes']:
    walk(r, np.eye(4), 0)
print('TRIS', tris)
print('extensionsUsed', G.get('extensionsUsed'))
for m in G['materials']:
    bad = [k for k in ('alphaMode',) if m.get(k, 'OPAQUE') != 'OPAQUE'] + list(m.get('extensions', {}).keys())
    if bad: print('MATERIAL', m['name'], bad)
print('MATERIALS', len(G['materials']), sorted(m['name'] for m in G['materials']))
for k in ('steer', 'wheel_f', 'spin_f', 'wheel_r', 'spin_r', 'body', 'rider'):
    if k in W:
        M = W[k]; y = M[:3, 1] / np.linalg.norm(M[:3, 1])
        print(f'{k:8s} origin {np.round(M[:3, 3], 4)} local+Y {np.round(y, 4)}' + (f' rake {math.degrees(math.atan2(y[2], y[1])):.2f} deg (axis tilts back: {y[2] < 0})' if k == 'steer' else ''))
if 'steer' in W and 'wheel_f' in W:
    s = W['steer']; a = s[:3, 1] / np.linalg.norm(s[:3, 1]); o = s[:3, 3]
    t = -o[1] / a[1]; g = o + a * t
    wf, wr = W['wheel_f'][:3, 3], W['wheel_r'][:3, 3]
    print('axis meets ground at z', round(g[2], 4), '| trail', round(g[2] - (wf[2] - 0), 4), '| wheelbase', round(wf[2] - wr[2], 4), '| contact midpoint z', round((wf[2] + wr[2]) / 2, 4))
for k, v in matpos.items():
    p = np.concatenate(v)
    print(f'{k:10s} x {p[:, 0].min():+.3f}..{p[:, 0].max():+.3f} y {p[:, 1].min():.3f}..{p[:, 1].max():.3f} z {p[:, 2].min():+.3f}..{p[:, 2].max():+.3f}')
