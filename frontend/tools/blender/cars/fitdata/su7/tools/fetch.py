"""fetch.py <list.json> <outdir> [width=1280] [p16,p22,...]: download the Commons photos of ref/list.json at a thumbnail
width; entries with "mirrored": true (the Commons file is a mirror image: its plate reads backwards) are flipped back.
Blender's Python needs SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt; Pillow for the flip."""
import json, os, sys, time, urllib.parse, urllib.request
from PIL import Image, ImageOps
L = json.load(open(sys.argv[1])); out = sys.argv[2]
W = int(sys.argv[3]) if len(sys.argv) > 3 else 1280
only = sys.argv[4].split(',') if len(sys.argv) > 4 else None
os.makedirs(out, exist_ok=True)
for e in L:
    stem = os.path.splitext(e['file'])[0]
    if only and stem not in only:
        continue
    dst = os.path.join(out, stem + '.jpg')
    if os.path.exists(dst) and os.path.getsize(dst):
        continue
    url = 'https://commons.wikimedia.org/wiki/Special:FilePath/' + urllib.parse.quote(e['title'].replace('File:', '').replace(' ', '_')) + f'?width={W}'
    for k in range(5):
        try:
            data = urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'car-fit-script/1.0'}), timeout=90).read()
            break
        except Exception as ex:
            print('retry', stem, ex); time.sleep(10 * (k + 1))
    else:
        continue
    open(dst, 'wb').write(data)
    if e.get('mirrored'):
        ImageOps.mirror(Image.open(dst).convert('RGB')).save(dst, quality=95)
    print('ok', stem, Image.open(dst).size); time.sleep(2)
