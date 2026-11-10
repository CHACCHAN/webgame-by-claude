"""
cam.py: the camera model of the L0 fit (shared by solve.py, sil.py, lamps.py and the Blender compare renders).

Game frame (metres): x = the train's left, y up (0 = the guideway's running surface / the road), z forward; the train
frame is car0's (origin midway between its bogies, its nose tip at z = +20.75). A camera is
[x, y, z, yaw, pitch, roll, f]: its eye, the view direction (yaw about +y from +z, pitch up), the roll about the view
axis, and the focal length in pixels of the photo as used (its width W, height H; the principal point in the middle).
"""
import math

import numpy as np


def basis(yaw, pitch, roll):
    """view direction d, screen right r, screen up u (game frame)"""
    d = np.array([math.sin(yaw) * math.cos(pitch), math.sin(pitch), math.cos(yaw) * math.cos(pitch)])
    r = np.cross(d, [0.0, 1.0, 0.0])
    r /= np.linalg.norm(r)
    u = np.cross(r, d)
    c, s = math.cos(roll), math.sin(roll)
    return d, c * r + s * u, -s * r + c * u


def project(cam, P, W, H):
    """pixels (u right, v down) of the points P (n x 3); depth along the view in the third column"""
    C = np.asarray(cam[:3], float)
    d, r, u = basis(*cam[3:6])
    f = cam[6]
    Q = np.asarray(P, float) - C
    z = Q @ d
    zz = np.where(np.abs(z) < 1e-6, 1e-6, z)
    return np.stack([W / 2 + f * (Q @ r) / zz, H / 2 - f * (Q @ u) / zz, z], 1)


def look_at(eye, target, f, roll=0.0):
    e, t = np.asarray(eye, float), np.asarray(target, float)
    d = t - e
    d /= np.linalg.norm(d)
    return [*e, math.atan2(d[0], d[2]), math.asin(max(-1.0, min(1.0, d[1]))), roll, f]


def from_pnp(P3, P2, W, H, f):
    """a camera from 3D-2D pairs at a given focal length (OpenCV's SQPnP), and its mean reprojection error"""
    import cv2
    K = np.array([[f, 0, W / 2], [0, f, H / 2], [0, 0, 1]], float)
    # (the game frame is right-handed: x left, y up, z forward; OpenCV's camera x right, y down, z forward)
    P = np.asarray(P3, float)
    ok, rv, tv = cv2.solvePnP(np.ascontiguousarray(P, np.float64).reshape(-1, 1, 3), np.ascontiguousarray(P2, np.float64).reshape(-1, 1, 2), K, None, flags=cv2.SOLVEPNP_SQPNP)
    if not ok:
        return None, 1e9
    R, _ = cv2.Rodrigues(rv)
    C = (-R.T @ tv).ravel()
    d = R.T @ np.array([0, 0, 1.0])
    right = R.T @ np.array([1.0, 0, 0])
    yaw = math.atan2(d[0], d[2])
    pitch = math.asin(max(-1, min(1, d[1])))
    _, r0, u0 = basis(yaw, pitch, 0.0)
    roll = math.atan2(right @ u0, right @ r0)
    cam = [*C, yaw, pitch, roll, f]
    e = np.sqrt(((project(cam, P3, W, H)[:, :2] - P2) ** 2).sum(1)).mean()
    return cam, e


def lm(fun, x0, steps=60, lam=1e-3, eps=None, verbose=False):
    """Levenberg-Marquardt on a residual vector fun(x) (numeric Jacobian)"""
    x = np.asarray(x0, float).copy()
    eps = np.full_like(x, 1e-6) if eps is None else np.asarray(eps, float)
    r = fun(x)
    cost = r @ r
    for it in range(steps):
        J = np.empty((len(r), len(x)))
        for k in range(len(x)):
            xk = x.copy()
            xk[k] += eps[k]
            J[:, k] = (fun(xk) - r) / eps[k]
        A = J.T @ J
        g = J.T @ r
        improved = False
        for _ in range(12):
            try:
                dx = -np.linalg.solve(A + lam * np.diag(np.diag(A) + 1e-12), g)
            except np.linalg.LinAlgError:
                lam *= 10
                continue
            r2 = fun(x + dx)
            c2 = r2 @ r2
            if c2 < cost:
                x, r, cost = x + dx, r2, c2
                lam = max(lam / 3, 1e-9)
                improved = True
                break
            lam *= 4
        if verbose:
            print(f'  lm {it} cost {cost:.4f} lam {lam:.1e}')
        if not improved or np.abs(dx).max() < 1e-9:
            break
    return x, cost
