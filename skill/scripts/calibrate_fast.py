"""Fast camera-model calibration on TRAIN samples (numpy point projection, no rendering).

Model: per-view azimuth az_i, shared elevation, lens (36 mm sensor), distance (x bbox diagonal), target offset (dx,dy,dz)
in normalised object space (bbox centre 0, LARGEST DIMENSION 1: measured, the renderer frames by max extent). Objective: mean silhouette IoU between splatted projections of
GT surface samples and the reference alpha masks, over all views and samples.

  python skill/scripts/calibrate_fast.py OUT.json SUBSET N_SAMPLES
"""
import json
import math
import sqlite3
import sys
from pathlib import Path

import cv2
import numpy as np
import trimesh
from scipy.optimize import minimize

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
import run_sample  # noqa: E402

RES = 256
NAMES = ["az0", "az1", "az2", "az3", "el", "lens", "dist", "dx", "dy", "dz"]


def basis(p, i):
    a, e = math.radians(p[i]), math.radians(p[4])
    dv = np.array([math.cos(e) * math.cos(a), math.cos(e) * math.sin(a), math.sin(e)])
    tgt = np.array([p[7], p[8], p[9]])
    C = tgt + dv * p[6]
    f = -dv
    r = np.cross(f, [0, 0, 1.0]); r /= np.linalg.norm(r)
    return C, r, np.cross(r, f), f


def splat_iou(p, pts, masks):
    s = []
    for i, mk in enumerate(masks):
        C, r, u, f = basis(p, i)
        d = pts - C
        zc = d @ f
        fpx = p[5] / 36.0 * RES
        ui = np.round(RES / 2 + fpx * (d @ r) / zc).astype(int)
        vi = np.round(RES / 2 - fpx * (d @ u) / zc).astype(int)
        ok = (ui >= 0) & (ui < RES) & (vi >= 0) & (vi < RES) & (zc > 0)
        pr = np.zeros((RES, RES), np.uint8)
        pr[vi[ok], ui[ok]] = 1
        pr = cv2.dilate(pr, np.ones((3, 3), np.uint8)) > 0
        s.append((pr & mk).sum() / max((pr | mk).sum(), 1))
    return float(np.mean(s))


def load(sid):
    key = sid.rsplit("/", 1)[1]
    src = ROOT / "data" / "extracted" / sid.rsplit("/", 1)[0] / key / "renders"
    npz = ROOT / "runs" / "calib2" / f"{key}.npz"
    if not npz.exists():
        run_sample.run("glb", str(src / "object.glb"), str(npz))
    d = np.load(npz)
    v = d["verts"].astype(float)
    c, size = (v.min(0) + v.max(0)) / 2, np.ptp(v, 0).max()
    m = trimesh.Trimesh((v - c) / size, d["faces"], process=False)
    pts, _ = trimesh.sample.sample_surface(m, 120000, seed=0)
    ms = []
    for i in range(4):
        im = cv2.imread(str(src / f"view_{i:02d}.png"), cv2.IMREAD_UNCHANGED)
        ms.append(cv2.resize(im[..., 3], (RES, RES), interpolation=cv2.INTER_AREA) > 127)
    return pts, ms


def main():
    out, subset, n = sys.argv[1], sys.argv[2], int(sys.argv[3])
    ids = [r[0] for r in sqlite3.connect(ROOT / "evals" / "manifest.sqlite").execute(
        "SELECT id FROM samples WHERE subset=? AND split='train' ORDER BY id", (f"3dcodebench/{subset}",))]
    ids = ids[:: max(1, len(ids) // n)][:n]
    data = [load(s) for s in ids]
    obj = lambda p: -np.mean([splat_iou(p, pts, ms) for pts, ms in data])
    best = None
    for start in ([203.7, 293.8, 24.2, 113.8, 28.0, 65.5, 2.92, 0, 0, 0],):
        r = minimize(obj, np.array(start, float), method="Powell", options={"maxfev": 4000, "xtol": 1e-3, "ftol": 1e-5})
        if best is None or r.fun < best.fun:
            best = r
    per = [round(splat_iou(best.x, pts, ms), 4) for pts, ms in data]
    res = {"params": dict(zip(NAMES, [round(float(x), 4) for x in best.x])), "mean_splat_iou": round(-float(best.fun), 4),
           "per_sample": dict(zip([s.rsplit('/', 1)[1] for s in ids], per)), "fitted_on": "train", "subset": subset}
    Path(out).write_text(json.dumps(res, indent=1))
    print(json.dumps(res))


main()
