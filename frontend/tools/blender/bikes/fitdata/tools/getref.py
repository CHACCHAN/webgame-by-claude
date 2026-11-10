"""getref.py <cand.json> <refdir> <width> c01:r01 c02:r02 ... : download chosen candidates at <width> (or full size if smaller) as ref/rNN.jpg; writes ref/list.json"""
import json, sys, os, time, urllib.request, urllib.parse
cand = json.load(open(sys.argv[1])); out = sys.argv[2]; W = int(sys.argv[3])
os.makedirs(out, exist_ok=True)
lp = os.path.join(out, 'list.json')
L = json.load(open(lp)) if os.path.exists(lp) else []
UA = {'User-Agent': 'bike-fit-script/1.0'}
for pair in sys.argv[4:]:
    c, r = pair.split(':'); e = cand[c]
    dst = os.path.join(out, r + '.jpg')
    w = min(W, e['size'][0])
    if not os.path.exists(dst):
        url = 'https://commons.wikimedia.org/wiki/Special:FilePath/' + urllib.parse.quote(e['title'][5:].replace(' ', '_')) + (f'?width={w}' if w < e['size'][0] else '')
        for k in range(6):
            try:
                data = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=90).read(); break
            except Exception as ex:
                print('retry', ex); time.sleep(15 * (k + 1))
        open(dst, 'wb').write(data)
    from_size = e['size']
    L = [x for x in L if x['file'] != r + '.jpg']
    L.append({'file': r + '.jpg', 'title': e['title'], 'author': e['author'], 'licence': e['licence'], 'url': e['url'],
              'size': [w, round(e['size'][1] * w / e['size'][0])], 'note': e.get('desc', '')[:120]})
    print(r, e['title'], w); time.sleep(2)
json.dump(sorted(L, key=lambda x: x['file']), open(lp, 'w'), indent=1, ensure_ascii=False)
