"""Shared paths, manifest access and capture helpers for the 3D skill scripts."""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import subprocess
import sys
import time

SCRIPTS = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(SCRIPTS)
SKILL_VERSION = open(os.path.join(SKILL_DIR, "VERSION")).read().strip() if os.path.exists(
    os.path.join(SKILL_DIR, "VERSION")) else "dev"

# Workspace: where data/, runs/ and evals/ live. Defaults to the repo root.
HOME = os.environ.get("SKILL3D_HOME", os.path.dirname(SKILL_DIR))
DATA = os.path.join(HOME, "data")
RUNS = os.path.join(HOME, "runs")
EVALS = os.path.join(HOME, "evals")
MANIFEST = os.path.join(EVALS, "manifest.sqlite")
PY = sys.executable

MAX_ROUNDS = 8
MIN_GAIN = 0.005  # stop after two consecutive rounds improving less than this

FAILURE_TAGS = ("proportion", "missing_part", "extra_part", "boolean", "orientation", "position",
                "curvature", "thin_feature", "hidden_geometry", "code_error", "material", "camera", "other")

SCHEMA = """
CREATE TABLE IF NOT EXISTS shards(
  shard TEXT PRIMARY KEY, subset TEXT, status TEXT, n_samples INTEGER,
  started REAL, finished REAL);
CREATE TABLE IF NOT EXISTS samples(
  id TEXT PRIMARY KEY, shard TEXT, subset TEXT, category TEXT, split TEXT,
  status TEXT,            -- pending | prepared | attempting | passed | failed | ref_error | skipped
  gt_path TEXT,           -- sealed ground-truth program (never read before reveal)
  attempts INTEGER DEFAULT 0, best_score REAL, best_attempt INTEGER, passed INTEGER DEFAULT 0,
  revealed INTEGER DEFAULT 0, failure_tags TEXT, note TEXT,
  skill_version TEXT, blender_version TEXT, updated REAL);
CREATE TABLE IF NOT EXISTS attempts(
  sample TEXT, round INTEGER, t REAL, ok INTEGER, pass INTEGER, sil_iou_min REAL,
  depth_agree_min REAL, far_error_max REAL, chamfer REAL, fscore REAL, vol_iou REAL,
  combined REAL, skill_version TEXT, blender_version TEXT, PRIMARY KEY(sample, round));
"""


def db():
    os.makedirs(EVALS, exist_ok=True)
    con = sqlite3.connect(MANIFEST, timeout=30)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    return con


def split_for(sample_id: str) -> str:
    """Deterministic 10% held-out split from the sample id."""
    h = int(hashlib.sha1(sample_id.encode()).hexdigest()[:8], 16)
    return "heldout" if h % 10 == 0 else "train"


def capture(code: str, out: str, frame: str | None = None, res: int = 256, occupancy: bool = True,
            timeout: int = 600) -> dict:
    """Run a program through the fixed rig in a separate process (programs are untrusted)."""
    cmd = [PY, os.path.join(SCRIPTS, "render_rig.py"), "--code", os.path.abspath(code), "--out",
           os.path.abspath(out), "--res", str(res)]
    if frame:
        cmd += ["--frame", os.path.abspath(frame)]
    if not occupancy:
        cmd.append("--no-occupancy")
    os.makedirs(out, exist_ok=True)
    t0 = time.time()
    try:
        subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=out)
    except subprocess.TimeoutExpired:
        json.dump({"ok": False, "error": f"timeout after {timeout}s"}, open(os.path.join(out, "status.json"), "w"))
    st_path = os.path.join(out, "status.json")
    if not os.path.exists(st_path):
        json.dump({"ok": False, "error": "rig crashed before writing status"}, open(st_path, "w"))
    st = json.load(open(st_path))
    st["wall"] = round(time.time() - t0, 2)
    return st


def combined(r: dict) -> float:
    """One number for 'how close' (1.0 = perfect), used for stop rules and best-of."""
    if not r.get("ok"):
        return 0.0
    ch = min(1.0, r["chamfer"] / 0.01)  # 0 at perfect, 1 at the pass bar or worse
    far = min(1.0, r["far_error_max"] / 0.005)
    return round(0.4 * r["sil_iou_min"] + 0.3 * r["depth_agree_min"] + 0.15 * (1 - ch) + 0.15 * (1 - far), 5)


def sample_dirs(sample_id: str) -> dict:
    base = os.path.join(RUNS, sample_id)
    return {"base": base, "ref": os.path.join(base, "ref"), "sealed": os.path.join(base, ".sealed"),
            "attempts": os.path.join(base, "attempts")}
