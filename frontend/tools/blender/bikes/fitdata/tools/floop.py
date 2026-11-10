"""floop.py <bike> <photos a,b> <outdir> [--band 0.04] [--nobuild]: fit renders from the solved cameras (Blender),
silfit per photo (overlay, IoU, zone offsets), photo|blend|render strips, lamp outline scores (fit/lamps.json)"""
import json, os, subprocess, sys, time
B = os.path.expanduser('~/.local/opt/carfit/bikes')
REPO = '/home/dev/Desktop/service/internal/webgame-by-claude/frontend'
PY = [os.path.expanduser('~/.local/opt/blender-5.2.3-linux-x64/5.2/python/bin/python3.13')]
ENV = dict(os.environ, PYTHONPATH=os.path.expanduser('~/.local/opt/carfit/pyfit'))
a = sys.argv[1:]
bike, photos, out = a[0], a[1].split(','), a[2]
band = a[a.index('--band') + 1] if '--band' in a else '0.04'
fd = os.path.join(B, bike, 'fit')
os.makedirs(out, exist_ok=True)
t0 = time.time()
if '--nobuild' not in a:
    r = subprocess.run([os.path.expanduser('~/.local/opt/carfit/blender.sh'), '-t', '6', '-b', '--factory-startup', '--python',
                        f'{REPO}/tools/blender/bikes/{bike}.py', '--', '--norider', '--fit', f'{fd}/cams.json', '--photos', ','.join(photos),
                        '--fitout', out], capture_output=True, text=True)
    for line in r.stdout.splitlines():
        if line.startswith(('TRIS total', 'MATERIALS', 'LAMP', 'Traceback', 'Error')) or 'Error' in line[:40]:
            print(line)
    if r.returncode:
        print(r.stdout[-3000:], r.stderr[-3000:]); sys.exit(1)
t1 = time.time()
fit = json.load(open(f'{fd}/fit.json')) if os.path.exists(f'{fd}/fit.json') else {}
procs = []
for n in photos:
    ph = f'{B}/{bike}/ref/{n}.jpg'
    cfg = fit.get(n, {})
    cmd = PY + [f'{REPO}/tools/carfit/silfit.py', ph, f'{out}/{n}_sil.png', out, '--name', n, '--ids', f'{out}/{n}_ids.png',
                '--band', str(cfg.get('band', band))]
    for bx in cfg.get('ignore', []):
        cmd += ['--ignore', ','.join(str(v) for v in bx)]
    if cfg.get('mask'):
        cmd += ['--mask', f'{fd}/{cfg["mask"]}']
    procs.append(subprocess.Popen(cmd, env=ENV, stdout=subprocess.PIPE, stderr=subprocess.STDOUT))
    procs.append(subprocess.Popen(PY + [f'{REPO}/tools/blender/cars/fitdata/raijin/tools/blend.py', ph, f'{out}/{n}_shade.png', f'{out}/{n}_blend.png'],
                                  env=ENV, stdout=subprocess.PIPE, stderr=subprocess.STDOUT))
for p in procs:
    o, _ = p.communicate()
    if p.returncode: print(o.decode()[-800:])
if os.path.exists(f'{fd}/lamps.json'):
    r = subprocess.run(PY + [f'{B}/tools/lampfit.py', bike, out] + photos, env=ENV, capture_output=True, text=True)
    print(r.stdout.strip()[-2500:], r.stderr[-1500:])
print(f'render {t1 - t0:.0f}s fit {time.time() - t1:.0f}s')
print(f'{"photo":6s} {"IoU":>6s} {"p95":>5s} {"p95b":>5s}  zones (signed %: tl tm tr bl bm br)')
for n in photos:
    j = json.load(open(f'{out}/{n}.json')); z = j['zones']
    zs = ' '.join(f'{z.get(k, {}).get("mean_signed_pct", float("nan")):+5.2f}' for k in ('top-left', 'top-middle', 'top-right', 'bottom-left', 'bottom-middle', 'bottom-right'))
    print(f'{n:6s} {j["iou"]:6.4f} {j["render_to_photo_p95_pct"]:5.2f} {j["photo_to_render_p95_pct"]:5.2f}  {zs}')
