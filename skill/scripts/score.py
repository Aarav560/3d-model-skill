"""Score a predicted mesh against ground truth (section 5 of the spec).

Metrics:
  iou_v0..3, iou_min, iou_mean  silhouette IoU per rig view (main pass/fail)
  ssim_mean                     SSIM of the shaded grey render (composited on white)
  lpips_mean                    LPIPS (AlexNet) of the shaded render, lower is better
  chamfer_pct                   symmetric mean chamfer distance, % of GT bbox diagonal
  volume_ratio                  pred/GT enclosed volume (only when both are watertight)
  runs_clean                    False -> every score is 0 (a crash scores 0)

  python skill/scripts/score.py gt_render_dir pred_render_dir gt.npz pred.npz
"""
from __future__ import annotations

import json
import sys
from functools import lru_cache
from pathlib import Path

import numpy as np

N_VIEWS = 4
N_POINTS = 100_000
POINT_SEED = 0


def _load_rgba(p: Path) -> np.ndarray:
    import cv2
    im = cv2.imread(str(p), cv2.IMREAD_UNCHANGED)
    return cv2.cvtColor(im, cv2.COLOR_BGRA2RGBA)


def _on_white(rgba: np.ndarray) -> np.ndarray:
    a = rgba[..., 3:4].astype(np.float32) / 255
    return (rgba[..., :3].astype(np.float32) * a + 255 * (1 - a)).astype(np.uint8)


@lru_cache(maxsize=1)
def _lpips_model():
    import lpips
    return lpips.LPIPS(net="alex", verbose=False).eval()


def _lpips(a: np.ndarray, b: np.ndarray) -> float:
    import torch
    t = lambda x: torch.from_numpy(x).permute(2, 0, 1)[None].float() / 127.5 - 1
    with torch.no_grad():
        return float(_lpips_model()(t(a), t(b)).item())


def image_metrics(gt_dir: str, pred_dir: str) -> dict:
    from skimage.metrics import structural_similarity as ssim
    out, ious, ssims, lps = {}, [], [], []
    for i in range(N_VIEWS):
        g = _load_rgba(Path(gt_dir) / f"view_{i:02d}.png")
        p = _load_rgba(Path(pred_dir) / f"view_{i:02d}.png")
        mg, mp = g[..., 3] > 127, p[..., 3] > 127
        union = (mg | mp).sum()
        iou = float((mg & mp).sum() / union) if union else 1.0
        gw, pw = _on_white(g), _on_white(p)
        s = float(ssim(gw.mean(2), pw.mean(2), data_range=255))
        ious.append(iou); ssims.append(s); lps.append(_lpips(gw, pw))
        out[f"iou_v{i}"] = round(iou, 4)
    out.update(iou_min=round(min(ious), 4), iou_mean=round(float(np.mean(ious)), 4),
               ssim_mean=round(float(np.mean(ssims)), 4), lpips_mean=round(float(np.mean(lps)), 4))
    return out


def geometry_metrics(gt_npz: str, pred_npz: str) -> dict:
    import trimesh
    from scipy.spatial import cKDTree
    def mesh(path):
        d = np.load(path)
        return trimesh.Trimesh(vertices=d["verts"], faces=d["faces"], process=False)
    g, p = mesh(gt_npz), mesh(pred_npz)
    diag = float(np.linalg.norm(g.bounds[1] - g.bounds[0]))
    pg, _ = trimesh.sample.sample_surface(g, N_POINTS, seed=POINT_SEED)
    pp, _ = trimesh.sample.sample_surface(p, N_POINTS, seed=POINT_SEED)
    d_pg = cKDTree(pg).query(pp)[0]   # pred -> gt  (accuracy)
    d_gp = cKDTree(pp).query(pg)[0]   # gt -> pred  (completeness)
    chamfer = (d_pg.mean() + d_gp.mean()) / 2
    res = {"chamfer_pct": round(100 * chamfer / diag, 4),
           "chamfer_acc_pct": round(100 * d_pg.mean() / diag, 4),
           "chamfer_comp_pct": round(100 * d_gp.mean() / diag, 4),
           "gt_diag": round(diag, 5)}
    pm, gm = trimesh.Trimesh(p.vertices, p.faces), trimesh.Trimesh(g.vertices, g.faces)  # merged verts
    if pm.is_watertight and gm.is_watertight and abs(gm.volume) > 0:
        res["volume_ratio"] = round(float(abs(pm.volume) / abs(gm.volume)), 4)
    else:
        res["volume_ratio"] = None  # not defined for open meshes; reported, not faked
    return res


def score(gt_dir: str, pred_dir: str, gt_npz: str, pred_npz: str, runs_clean: bool = True) -> dict:
    if not runs_clean:
        return {"runs_clean": False, "iou_min": 0.0, "iou_mean": 0.0, "ssim_mean": 0.0,
                "lpips_mean": 1.0, "chamfer_pct": None, "volume_ratio": None}
    r = {"runs_clean": True}
    r.update(image_metrics(gt_dir, pred_dir))
    r.update(geometry_metrics(gt_npz, pred_npz))
    return r


if __name__ == "__main__":
    print(json.dumps(score(*sys.argv[1:5]), indent=1))
