"""cinfo.py <outdir> <thumbwidth> <title>... : Commons imageinfo (size, author, licence) + thumbnails; appends to <outdir>/cand.json"""
import json, sys, os, time, urllib.request, urllib.parse, re
out, W = sys.argv[1], int(sys.argv[2]); titles = sys.argv[3:]
os.makedirs(out, exist_ok=True)
dbp = os.path.join(out, 'cand.json')
db = json.load(open(dbp)) if os.path.exists(dbp) else {}
UA = {'User-Agent': 'bike-fit-script/1.0'}
for t in titles:
    if not t.startswith('File:'): t = 'File:' + t
    q = urllib.parse.urlencode({'action': 'query', 'titles': t, 'prop': 'imageinfo', 'iiprop': 'url|size|extmetadata', 'iiurlwidth': W, 'format': 'json'})
    for k in range(6):
        try:
            d = json.load(urllib.request.urlopen(urllib.request.Request('https://commons.wikimedia.org/w/api.php?' + q, headers=UA), timeout=60)); break
        except Exception as ex:
            print('retry api', ex); time.sleep(15 * (k + 1))
    p = next(iter(d['query']['pages'].values()))
    if 'imageinfo' not in p: print('missing', t); continue
    ii = p['imageinfo'][0]; em = ii.get('extmetadata', {})
    strip = lambda s: re.sub('<[^>]+>', '', s or '').strip()
    key = 'c%02d' % (len(db) + 1)
    for k, v in db.items():
        if v['title'] == t: key = k
    db[key] = {'title': t, 'url': ii['descriptionurl'], 'size': [ii['width'], ii['height']],
               'author': strip(em.get('Artist', {}).get('value')), 'licence': strip(em.get('LicenseShortName', {}).get('value')),
               'desc': strip(em.get('ImageDescription', {}).get('value'))[:200], 'date': strip(em.get('DateTimeOriginal', {}).get('value'))[:40]}
    dst = os.path.join(out, key + '.jpg')
    if not os.path.exists(dst):
        for k in range(4):
            try:
                data = urllib.request.urlopen(urllib.request.Request(ii['thumburl'], headers=UA), timeout=60).read(); break
            except Exception as ex:
                print('retry', ex); time.sleep(5 * (k + 1))
        open(dst, 'wb').write(data)
    print(key, db[key]['size'], db[key]['licence'], '|', db[key]['author'][:40], '|', t[5:60], '|', db[key]['desc'][:80])
    time.sleep(1)
json.dump(db, open(dbp, 'w'), indent=1, ensure_ascii=False)
