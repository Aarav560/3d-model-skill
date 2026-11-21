"""Milestone 1 exit test: run the dataset's own ground-truth code through the rig and
check it scores ~1.0 against the dataset's ground-truth GLB.

For each of N fixed TRAIN samples (held-out samples are never touched here):
  gt.npz    <- import renders/object.glb   (sealed ground truth mesh)
  pred.npz  <- exec code.py with SEED=0    (the dataset's own program)
  ctrl.npz  <- exec code.py with SEED=1    (negative control: a different instance
                                            should score clearly LOWER, proving the
                                            scorer discriminates)
Then render all three on the fixed rig (GT frame) and score pred/ctrl vs gt.

  python skill/scripts/validate_scorer.py --n 20 --workers 3
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sqlite3
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
import run_sample  # noqa: E402
import score as scorer  # noqa: E402

SKILL_VERSION = "m1-harness"
SUBSET = "3dcodebench/factories_geo"


def pick_samples(n: int) -> list[str]:
    con = sqlite3.connect(ROOT / "evals" / "manifest.sqlite")
    ids = [r[0] for r in con.execute(
        "SELECT id FROM samples WHERE subset=? AND split='train'", (SUBSET,))]
    # fixed pseudo-random order (not alphabetical, so categories are mixed)
    ids.sort(key=lambda s: hashlib.sha256(f"m1-pick:{s}".encode()).hexdigest())
    return ids[:n]


def render(mesh: Path, frame_mesh: Path, out: Path) -> bool:
    p = subprocess.run([sys.executable, str(HERE / "render_rig.py"), str(mesh), str(frame_mesh), str(out)],
                       capture_output=True, text=True, timeout=900)
    return p.returncode == 0 and (out / "view_03.png").exists()


def one(sample_id: str, run_dir: Path) -> dict:
    key = sample_id.split("/")[-1]
    src = ROOT / "data" / "extracted" / SUBSET / key
    out = run_dir / key
    out.mkdir(parents=True, exist_ok=True)
    row = {"sample": key}
    t0 = time.time()
    g = run_sample.run("glb", str(src / "renders" / "object.glb"), str(out / "gt.npz"))
    if not g["ok"]:
        return {**row, "status": "gt_glb_failed", "error": g.get("error")}
    render(out / "gt.npz", out / "gt.npz", out / "gt_r")
    for tag, seed in (("pred", 0), ("ctrl", 1)):
        r = run_sample.run("code", str(src / "code.py"), str(out / f"{tag}.npz"), seed=seed)
        row[f"{tag}_run_s"] = r["seconds"]
        ok = r["ok"] and render(out / f"{tag}.npz", out / "gt.npz", out / f"{tag}_r")
        if not ok:
            row[f"{tag}_error"] = r.get("error", "render failed")
        s = scorer.score(str(out / "gt_r"), str(out / f"{tag}_r"), str(out / "gt.npz"),
                         str(out / f"{tag}.npz"), runs_clean=ok)
        row.update({f"{tag}_{k}": v for k, v in s.items()})
        row["blender_version"] = r.get("blender_version", g.get("blender_version"))
    row["status"] = "ok" if row.get("pred_runs_clean") else "code_failed"
    row["seconds"] = round(time.time() - t0, 1)
    print(f"{key:40s} pred iou_min={row.get('pred_iou_min')} chamfer={row.get('pred_chamfer_pct')} | "
          f"ctrl iou_min={row.get('ctrl_iou_min')}  ({row['seconds']}s)", flush=True)
    return row


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=20)
    ap.add_argument("--workers", type=int, default=3)
    a = ap.parse_args()
    run_dir = ROOT / "runs" / "m1_validation"
    ids = pick_samples(a.n)
    scorer._lpips_model()  # load once before threads start
    with ThreadPoolExecutor(a.workers) as ex:
        rows = list(ex.map(lambda s: one(s, run_dir), ids))

    con = sqlite3.connect(ROOT / "evals" / "manifest.sqlite")
    for sid, r in zip(ids, rows):
        con.execute("INSERT INTO attempts (sample_id, kind, round, skill_version, blender_version,"
                    " score_json, created_at) VALUES (?,?,?,?,?,?,?)",
                    (sid, "scorer_validation", 0, SKILL_VERSION, r.get("blender_version"),
                     json.dumps(r), time.time()))
    con.commit()

    cols = sorted({k for r in rows for k in r}, key=lambda k: (k != "sample", k))
    with open(run_dir / "results.csv", "w", newline="") as f:
        w = csv.DictWriter(f, cols)
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {run_dir / 'results.csv'}")


if __name__ == "__main__":
    main()
