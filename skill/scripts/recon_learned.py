"""Learned multi-view reconstruction ("recon-learned-v1").

The visual hull from 4 elevated views is always a superset of the object (bulges between views, unseen undersides).
A classifier trained on TRAIN samples learns which hull voxels are really solid, from per-voxel features that come
only from the 4 input masks: signed distance to each silhouette edge (per view and sorted), and position.

  build  SUBSET N_TRAIN OUT.npz        features + GT-occupancy labels from N train samples (GT used only here, train only)
  train  DATA.npz MODEL.joblib         fit HistGradientBoostingClassifier
  run    SAMPLE_ID MODEL.joblib [--tag T] [--skill V]    reconstruct + score one sample (inputs only, then scorer)
"""
from __future__ import annotations

import json
import math
import sqlite3
import sys
import time
from pathlib import Path

import cv2
import numpy as np
from scipy import ndimage

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
import recon  # noqa: E402

RES = 128
EXT = 0.505
FEATS = ["d0", "d1", "d2", "d3", "s0", "s1", "s2", "s3", "dmean", "x", "y", "z", "r", "zrel", "rrel"]


def cams(subset):
    return json.loads((ROOT / "skill" / "references" / f"cameras_{subset}.json").read_text())["params"]


def signed_dist(mask):
    inside = ndimage.distance_transform_edt(mask)
    outside = ndimage.distance_transform_edt(~mask)
    return np.where(mask, inside, -outside).astype(np.float32)


def features(renders_dir, params):
    ms = recon.masks(renders_dir)
    W = ms[0].shape[1]
    px_world = params["dist"] / (params["lens"] / 36.0 * W)       # world units per pixel at the object
    sds = [signed_dist(m) for m in ms]
    g = np.linspace(-EXT, EXT, RES)
    X, Y, Z = np.meshgrid(g, g, g, indexing="ij")
    P = np.stack([X.ravel(), Y.ravel(), Z.ravel()], 1)
    D = np.empty((len(P), 4), np.float32)
    for i, sd in enumerate(sds):
        u, v = recon.project(P, params, i, W)
        ui, vi = np.clip(np.round(u).astype(int), 0, W - 1), np.clip(np.round(v).astype(int), 0, W - 1)
        D[:, i] = sd[vi, ui] * px_world
    hull = D.min(1) > 0
    # z-symmetric bbox prior (camera target = bbox centre): clip the unseen underside
    hz = P[hull, 2]
    if len(hz):
        top = hz.max() - params["dz"]
        hull &= P[:, 2] >= params["dz"] - top
    idx = np.nonzero(hull)[0]
    Ph, Dh = P[idx], D[idx]
    r = np.linalg.norm(Ph[:, :2], axis=1)
    zr = (Ph[:, 2] - Ph[:, 2].min()) / max(np.ptp(Ph[:, 2]), 1e-6)
    rr = r / max(r.max(), 1e-6)
    F = np.column_stack([Dh, np.sort(Dh, 1), Dh.mean(1), Ph, r, zr, rr]).astype(np.float32)
    return F, idx, g


def gt_occupancy(gt_npz, points):
    import trimesh
    d = np.load(gt_npz)
    v = d["verts"].astype(np.float64)
    c, size = (v.min(0) + v.max(0)) / 2, np.ptp(v, 0).max()
    m = trimesh.Trimesh((v - c) / size, d["faces"], process=False)
    pitch = 2 * EXT / (RES - 1)
    vg = m.voxelized(pitch).fill()
    return vg.is_filled(points)


def build(subset, n, out, part=0, nparts=1):
    import run_sample
    params = cams(subset)
    ids = [r[0] for r in sqlite3.connect(ROOT / "evals" / "manifest.sqlite").execute(
        "SELECT id FROM samples WHERE subset=? AND split='train' ORDER BY id", (f"3dcodebench/{subset}",))]
    have = [s for s in ids if (ROOT / "data" / "extracted" / s.rsplit("/", 1)[0] / s.rsplit("/", 1)[1]).exists()]
    pick = have[:: max(1, len(have) // n)][:n][part::nparts]
    Xs, ys, names = [], [], []
    rng = np.random.default_rng(0)
    for sid in pick:
        key = sid.rsplit("/", 1)[1]
        src = ROOT / "data" / "extracted" / sid.rsplit("/", 1)[0] / key / "renders"
        npz = ROOT / "runs" / "calib2" / f"{key}.npz"
        if not npz.exists():
            r = run_sample.run("glb", str(src / "object.glb"), str(npz))
            if not r["ok"]:
                continue
        F, idx, g = features(src, params)
        if len(idx) == 0:
            continue
        X, Y, Z = np.meshgrid(g, g, g, indexing="ij")
        P = np.stack([X.ravel(), Y.ravel(), Z.ravel()], 1)[idx]
        y = gt_occupancy(npz, P)
        k = min(len(idx), 20000)
        sel = rng.choice(len(idx), k, replace=False)
        Xs.append(F[sel]); ys.append(y[sel]); names += [key] * k
        print(f"{key}: hull {len(idx)} voxels, solid frac {y.mean():.2f}", flush=True)
    np.savez_compressed(out, X=np.concatenate(Xs), y=np.concatenate(ys), names=np.array(names))


def train(data, model_out):
    import joblib
    from sklearn.ensemble import HistGradientBoostingClassifier
    d = np.load(data)
    clf = HistGradientBoostingClassifier(max_iter=300, learning_rate=0.08, max_leaf_nodes=63, l2_regularization=1.0,
                                         early_stopping=True, validation_fraction=0.1, random_state=0)
    clf.fit(d["X"], d["y"])
    joblib.dump(clf, model_out)
    print(f"trained on {len(d['y'])} voxels from {len(set(d['names']))} train samples; "
          f"train acc {clf.score(d['X'], d['y']):.3f}; base rate {d['y'].mean():.3f}")


def run(sid, model_path, tag="_learned", skill="recon-learned-v1", thr=0.5, smooth=1.0):
    import joblib  # loads only the model this project trains itself (runs/learned), never downloaded files
    import attempt
    import score as scorer
    subset = sid.split("/")[1]
    params = cams(subset)
    key = sid.rsplit("/", 1)[1]
    src = ROOT / "data" / "extracted" / sid.rsplit("/", 1)[0] / key / "renders"
    att = ROOT / "runs" / "recon" / (key + tag)
    att.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    F, idx, g = features(src, params)
    vol = np.zeros(RES ** 3, np.float32)
    if len(idx):
        vol[idx] = joblib.load(model_path).predict_proba(F)[:, 1]
    vol = vol.reshape(RES, RES, RES)
    ok = recon.to_mesh(vol, g, att / "pred.npz", smooth, thr)
    sealed = ROOT / "runs" / "sealed" / key
    if not (sealed / "gt_r" / "view_03.png").exists():
        attempt.prepare(sid)
    if ok:
        attempt._align(att / "pred.npz", sealed / "gt.npz", att / "pred_aligned.npz")
        ok = attempt._render(att / "pred_aligned.npz", sealed / "gt.npz", att / "aligned_r")
    s = scorer.score(str(sealed / "gt_r"), str(att / "aligned_r"), str(sealed / "gt.npz"), str(att / "pred_aligned.npz"),
                     runs_clean=ok)
    rec = {"sample": sid, "skill": skill, "iou_min": s.get("iou_min"), "iou_mean": s.get("iou_mean"),
           "chamfer_pct": s.get("chamfer_pct"), "seconds": round(time.time() - t0, 1), "t": time.time()}
    (att / "score.json").write_text(json.dumps({**rec, "aligned": s}, indent=1))
    with open(ROOT / "runs" / "recon_log.jsonl", "a") as f:
        f.write(json.dumps(rec) + "\n")
    print(json.dumps({k: rec[k] for k in ("sample", "iou_min", "iou_mean", "chamfer_pct", "seconds")}))
    return rec


if __name__ == "__main__":
    cmd, *a = sys.argv[1:]
    if cmd == "build":
        build(a[0], int(a[1]), a[2], int(a[3]) if len(a) > 3 else 0, int(a[4]) if len(a) > 4 else 1)
    elif cmd == "train":
        train(a[0], a[1])
    elif cmd == "run":
        tag = a[a.index("--tag") + 1] if "--tag" in a else "_learned"
        skill = a[a.index("--skill") + 1] if "--skill" in a else "recon-learned-v1"
        run(a[0], a[1], tag, skill)
