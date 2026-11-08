"""
loop.py <tag> [--cams cams.json] [--photos r01,r03] [--glb existing.glb] [--nobuild] [--noids]
Build shiden (Blender), render silhouettes + material ids from every solved camera (pop-ups folded), run silfit per
photo (3 at a time) with the per-photo settings in fitargs.json, print one table.
"""
import json, os, subprocess, sys, concurrent.futures as cf
SP = '/tmp/claude-1000/-home-dev-Desktop-service-internal-webgame-by-claude/43be7242-fdd3-4dc4-ac3b-587fd8b5aa08/scratchpad'
SH = SP + '/cars/shiden'
REPO = '/home/dev/Desktop/service/internal/webgame-by-claude/frontend'
BL = SP + '/agents/blender.sh'
PY = ['env', 'PYTHONPATH=' + SP + '/pyfit', 'PYTHONDONTWRITEBYTECODE=1',
      '/home/dev/.local/opt/blender-5.2.3-linux-x64/5.2/python/bin/python3.13', '-P']
a = sys.argv[1:]
tag = a[0]
def opt(k, d=None):
    return a[a.index(k) + 1] if k in a else d
cams_file = opt('--cams', SH + '/cams.json')
cams = json.load(open(cams_file))['cams']
photos = opt('--photos', ','.join(sorted(cams))).split(',')
out = f'{SH}/runs/{tag}'
os.makedirs(out + '/ren', exist_ok=True)
fa = json.load(open(SH + '/fitargs.json')) if os.path.exists(SH + '/fitargs.json') else {}
glb = opt('--glb', out + '/shiden.glb')
if '--nobuild' not in a and '--glb' not in a:
    extra = opt('--build', '')
    r = subprocess.run([BL, '-t', '4', '-b', '--factory-startup', '--python', REPO + '/tools/blender/cars/shiden.py',
                        '--', '--out', glb] + (extra.split() if extra else []), capture_output=True, text=True)
    tl = [l for l in r.stdout.splitlines() if l.startswith(('TRIS total', 'MATERIALS'))]
    print(' | '.join(tl))
    if r.returncode or not os.path.exists(glb):
        print(r.stdout[-3000:], r.stderr[-3000:]); sys.exit(1)
# render: split cameras over up to 3 Blender processes
groups = [photos]  # one Blender process at a time (memory rules)
def render(g):
    return subprocess.run([BL, '-t', '4', '-b', '--factory-startup', '--python', REPO + '/tools/carfit/silrender.py', '--',
                           glb, cams_file, out + '/ren', ','.join(g), '--fold-popups'], capture_output=True, text=True)
with cf.ThreadPoolExecutor(1) as ex:
    for r in ex.map(render, groups):
        if r.returncode:
            print(r.stdout[-2000:], r.stderr[-2000:]); sys.exit(1)
def fit(n):
    s = fa.get(n, {})
    cmd = PY + [REPO + '/tools/carfit/silfit.py', f'{SH}/photos/{n}.jpg', f'{out}/ren/{n}_sil.png', out + '/fit',
                '--ids', f'{out}/ren/{n}_ids.png', '--band', str(s.get('band', 0.06))]
    for ig in s.get('ignore', []):
        cmd += ['--ignore', ','.join(str(v) for v in ig)]
    if s.get('mask'):
        cmd += ['--mask', SH + '/' + s['mask']]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        print(n, r.stderr[-1500:])
    return n
with cf.ThreadPoolExecutor(3) as ex:
    list(ex.map(fit, photos))
Z = ['top-left', 'top-middle', 'top-right', 'bottom-left', 'bottom-middle', 'bottom-right']
print(f'{"photo":6s} {"IoU":>6s} {"p95":>5s} {"p95b":>5s} | ' + ' '.join(f'{z[:1]}{z.split("-")[1][:1]:>6s}' for z in Z))
rows = {}
for n in photos:
    j = json.load(open(f'{out}/fit/{n}.json'))
    rows[n] = j
    zs = ' '.join(f'{j["zones"].get(z, {}).get("mean_signed_pct", 0):+7.2f}' for z in Z)
    ok = j['iou'] >= 0.95 and j['render_to_photo_p95_pct'] <= 1.5 and all(abs(v['mean_signed_pct']) <= 1 for v in j['zones'].values())
    print(f'{n:6s} {j["iou"]:6.3f} {j["render_to_photo_p95_pct"]:5.2f} {j["photo_to_render_p95_pct"]:5.2f} | {zs} {"PASS" if ok else ""}')
import statistics
print('mean IoU', round(statistics.mean(r['iou'] for r in rows.values()), 4), ' mean p95', round(statistics.mean(r['render_to_photo_p95_pct'] for r in rows.values()), 2))
