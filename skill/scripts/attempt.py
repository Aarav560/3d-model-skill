"""Sealed attempt workflow for one dataset sample.

  prepare <sample_id>          copy ONLY the inputs (4 reference renders + instruction
                               caption) into runs/attempts/<key>/input/, and preprocess the
                               ground truth (GLB -> mesh -> rig renders) into
                               runs/sealed/<key>/. The attempter never opens runs/sealed/.
  score <sample_id> <code.py> [--round N] [--skill-version V]
                               run the attempt code, render, score, log to the manifest.

Two frames are scored:
  aligned   the attempt mesh is translated/scaled so its bbox center and diagonal match
            the GT (no rotation). Primary for image-only input, because absolute scale is
            not observable from a render.
  absolute  attempt mesh as-is in the GT frame.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import subprocess
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
import sys
sys.path.insert(0, str(HERE))
import run_sample  # noqa: E402
import score as scorer  # noqa: E402

ATTEMPTS = ROOT / "runs" / "attempts"
SEALED = ROOT / "runs" / "sealed"


def _paths(sample_id: str):
    subset, key = sample_id.rsplit("/", 1)
    return ROOT / "data" / "extracted" / subset / key, ATTEMPTS / key, SEALED / key


def _render(mesh: Path, frame: Path, out: Path) -> bool:
    p = subprocess.run(run_sample.blender_cmd(HERE / "render_rig.py", [str(mesh), str(frame), str(out)]),
                       capture_output=True, text=True, timeout=900)
    return p.returncode == 0 and (out / "view_03.png").exists()


def prepare(sample_id: str) -> None:
    src, att, sealed = _paths(sample_id)
    (att / "input").mkdir(parents=True, exist_ok=True)
    for i in range(4):
        shutil.copy(src / "renders" / f"view_{i:02d}.png", att / "input" / f"view_{i:02d}.png")
    caps = json.loads((src / "captions.json").read_text())
    (att / "input" / "task.json").write_text(json.dumps(
        {"sample_id": sample_id, "instruction": caps.get("instruction", "")}, indent=1))
    if not (sealed / "gt_r" / "view_03.png").exists():
        sealed.mkdir(parents=True, exist_ok=True)
        g = run_sample.run("glb", str(src / "renders" / "object.glb"), str(sealed / "gt.npz"))
        if not g["ok"] or not _render(sealed / "gt.npz", sealed / "gt.npz", sealed / "gt_r"):
            raise SystemExit(f"GT preprocessing failed: {g.get('error')}")
    print(f"prepared {att / 'input'}")


def _align(pred: Path, gt: Path, out: Path) -> None:
    p, g = np.load(pred), np.load(gt)
    pv, gv = p["verts"].astype(np.float64), g["verts"].astype(np.float64)
    pc, gc = (pv.min(0) + pv.max(0)) / 2, (gv.min(0) + gv.max(0)) / 2
    s = np.linalg.norm(np.ptp(gv, 0)) / max(np.linalg.norm(np.ptp(pv, 0)), 1e-9)
    np.savez_compressed(out, verts=((pv - pc) * s + gc).astype(np.float32), faces=p["faces"])


def score_attempt(sample_id: str, code: str, rnd: int, skill_version: str) -> dict:
    _, att, sealed = _paths(sample_id)
    d = att / f"round_{rnd:02d}"
    d.mkdir(parents=True, exist_ok=True)
    shutil.copy(code, d / "attempt.py")
    r = run_sample.run("code", str(d / "attempt.py"), str(d / "pred.npz"), timeout=600)
    res = {"sample_id": sample_id, "round": rnd, "skill_version": skill_version,
           "blender_version": r.get("blender_version"), "run_s": r.get("seconds"), "error": r.get("error")}
    ok = r["ok"]
    if ok:
        _align(d / "pred.npz", sealed / "gt.npz", d / "pred_aligned.npz")
        ok = _render(d / "pred_aligned.npz", sealed / "gt.npz", d / "aligned_r") and \
             _render(d / "pred.npz", sealed / "gt.npz", d / "abs_r")
    s_al = scorer.score(str(sealed / "gt_r"), str(d / "aligned_r"), str(sealed / "gt.npz"),
                        str(d / "pred_aligned.npz"), runs_clean=ok)
    s_ab = scorer.score(str(sealed / "gt_r"), str(d / "abs_r"), str(sealed / "gt.npz"),
                        str(d / "pred.npz"), runs_clean=ok) if ok else {"iou_min": 0.0}
    res["aligned"] = s_al
    res["absolute_iou_min"] = s_ab.get("iou_min")
    (d / "score.json").write_text(json.dumps(res, indent=1))
    con = sqlite3.connect(ROOT / "evals" / "manifest.sqlite")
    con.execute("INSERT INTO attempts (sample_id, kind, round, skill_version, blender_version, score_json,"
                " created_at) VALUES (?,?,?,?,?,?,?)",
                (sample_id, "attempt", rnd, skill_version, res["blender_version"], json.dumps(res), time.time()))
    con.execute("UPDATE samples SET attempts = attempts + 1, status='attempted',"
                " best_score = MAX(COALESCE(best_score, 0), ?) WHERE id=?", (s_al.get("iou_min", 0), sample_id))
    con.commit()
    return res


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["prepare", "score"])
    ap.add_argument("sample_id")
    ap.add_argument("code", nargs="?")
    ap.add_argument("--round", type=int, default=1)
    ap.add_argument("--skill-version", default="baseline-noskill")
    a = ap.parse_args()
    if a.cmd == "prepare":
        prepare(a.sample_id)
    else:
        res = score_attempt(a.sample_id, a.code, a.round, a.skill_version)
        s = res["aligned"]
        print(json.dumps({k: res[k] for k in ("sample_id", "round", "error")} |
                         {"aligned_iou_min": s.get("iou_min"), "aligned_iou_mean": s.get("iou_mean"),
                          "chamfer_pct": s.get("chamfer_pct"), "absolute_iou_min": res["absolute_iou_min"]}))


if __name__ == "__main__":
    main()
