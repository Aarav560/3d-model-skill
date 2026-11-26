"""Unattended shard-by-shard cycle (Milestone 5): download -> reconstruct + score every sample -> log -> delete.
Resumable: samples already in runs/batch/<skill>.jsonl are skipped, so a killed run continues where it stopped.

  python skill/scripts/batch_dataset.py SUBSET MODEL.joblib --shards 0-7 [--workers 4] [--skill recon-learned-v1]
"""
from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PY = sys.executable


def done_set(log):
    if not log.exists():
        return set()
    return {json.loads(l)["sample"] for l in open(log) if l.strip()}


def one(sid, model, skill, log):
    p = subprocess.run([PY, str(HERE / "recon_learned.py"), "run", sid, model, "--tag", "_batch", "--skill", skill],
                       capture_output=True, text=True, timeout=1800)
    line = next((l for l in p.stdout.splitlines()[::-1] if l.startswith("{")), None)
    rec = json.loads(line) if line else {"sample": sid, "iou_min": 0.0, "error": (p.stderr or "")[-300:]}
    split = sqlite3.connect(ROOT / "evals" / "manifest.sqlite").execute("SELECT split FROM samples WHERE id=?", (sid,)).fetchone()
    rec["split"] = split[0] if split else "?"
    with open(log, "a") as f:
        f.write(json.dumps(rec) + "\n")
    # keep disk bounded: drop the per-sample working files, keep the score
    for d in (ROOT / "runs" / "recon" / (sid.rsplit("/", 1)[1] + "_batch"),):
        for fn in ("pred.npz", "pred_aligned.npz"):
            (d / fn).unlink(missing_ok=True)
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("subset"); ap.add_argument("model")
    ap.add_argument("--shards", default="0-7"); ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--skill", default="recon-learned-v1")
    a = ap.parse_args()
    lo, hi = (int(x) for x in a.shards.split("-"))
    log = ROOT / "runs" / "batch" / f"{a.skill}.jsonl"
    log.parent.mkdir(parents=True, exist_ok=True)
    for k in range(lo, hi + 1):
        shard = f"samples-{k:03d}.tar"
        t0 = time.time()
        subprocess.run([PY, str(HERE / "shard_manager.py"), "fetch", "--subset", f"3dcodebench/{a.subset}", "--shard", shard],
                       capture_output=True, text=True)
        ids = [r[0] for r in sqlite3.connect(ROOT / "evals" / "manifest.sqlite").execute(
            "SELECT id FROM samples WHERE subset=? AND shard=? ORDER BY id", (f"3dcodebench/{a.subset}", shard))]
        todo = [s for s in ids if s not in done_set(log)]
        print(f"[{time.strftime('%H:%M:%S')}] shard {k}: {len(ids)} samples, {len(todo)} to do", flush=True)
        with ThreadPoolExecutor(a.workers) as ex:
            for i, rec in enumerate(ex.map(lambda s: one(s, a.model, a.skill, log), todo)):
                if (i + 1) % 25 == 0:
                    print(f"[{time.strftime('%H:%M:%S')}] shard {k}: {i + 1}/{len(todo)}", flush=True)
        # one shard at a time on disk: delete extracted data and this shard's sealed GT renders
        keep = {l.strip() for l in open(ROOT / "evals" / "baseline_list.txt") if l.strip()}
        for sid in ids:
            if sid in keep:          # the fixed benchmark samples keep their sealed GT for later comparisons
                continue
            shutil.rmtree(ROOT / "runs" / "sealed" / sid.rsplit("/", 1)[1], ignore_errors=True)
        subprocess.run([PY, str(HERE / "shard_manager.py"), "delete", "--subset", f"3dcodebench/{a.subset}"], capture_output=True)
        print(f"[{time.strftime('%H:%M:%S')}] shard {k} done in {(time.time() - t0) / 60:.1f} min", flush=True)
    print("ALL DONE", flush=True)


if __name__ == "__main__":
    main()
