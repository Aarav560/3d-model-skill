"""Aggregate attempt scores from the manifest into evals/ tables.

  python skill/scripts/scoreboard.py --skill-version baseline-noskill --list evals/baseline_list.txt

Writes evals/scores_<skill_version>.csv (one row per sample, best round) and appends
one aggregate row per subset plus an overall row to evals/scoreboard.csv.
Pass bar (dataset samples, spec section 5, unconfirmed): aligned silhouette IoU >= 0.98 on all 4 views.
"""
from __future__ import annotations

import argparse
import csv
import json
import sqlite3
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PASS_IOU = 0.98
RIG = "rig-v1"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skill-version", required=True)
    ap.add_argument("--list", required=True, help="fixed sample list (one id per line)")
    a = ap.parse_args()
    ids = [l.strip() for l in open(a.list) if l.strip()]
    con = sqlite3.connect(ROOT / "evals" / "manifest.sqlite")
    rows = []
    for sid in ids:
        best = None
        for (sj,) in con.execute("SELECT score_json FROM attempts WHERE sample_id=? AND kind='attempt' AND skill_version=?",
                                 (sid, a.skill_version)):
            r = json.loads(sj)
            if best is None or r["aligned"].get("iou_min", 0) > best["aligned"].get("iou_min", 0):
                best = r
        if best is None:
            rows.append({"sample": sid, "status": "missing"})
            continue
        s = best["aligned"]
        rows.append({"sample": sid, "subset": sid.rsplit("/", 1)[0].split("/")[-1], "status": "ok" if s.get("runs_clean") else "crash",
                     "rounds": best["round"], "iou_min": s.get("iou_min"), "iou_mean": s.get("iou_mean"),
                     "ssim": s.get("ssim_mean"), "lpips": s.get("lpips_mean"), "chamfer_pct": s.get("chamfer_pct"),
                     "abs_iou_min": best.get("absolute_iou_min"), "blender": best.get("blender_version"),
                     "pass": int((s.get("iou_min") or 0) >= PASS_IOU)})
    out = ROOT / "evals" / f"scores_{a.skill_version}.csv"
    cols = ["sample", "subset", "status", "rounds", "iou_min", "iou_mean", "ssim", "lpips", "chamfer_pct", "abs_iou_min", "blender", "pass"]
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, cols)
        w.writeheader()
        w.writerows(rows)
    groups = {}
    for r in rows:
        groups.setdefault(r.get("subset", "?"), []).append(r)
    groups["ALL"] = rows
    with open(ROOT / "evals" / "scoreboard.csv", "a") as f:
        for g, rs in groups.items():
            ious = [r.get("iou_min") or 0 for r in rs]
            line = f"{a.skill_version},{rs[0].get('blender')},{RIG},held_out,{g},{len(rs)},{statistics.mean(ious):.4f},{sum(r.get('pass', 0) for r in rs) / len(rs):.2f}\n"
            f.write(line)
            print(line.strip(), f"median={statistics.median(ious):.4f}")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
