"""lampfit.py <bike> <loopdir> <photos...> : lamp outlines. fit/lamps.json {photo: {lamp: {"poly": [[u,v]...], "mat": "headlight" | "mats": [..]}}}
The model's lamp = pixels of that material in <photo>_ids.png (palette.json) within the lamp's box (+40 %);
prints IoU, mean and max outline deviation (px) and writes <loopdir>/<photo>_<lamp>_lamp.png (photo crop | render crop)."""
import json, os, sys
import cv2, numpy as np
from PIL import Image, ImageDraw
B = os.path.expanduser('~/.local/opt/carfit/bikes')
bike, ld = sys.argv[1], sys.argv[2]
L = json.load(open(f'{B}/{bike}/fit/lamps.json'))
pal = json.load(open(f'{ld}/palette.json'))
res = {}
for n in sys.argv[3:]:
    if n not in L: continue
    ph = Image.open(f'{B}/{bike}/ref/{n}.jpg').convert('RGB'); W, H = ph.size
    ids = np.array(Image.open(f'{ld}/{n}_ids.png').convert('RGBA').resize((W, H), Image.NEAREST)).astype(int)
    sh = Image.open(f'{ld}/{n}_shade.png').convert('RGBA').resize((W, H), Image.LANCZOS)
    bg = Image.new('RGBA', (W, H), (90, 96, 104, 255)); bg.alpha_composite(sh); sh = bg.convert('RGB')
    for lamp, spec in L[n].items():
        poly = np.array(spec['poly'], float)
        mats = spec.get('mats') or [spec.get('mat', 'headlight')]
        x0, y0 = poly.min(0); x1, y1 = poly.max(0); w, h = x1 - x0, y1 - y0
        bx0, by0, bx1, by1 = int(max(0, x0 - 0.4 * w)), int(max(0, y0 - 0.4 * h)), int(min(W, x1 + 0.4 * w)), int(min(H, y1 + 0.4 * h))
        M = np.zeros((H, W), bool)
        for mt in mats:
            M |= (np.abs(ids[:, :, :3] - np.array(pal[mt])[None, None]).sum(2) < 12) & (ids[:, :, 3] > 127)
        box = np.zeros_like(M); box[by0:by1, bx0:bx1] = True
        M &= box
        k = np.ones((3, 3), np.uint8)
        M = cv2.morphologyEx(M.astype(np.uint8), cv2.MORPH_CLOSE, k, iterations=2).astype(bool)
        Pm = np.zeros((H, W), np.uint8); cv2.fillPoly(Pm, [poly.round().astype(np.int32)], 1); Pm = Pm.astype(bool)
        # only this lamp: drop separate blobs that do not touch the traced lens (the pair's other lamp peeking past
        # the nose); their pixel count is reported as other_px
        nl, lab = cv2.connectedComponents(M.astype(np.uint8))
        near = cv2.dilate(Pm.astype(np.uint8), np.ones((9, 9), np.uint8)).astype(bool)
        keep = np.isin(lab, [i for i in range(1, nl) if (near & (lab == i)).any()])
        other_px = int((M & ~keep).sum())
        M = keep
        if spec.get('fill'):
            # a housing scored by its rim and walls: fill what lies inside them (the lens drawn over its back)
            ff = (~M).astype(np.uint8); cv2.floodFill(ff, None, (0, 0), 0)
            M |= ff.astype(bool)
        inter, uni = (M & Pm).sum(), (M | Pm).sum()
        iou = inter / max(1, uni)
        eP = Pm.astype(np.uint8) - cv2.erode(Pm.astype(np.uint8), k); eM = M.astype(np.uint8) - cv2.erode(M.astype(np.uint8), k)
        if eM.sum() == 0:
            print(f'{n} {lamp}: model lamp not visible'); continue
        dtP = cv2.distanceTransform(1 - eP, cv2.DIST_L2, 5); dtM = cv2.distanceTransform(1 - eM, cv2.DIST_L2, 5)
        d1 = dtP[eM.astype(bool)]; d2 = dtM[eP.astype(bool)]
        mx = float(max(d1.max(), d2.max())); mean = float(np.concatenate([d1, d2]).mean())
        cy, cx = np.argwhere(M).mean(0); py, px = np.argwhere(Pm).mean(0)
        res[f'{n}/{lamp}'] = {'iou': round(float(iou), 3), 'mean_px': round(mean, 1), 'max_px': round(mx, 1),
                              'centre_shift_px': [round(float(cx - px), 1), round(float(cy - py), 1)],
                              'size_model_vs_photo': [round(float(np.ptp(np.argwhere(M)[:, 1]) / max(1, np.ptp(poly[:, 0]))), 2),
                                                      round(float(np.ptp(np.argwhere(M)[:, 0]) / max(1, np.ptp(poly[:, 1]))), 2)],
                              'lamp_width_px': round(float(w), 1), 'other_lamp_px': other_px}
        r = res[f'{n}/{lamp}']
        print(f'{n} {lamp}: IoU {r["iou"]:.3f} mean {r["mean_px"]} max {r["max_px"]} px (lamp {w:.0f} px wide) centre shift {r["centre_shift_px"]} size ratio {r["size_model_vs_photo"]}')
        # close-up pair
        pad = 1.0
        cx0, cy0, cx1, cy1 = int(max(0, x0 - pad * w)), int(max(0, y0 - pad * h * 1.5)), int(min(W, x1 + pad * w)), int(min(H, y1 + pad * h * 1.5))
        a = ph.crop((cx0, cy0, cx1, cy1)); b = sh.crop((cx0, cy0, cx1, cy1))
        s = 360 / a.size[1]
        a = a.resize((int(a.size[0] * s), 360), Image.LANCZOS); b = b.resize(a.size, Image.LANCZOS)
        for im, draw_model in ((a, False), (b, True)):
            d = ImageDraw.Draw(im)
            d.line([((u - cx0) * s, (v - cy0) * s) for u, v in list(poly) + [poly[0]]], fill=(60, 255, 60), width=2)
            cs, _ = cv2.findContours(M[cy0:cy1, cx0:cx1].astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
            for c in cs:
                d.line([(p[0][0] * s, p[0][1] * s) for p in c] + [(c[0][0][0] * s, c[0][0][1] * s)], fill=(255, 60, 60), width=2)
        o = Image.new('RGB', (a.size[0] * 2 + 8, 360), 'white'); o.paste(a, (0, 0)); o.paste(b, (a.size[0] + 8, 0))
        o.save(f'{ld}/{n}_{lamp}_lamp.png')
json.dump(res, open(f'{ld}/lamps_score.json', 'w'), indent=1)
