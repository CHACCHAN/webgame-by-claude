"""seg.py <fit.json> <state.json> <outdir> [names] [--margin 0.18] : car probability maps by IS-Net (general use,
onnx) on a crop around the model's projection from the current camera; writes <n>_p.png (0..255) and <n>_sov.png
(photo dimmed + 0.5 contour green + model outline red). Pixels outside the crop are 0."""
import json, os, sys
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cv2, numpy as np
import onnxruntime as ort
import fitlib as F
argv = sys.argv[1:]
MARGIN = float(argv[argv.index('--margin') + 1]) if '--margin' in argv else 0.18
argv = [a for i, a in enumerate(argv) if not (a == '--margin' or (i and argv[i - 1] == '--margin'))]
cfg = json.load(open(argv[0])); st = json.load(open(argv[1])); out = argv[2]; os.makedirs(out, exist_ok=True)
base = os.path.dirname(os.path.abspath(argv[0]))
names = argv[3].split(',') if len(argv) > 3 else list(cfg['photos'])
mesh = np.load(os.path.join(base, cfg['mesh']))
MODEL = os.path.join(base, '..', '..', 'segmodel', 'isnet-general-use.onnx')
so = ort.SessionOptions(); so.intra_op_num_threads = 4
sess = ort.InferenceSession(MODEL, so, providers=['CPUExecutionProvider'])
iname = sess.get_inputs()[0].name
for n in names:
    img = cv2.imread(f'{base}/photos/{n}.jpg'); H, W = img.shape[:2]
    c = st['cams'][n]
    uvs = []
    for key in ['body'] + list(F.WHEELS):
        V = mesh['body_v'] if key == 'body' else mesh[f'{key}_v']
        uv, z = F.project(c[:7], V, W, H); uvs.append(uv[z > 0.05])
    uv = np.concatenate(uvs)
    x0, y0 = uv.min(0); x1, y1 = uv.max(0)
    mx, my = (x1 - x0) * MARGIN, (y1 - y0) * MARGIN
    x0, y0 = int(max(0, x0 - mx)), int(max(0, y0 - my)); x1, y1 = int(min(W, x1 + mx)), int(min(H, y1 + my))
    crop = img[y0:y1, x0:x1, ::-1].astype(np.float32)
    inp = cv2.resize(crop, (1024, 1024), interpolation=cv2.INTER_LANCZOS4) / max(crop.max(), 1e-6)
    inp = (inp - 0.5) / 1.0
    pred = sess.run(None, {iname: inp.transpose(2, 0, 1)[None].astype(np.float32)})[0][0, 0]
    pred = (pred - pred.min()) / max(pred.max() - pred.min(), 1e-6)
    p = np.zeros((H, W), np.float32)
    p[y0:y1, x0:x1] = cv2.resize(pred, (x1 - x0, y1 - y0), interpolation=cv2.INTER_LINEAR)
    cv2.imwrite(f'{out}/{n}_p.png', np.clip(p * 255 + 0.5, 0, 255).astype(np.uint8))
    M = np.zeros((H, W), np.uint8)
    for key in ['body'] + list(F.WHEELS):
        V = mesh['body_v'] if key == 'body' else mesh[f'{key}_v']; T = mesh['body_t'] if key == 'body' else mesh[f'{key}_t']
        uv, _ = F.project(c[:7], V, W, H); F.raster(uv, T, W, H, M)
    ov = (img * 0.45).astype(np.uint8)
    ov[F.outline(p > 0.5)] = (0, 255, 0); ov[F.outline(M > 0)] = (0, 0, 255)
    cv2.rectangle(ov, (x0, y0), (x1 - 1, y1 - 1), (255, 200, 0), 1)
    cv2.imwrite(f'{out}/{n}_sov.png', ov)
    print(n, 'crop', (x0, y0, x1, y1), 'car px', int((p > 0.5).sum()), 'model px', int((M > 0).sum()), flush=True)
