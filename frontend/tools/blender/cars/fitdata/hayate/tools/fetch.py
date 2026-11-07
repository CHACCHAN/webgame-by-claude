"""fetch Commons photos (thumbnails of a given width) listed in list.json files: fetch.py <width> <outdir> <prefix:list.json>..."""
import json, sys, time, urllib.parse, urllib.request, os
W = int(sys.argv[1]); out = sys.argv[2]
os.makedirs(out, exist_ok=True)
for spec in sys.argv[3:]:
    pre, lst = spec.split(':', 1)
    only = None
    if '@' in pre:
        pre, only = pre.split('@'); only = set(only.split(','))
    for e in json.load(open(lst)):
        idx = e['file'][:2] if pre else e['file'].split('.')[0]
        if only and idx not in only: continue
        name = e['title'][5:].replace(' ', '_')
        url = 'https://commons.wikimedia.org/wiki/Special:FilePath/' + urllib.parse.quote(name) + f'?width={W}'
        dst = os.path.join(out, f'{pre}{idx}.jpg')
        if os.path.exists(dst): continue
        for att in range(4):
            try:
                req = urllib.request.Request(url, headers={'User-Agent': 'TougeNocturneFit/1.0'})
                data = urllib.request.urlopen(req, timeout=60).read()
                open(dst, 'wb').write(data); print('ok', dst, len(data)); break
            except Exception as ex:
                print('retry', dst, ex); time.sleep(30 * (att + 1))
        time.sleep(8.0)
