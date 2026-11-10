"""fetch.py <list.json> <outdir> <width> [r02,r10,...] : download Commons photos (thumbnail width) by their list entry"""
import json, sys, time, urllib.request, urllib.parse, os
L = json.load(open(sys.argv[1])); out = sys.argv[2]; W = int(sys.argv[3])
only = sys.argv[4].split(',') if len(sys.argv) > 4 else None
for e in L:
    stem = os.path.splitext(e['file'])[0]
    if only and stem not in only: continue
    dst = os.path.join(out, stem + '.jpg')
    if os.path.exists(dst): continue
    name = e['title'].replace('File:', '').replace(' ', '_')
    url = 'https://commons.wikimedia.org/wiki/Special:FilePath/' + urllib.parse.quote(name) + f'?width={W}'
    req = urllib.request.Request(url, headers={'User-Agent': 'TougeNocturneFit/1.0'})
    for k in range(5):
        try:
            data = urllib.request.urlopen(req, timeout=60).read(); break
        except Exception as ex:
            print('retry', stem, ex); time.sleep(10 * (k + 1))
    else:
        continue
    open(dst, 'wb').write(data); print('ok', stem, len(data)); time.sleep(2)
