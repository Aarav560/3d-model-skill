"""Multi-view reconstruction of a dataset sample from its 4 reference renders (visual hull).

Uses ONLY the inputs (reference PNGs with alpha) + the calibrated camera model of the subset
(skill/references/cameras_<subset>.json, fitted on TRAIN samples by calibrate_cams.py).
GT is touched only by the scorer after reconstruction.

  python skill/scripts/recon.py <sample_id> [--res 160] [--skill-version recon-hull-v1]

Pipeline: alpha masks -> carve a voxel grid in normalised object space (bbox centre 0, largest dimension 1;
the renderer frames each object by its max extent, measured on train samples) -> marching cubes -> pred.npz -> attempt scoring (aligned + absolute).
"""
from __future__ import annotations

import argparse
import json
import math
import shutil
import time
from pathlib import Path

import cv2
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
import sys  # noqa: E402
sys.path.insert(0, str(HERE))
import attempt  # noqa: E402
import score as scorer  # noqa: E402


def cam_basis(params, i):
    a, e = math.radians(params[f"az{i}"]), math.radians(params["el"])
    dv = np.array([math.cos(e) * math.cos(a), math.cos(e) * math.sin(a), math.sin(e)])
    tgt = np.array([params["dx"], params["dy"], params["dz"]])
    C = tgt + dv * params["dist"]
    f = -dv
    r = np.cross(f, [0, 0, 1.0]); r /= np.linalg.norm(r)
    u = np.cross(r, f)
    return C, r, u, f


def project(P, params, i, W):
    C, r, u, f = cam_basis(params, i)
    d = P - C
    zc = d @ f
    fpx = params["lens"] / 36.0 * W
    return W / 2 + fpx * (d @ r) / zc, W / 2 - fpx * (d @ u) / zc


def masks(input_dir):
    out = []
    for i in range(4):
        im = cv2.imread(str(Path(input_dir) / f"view_{i:02d}.png"), cv2.IMREAD_UNCHANGED)
        a = im[..., 3] if im.ndim == 3 and im.shape[2] == 4 else (im[..., :3].max(2) > 8).astype(np.uint8) * 255
        out.append(a > 127)
    return out


def carve(ms, params, res, extent=0.505):   # renderer normalises max extent to 1 around the target -> |x|,|y|,|z| <= 0.5
    W = ms[0].shape[1]
    g = np.linspace(-extent, extent, res)
    X, Y, Z = np.meshgrid(g, g, g, indexing="ij")
    P = np.stack([X.ravel(), Y.ravel(), Z.ravel()], 1)
    occ = np.ones(len(P), bool)
    for i, m in enumerate(ms):
        u, v = project(P[occ], params, i, W)
        ui, vi = np.round(u).astype(int), np.round(v).astype(int)
        inside = (ui >= 0) & (ui < W) & (vi >= 0) & (vi < W)
        keep = np.zeros(len(ui), bool)
        keep[inside] = m[vi[inside], ui[inside]]
        idx = np.nonzero(occ)[0]
        occ[idx[~keep]] = False
    vol = occ.reshape(res, res, res)
    # prior from calibration: the camera target is the bbox centre (dz ~ 0), so the bbox is symmetric in z.
    # Elevated views constrain the top well but never see the underside: clip the bottom to -(top).
    zs = np.nonzero(vol.any(axis=(0, 1)))[0]
    if len(zs):
        top = g[zs.max()] - params["dz"]
        vol[:, :, g < params["dz"] - top] = False
    return vol, g


def to_mesh(vol, g, out, smooth=0.0, thr=0.5):
    """smooth/thr: blur the occupancy and threshold it. thr > 0.5 shaves the corners that 4-view carving
    leaves at 45 deg between the views (a round object carves to a rounded square)."""
    from scipy import ndimage
    from skimage import measure
    if vol.sum() == 0:
        return False
    v = vol.astype(np.float32)
    if smooth > 0:
        v = ndimage.gaussian_filter(v, smooth)
    v = np.pad(v, 1)
    if v.max() <= thr:
        return False
    verts, faces, _, _ = measure.marching_cubes(v, thr)
    step = g[1] - g[0]
    verts = (verts - 1) * step + g[0]
    np.savez_compressed(out, verts=verts.astype(np.float32), faces=faces.astype(np.int32))
    return True


def run(sid, res, skill, smooth=0.0, thr=0.5, tag=""):
    subset = sid.split("/")[1]
    params = json.loads((ROOT / "skill" / "references" / f"cameras_{subset}.json").read_text())["params"]
    key = sid.rsplit("/", 1)[1]
    att = ROOT / "runs" / "recon" / (key + tag)
    att.mkdir(parents=True, exist_ok=True)
    src_in = ROOT / "data" / "extracted" / sid.rsplit("/", 1)[0] / key / "renders"
    t0 = time.time()
    vol, g = carve(masks(src_in), params, res)
    ok = to_mesh(vol, g, att / "pred.npz", smooth, thr)
    res_d = {"sample_id": sid, "skill_version": skill, "seconds": None}
    sealed = ROOT / "runs" / "sealed" / key
    if not (sealed / "gt_r" / "view_03.png").exists():
        attempt.prepare(sid)
    if ok:
        attempt._align(att / "pred.npz", sealed / "gt.npz", att / "pred_aligned.npz")
        ok = attempt._render(att / "pred_aligned.npz", sealed / "gt.npz", att / "aligned_r")
    s = scorer.score(str(sealed / "gt_r"), str(att / "aligned_r"), str(sealed / "gt.npz"), str(att / "pred_aligned.npz"), runs_clean=ok)
    res_d.update(aligned=s, seconds=round(time.time() - t0, 1), voxels=int(vol.sum()))
    (att / "score.json").write_text(json.dumps(res_d, indent=1))
    with open(ROOT / "runs" / "recon_log.jsonl", "a") as f:
        f.write(json.dumps({"sample": sid, "skill": skill, "smooth": smooth, "thr": thr, "iou_min": s.get("iou_min"), "iou_mean": s.get("iou_mean"),
                            "chamfer_pct": s.get("chamfer_pct"), "seconds": res_d["seconds"], "t": time.time()}) + "\n")
    print(json.dumps({"sample": key, "iou_min": s.get("iou_min"), "iou_mean": s.get("iou_mean"), "chamfer": s.get("chamfer_pct"),
                      "sec": res_d["seconds"]}))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("sample_id")
    ap.add_argument("--res", type=int, default=160)
    ap.add_argument("--skill-version", default="recon-hull-v1")
    ap.add_argument("--smooth", type=float, default=0.0)
    ap.add_argument("--thr", type=float, default=0.5)
    ap.add_argument("--tag", default="")
    a = ap.parse_args()
    run(a.sample_id, a.res, a.skill_version, a.smooth, a.thr, a.tag)
