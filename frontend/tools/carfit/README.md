# carfit: fit a car model to photos by its silhouette and feature lines

Kept from Session 7 (2026-11-04), when the own car models were paused (the owner's call, to save cost; the cars stay
on the Sketchfab models until then). The work in progress is in `tools/blender/cars/<id>*.py` and
`tools/blender/textures/<id>/`; each agent's camera solves, photo lists (URL, author, licence) and fit settings are in
`tools/blender/cars/fitdata/<id>/` (the photos themselves are not in the repo: fetch them again from the lists).
$SP below was the session's scratch folder: use any scratch folder. silfit.py needs OpenCV and Pillow, e.g. in
Blender's Python: `<blender>/5.2/python/bin/python3.13 -m pip install --target <dir> opencv-python-headless pillow`,
then `PYTHONPATH=<dir> <that python> silfit.py …`.

The owner judged the cars "not the same as the real ones". Looking at photos and renders side by side has not
converged: a shape that looks right next to a photo is often 3-6 % off when overlaid, and a wrong camera solve hides
it. So acceptance is now measured. Iterate on your own against these numbers: a Workbench render takes seconds, so run
many loops per round instead of one.

## Tools (in this folder; do not edit, copy if you need changes)
- `silrender.py` (Blender): `$SP/agents/blender.sh -b --factory-startup --python silrender.py -- <car.glb> <cams.json> <outdir> [names] [--fold-popups]`
  renders `<name>_sil.png` (silhouette on transparent) and `<name>_ids.png` (flat colour per material) from each
  solved camera. cams.json format: see the file header (game coordinates, yaw/pitch/roll, focal in px, [W, H]).
  You may instead render the same two images from your own build script (no GLB export needed): white silhouette with
  alpha, and flat material colours, at the photo's resolution.
- `silfit.py`: `PY=PYTHONPATH=$SP/pyfit /home/dev/.local/opt/blender-5.2.3-linux-x64/5.2/python/bin/python3.13`
  `$PY silfit.py <photo> <name>_sil.png <outdir> --ids <name>_ids.png [--band 0.06] [--ignore x0,y0,x1,y1] [--mask m.png]`
  → `<name>_overlay.png` (red = model only, blue = photo only, green = photo outline, red line = model outline,
  yellow = the model's material borders: glass, lamps, openings), `<name>_mask.png`, `<name>.json`
  (IoU, boundary errors in % of the car's width in the image, signed offsets per zone: + = model too big there).
- The photo's car mask comes from GrabCut seeded by your render, so check it in the overlay once per photo. Ground
  shadows, cars behind, kerbs can leak in (seen: a dark shadow under the car counted as car). Fix with a smaller
  `--band` (0.03 once the model is close), `--ignore` boxes, or paint the mask by hand (white car / black not / grey
  128 ignore) and pass `--mask`.

## Procedure
1. Photos: at least 5 of the exact model year/grade, with the whole car visible: one near side-on, one near
   head-on, one near rear-on, a front 3/4 and a rear 3/4. Prefer long lenses, so perspective errors stay small.
2. Cameras: solve each from point correspondences with known 3D positions: wheel centres and contact points
   (wheelbase, track), plate corners (330 × 165 mm JP / 520 × 110 mm EU), lamp centres, mirror tips, roof peak.
   Use official overall length, width, height, wheelbase and track. If an overlay shows the model's outline offset or
   scaled the same way all round, the camera is wrong, not the shape: re-solve it before changing the body. Report
   each camera's reprojection error.
3. Loop: change the body → render → silfit for every photo → read the zone offsets and the overlay → repeat.
   Fix the largest-scale errors first: proportions and overall silhouette, then the greenhouse, then the feature
   lines (window frames, lamps, intakes, arches, shut lines).
4. Acceptance per photo:
   - IoU ≥ 0.95;
   - p95 boundary error ≤ 1.5 % of the car's width;
   - no zone offset beyond ±1 %;
   - yellow lines on the photo's window, lamp, intake and arch outlines, within about 1 %.

   Then look at the shaded renders (light silver) for surface quality: smooth reflections, crisp creases where the
   real car has them, no blotches.
5. Report:
   - the silfit table for every photo, before and after;
   - the overlays;
   - your compare sheets and the light-silver front34 / rear34 / side.
