"""raypl.py helpers: rays from a solved camera through pixels, cut with planes x = c (game frame)"""
import json, math, os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bsolve as S


def ray(cam, u, v):
    C = np.array(cam[:3]); d, r, up = S.basis(*cam[3:6]); f = cam[6]; W, H = cam[7]
    return C, d + r * (u - W / 2) / f + up * (H / 2 - v) / f


def on_x(cam, u, v, x):
    C, D = ray(cam, u, v)
    t = (x - C[0]) / D[0]
    return C + D * t
