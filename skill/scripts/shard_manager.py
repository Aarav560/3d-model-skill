"""Shard manager: download ONE dataset shard, extract it, register samples in the
SQLite manifest, assign a deterministic 10% held-out split, and delete the shard.

Usage:
  python skill/scripts/shard_manager.py fetch  --subset 3dcodebench/factories_geo --shard samples-000.tar
  python skill/scripts/shard_manager.py status
  python skill/scripts/shard_manager.py delete --subset 3dcodebench/factories_geo

Rules enforced here (see 3D-SKILL-BUILD.md section 3):
  * HF token is read only from the HF_TOKEN env var and never printed or stored.
  * One shard at a time: fetch refuses if another shard is still extracted.
  * Held-out split is assigned on first touch and never changed afterwards.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sqlite3
import sys
import tarfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
MANIFEST = ROOT / "evals" / "manifest.sqlite"
REPO_ID = "3dcodeverse/3dcodeverse-2m"
HELDOUT_FRACTION = 0.10
SPLIT_SALT = "3d-skill-split-v1"  # changing this would reshuffle the split: never do it

SCHEMA = """
CREATE TABLE IF NOT EXISTS shards (
  subset TEXT, shard TEXT, status TEXT, n_samples INTEGER,
  fetched_at REAL, deleted_at REAL, PRIMARY KEY (subset, shard));
CREATE TABLE IF NOT EXISTS samples (
  id TEXT PRIMARY KEY, subset TEXT, shard TEXT, name TEXT, category TEXT,
  environment TEXT, split TEXT, status TEXT DEFAULT 'new',
  attempts INTEGER DEFAULT 0, best_score REAL);
CREATE TABLE IF NOT EXISTS attempts (
  id INTEGER PRIMARY KEY AUTOINCREMENT, sample_id TEXT, kind TEXT, round INTEGER,
  skill_version TEXT, blender_version TEXT, score_json TEXT, created_at REAL);
"""


def db() -> sqlite3.Connection:
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(MANIFEST)
    con.executescript(SCHEMA)
    return con


def split_hash(sample_id: str) -> str:
    return hashlib.sha256(f"{SPLIT_SALT}:{sample_id}".encode()).hexdigest()


def assign_splits(sample_ids: list[str]) -> dict[str, str]:
    """Exactly ceil(10%) of a shard's samples go to held_out, chosen by a salted hash
    rank (deterministic, machine independent). Assigned once, on first touch."""
    import math
    ranked = sorted(sample_ids, key=split_hash)
    n_held = math.ceil(HELDOUT_FRACTION * len(ranked))
    return {sid: ("held_out" if i < n_held else "train") for i, sid in enumerate(ranked)}


def category_for(name: str) -> str:
    return name[:-len("Factory")] if name.endswith("Factory") else name


def extracted_dirs() -> list[Path]:
    root = DATA / "extracted"
    return [p for p in root.glob("*/*") if p.is_dir()] if root.exists() else []


def fetch(subset: str, shard: str) -> None:
    from huggingface_hub import hf_hub_download

    busy = [p for p in extracted_dirs() if p.name != subset.split("/")[-1]]
    if busy:
        sys.exit(f"Another shard is still extracted ({busy[0]}); delete it first.")
    token = os.environ.get("HF_TOKEN") or None  # dataset is public; token optional
    raw = DATA / "raw"
    t0 = time.time()
    meta_path = hf_hub_download(REPO_ID, f"{subset}/metadata.parquet", repo_type="dataset",
                                local_dir=raw, token=token)
    tar_path = hf_hub_download(REPO_ID, f"{subset}/{shard}", repo_type="dataset",
                               local_dir=raw, token=token)
    print(f"downloaded {shard} in {time.time() - t0:.0f}s")

    out = DATA / "extracted" / subset
    out.mkdir(parents=True, exist_ok=True)
    with tarfile.open(tar_path) as tf:
        tf.extractall(out, filter="data")  # 'data' filter blocks path traversal
    Path(tar_path).unlink()  # keep only the extracted copy on disk

    import pandas as pd
    meta = pd.read_parquet(meta_path, columns=["key", "name", "tar", "meta_json"])
    meta = meta[meta.tar == f"{subset}/{shard}"]
    con = db()
    n_new = 0
    splits = assign_splits([f"{subset}/{k}" for k in meta.key])
    for row in meta.itertuples():
        sid = f"{subset}/{row.key}"
        env = json.loads(row.meta_json).get("environment", "")
        cur = con.execute(
            "INSERT OR IGNORE INTO samples (id, subset, shard, name, category, environment, split)"
            " VALUES (?,?,?,?,?,?,?)",
            (sid, subset, shard, row.name, category_for(row.name), env, splits[sid]))
        n_new += cur.rowcount
    con.execute("INSERT OR REPLACE INTO shards VALUES (?,?,?,?,?,NULL)",
                (subset, shard, "extracted", len(meta), time.time()))
    con.commit()
    print(f"registered {len(meta)} samples ({n_new} new) -> {out}")
    status()


def delete(subset: str) -> None:
    shutil.rmtree(DATA / "extracted" / subset, ignore_errors=True)
    shutil.rmtree(DATA / "raw" / subset, ignore_errors=True)
    con = db()
    con.execute("UPDATE shards SET status='deleted', deleted_at=? WHERE subset=?",
                (time.time(), subset))
    con.commit()
    print(f"deleted local data for {subset}")


def status() -> None:
    con = db()
    for row in con.execute("SELECT subset, shard, status, n_samples FROM shards"):
        print("shard", *row)
    for row in con.execute("SELECT split, COUNT(*) FROM samples GROUP BY split"):
        print("split", *row)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["fetch", "delete", "status"])
    ap.add_argument("--subset", default="3dcodebench/factories_geo")
    ap.add_argument("--shard", default="samples-000.tar")
    a = ap.parse_args()
    {"fetch": lambda: fetch(a.subset, a.shard), "delete": lambda: delete(a.subset),
     "status": status}[a.cmd]()


if __name__ == "__main__":
    main()
