#!/bin/bash
# The frames of a course's run (tools/course-clip.cjs) → public/video/courses/<id>.mp4 (H.264, no sound),
# <id>.jpg (the still shown before the film plays) and <id>.json (where the car is: every 0.2 s the share of the
# course it has covered; the course select's grains follow it), and writes the film's stamp into
# src/ui/screens/courseFilms.json (the page fetches the three files with it: fixed names are cached for a day).
#   tools/course-clip-encode.sh <frames dir of the course> <course id> [crf=34] [width=1280] [height=720]
# ffmpeg runs in a container (FFMPEG_IMAGE, default touge-tools-ffmpeg:latest: any image with ffmpeg + libx264);
# the still and the track need Python with PIL.
set -e
RAW=$(realpath "$1"); ID=$2; CRF=${3:-34}; W=${4:-1280}; H=${5:-720}
OUT=$(realpath "$(dirname "$0")/../public/video/courses")
mkdir -p "$OUT"
docker run --rm -u "$(id -u):$(id -g)" -v "$RAW":/in:ro -v "$OUT":/out "${FFMPEG_IMAGE:-touge-tools-ffmpeg:latest}" ffmpeg -hide_banner -loglevel error -y \
  -framerate 30 -i /in/f%05d.jpg -vf "scale=$W:$H:flags=lanczos" -c:v libx264 -preset slower -crf "$CRF" -pix_fmt yuv420p -g 45 -movflags +faststart -an "/out/$ID.mp4"
python3 - "$RAW" "$OUT" "$ID" <<'PY'
import json, sys
from PIL import Image
raw, out, cid = sys.argv[1:4]
t = json.load(open(f'{raw}/track.json'))
tr = t['track']
step = 6
u = [tr[i][0] for i in range(0, len(tr), step)]
# (the share of the course never goes back in the film)
for i in range(1, len(u)): u[i] = max(u[i], u[i - 1])
json.dump({'step': step / t['fps'], 'u': u}, open(f'{out}/{cid}.json', 'w'), separators=(',', ':'))
Image.open(f'{raw}/f00000.jpg').resize((960, 540), Image.LANCZOS).save(f'{out}/{cid}.jpg', quality=80)
print(cid, 'pictures', len(tr), '=', round(len(tr) / t['fps'], 1), 's')
PY
# the film's stamp: the page asks for the three files with it, so a film recorded again is not served from a cache
python3 - "$OUT" "$ID" "$(dirname "$0")/../src/ui/screens/courseFilms.json" <<'PY'
import hashlib, json, os, sys
out, cid, path = sys.argv[1:4]
films = json.load(open(path)) if os.path.exists(path) else {}
films[cid] = hashlib.sha1(open(f'{out}/{cid}.mp4', 'rb').read()).hexdigest()[:8]
open(path, 'w').write(json.dumps(films, indent=2) + '\n')
print(cid, 'stamp', films[cid])
PY
ls -la "$OUT/$ID".*
