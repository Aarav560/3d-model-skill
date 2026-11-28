"""Download one dataset shard at a time, turn its Blender programs into sealed samples,
and delete the shard when its samples are finished.

    python shard_manager.py list    [--subset 3dcodebench/factories_geo]
    python shard_manager.py inspect --shard 3dcodebench/factories_geo/samples-000.tar
    python shard_manager.py next    [--subset ...] [--limit 200]   # fetch + prepare the next shard
    python shard_manager.py finish  --shard ...                    # prune + delete when all samples are done
    python shard_manager.py progress                               # which shards are done

Needs HF_TOKEN in the environment (never printed or stored) and, for gated datasets,
an accepted access request on the dataset page made by the token's owner.

NOT YET RUN AGAINST THE REAL DATASET: Hugging Face was unreachable from the machine
this was written on. Run `inspect` on the first shard before `next`, and check that the
grouping (one sample = files sharing a key) and the code-file detection match what the
tar really holds. Adjust --code-ext / --key-mode if they do not.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tarfile
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import DATA, PY, RUNS, SCRIPTS, db, sample_dirs  # noqa: E402

DEFAULT_REPO = "3dcodeverse/3dcodeverse-2m"
DEFAULT_SUBSETS = ["3dcodebench/factories_geo", "3dcodebench/factories_tex", "3dcodebench/instances_geo",
                   "thingiverse/blender_5_0", "thingiverse/blender_5_1_2_parametric"]


def token():
    t = os.environ.get("HF_TOKEN")
    if not t:
        sys.exit("HF_TOKEN is not set (export it in your shell; never commit it)")
    return t


def list_shards(repo, subset=None):
    from huggingface_hub import list_repo_files

    files = list_repo_files(repo, repo_type="dataset", token=token())
    shards = sorted(f for f in files if f.endswith(".tar"))
    if subset:
        shards = [f for f in shards if f.startswith(subset.rstrip("/") + "/")]
    return shards


def download(repo, path):
    from huggingface_hub import hf_hub_download

    os.makedirs(DATA, exist_ok=True)
    return hf_hub_download(repo, path, repo_type="dataset", token=token(), local_dir=DATA)


def metadata_for(repo, shard):
    """The subset's metadata.parquet as a dict key -> row (best effort)."""
    subset = os.path.dirname(shard)
    try:
        import pyarrow.parquet as pq

        p = download(repo, f"{subset}/metadata.parquet")
        t = pq.read_table(p).to_pylist()
    except Exception as e:  # noqa: BLE001
        print(f"[meta] no metadata for {subset}: {type(e).__name__}")
        return {}, []
    cols = list(t[0].keys()) if t else []
    key_col = next((c for c in ("__key__", "key", "id", "sample_id", "uid", "name") if c in cols), None)
    if not key_col:
        return {}, cols
    return {str(r[key_col]): r for r in t}, cols


def sample_key(member_name, mode):
    base = os.path.basename(member_name)
    if mode == "dir":
        return os.path.dirname(member_name) or base.split(".")[0]
    return os.path.join(os.path.dirname(member_name), base.split(".")[0])


def cmd_list(a):
    for s in list_shards(a.repo, a.subset):
        print(s)


def cmd_inspect(a):
    p = download(a.repo, a.shard)
    with tarfile.open(p) as tf:
        names = tf.getnames()
    print(f"{a.shard}: {len(names)} members, {os.path.getsize(p) / 1e6:.1f} MB")
    for n in names[:30]:
        print("  ", n)
    exts = {}
    for n in names:
        e = os.path.splitext(n)[1]
        exts[e] = exts.get(e, 0) + 1
    print("extensions:", exts)
    meta, cols = metadata_for(a.repo, a.shard)
    print("metadata columns:", cols, "rows:", len(meta))


def is_blender_program(path):
    try:
        head = open(path, encoding="utf-8", errors="ignore").read(20000)
    except OSError:
        return False
    return "import bpy" in head or "from bpy" in head


def cmd_next(a):
    con = db()
    done = {r["shard"] for r in con.execute("SELECT shard FROM shards WHERE status IN ('prepared','finished')")}
    subsets = [a.subset] if a.subset else DEFAULT_SUBSETS
    shard = None
    if a.local_tar:  # a shard you downloaded yourself (browser, other machine)
        shard = f"local/{os.path.basename(a.local_tar)}"
        subsets = []
    for sub in subsets:
        for s in list_shards(a.repo, sub):
            if s not in done:
                shard = s
                break
        if shard:
            break
    if not shard:
        print(json.dumps({"shard": None, "note": "every listed shard is prepared or finished"}))
        return
    t0 = time.time()
    con.execute("INSERT OR REPLACE INTO shards VALUES(?,?,?,?,?,?)", (shard, os.path.dirname(shard), "downloading",
                                                                    0, t0, None))
    con.commit()
    p = a.local_tar if a.local_tar else download(a.repo, shard)
    out = os.path.join(DATA, "extracted", shard.replace("/", "__"))
    os.makedirs(out, exist_ok=True)
    with tarfile.open(p) as tf:
        tf.extractall(out, filter="data")
    meta = {}
    if not a.local_tar:
        meta, _ = metadata_for(a.repo, shard)
    groups = {}
    for root, _dirs, files in os.walk(out):
        for f in files:
            full = os.path.join(root, f)
            rel = os.path.relpath(full, out)
            groups.setdefault(sample_key(rel, a.key_mode), []).append(full)
    n = 0
    prepared = 0
    for key, files in sorted(groups.items()):
        code = [f for f in files if f.endswith(a.code_ext) and is_blender_program(f)]
        if not code:
            continue
        n += 1
        if a.limit and prepared >= a.limit:
            continue
        sid = f"{os.path.dirname(shard).replace('/', '_')}__{key.replace('/', '_')}"
        row = meta.get(os.path.basename(key)) or meta.get(key) or {}
        cat = next((str(row[c]) for c in ("category", "class", "label", "factory", "object_type") if c in row), None)
        import subprocess

        subprocess.run([PY, os.path.join(SCRIPTS, "run_sample.py"), "prepare", "--id", sid, "--gt", code[0],
                        "--shard", shard, "--subset", os.path.dirname(shard)] + (["--category", cat] if cat else []),
                       timeout=900)
        prepared += 1
    con.execute("UPDATE shards SET status='prepared', n_samples=? WHERE shard=?", (n, shard))
    con.commit()
    if not a.local_tar:
        os.remove(p)  # the tar itself is no longer needed once extracted
    print(json.dumps({"shard": shard, "blender_samples": n, "prepared": prepared,
                      "minutes": round((time.time() - t0) / 60, 1)}))


def prune_sample(sid):
    """Keep scores, attempt code and small images; drop heavy capture files and sealed geometry."""
    d = sample_dirs(sid)
    for root, _dirs, files in os.walk(d["base"]):
        for f in files:
            if f in ("geometry.npz", "occupancy.npz", "views.npz"):
                os.remove(os.path.join(root, f))


def cmd_finish(a):
    con = db()
    open_ = con.execute("SELECT COUNT(*) FROM samples WHERE shard=? AND status IN ('prepared','attempting')",
                        (a.shard,)).fetchone()[0]
    if open_ and not a.force:
        sys.exit(f"{open_} samples of {a.shard} are not finished (use --force to drop them as skipped)")
    if open_:
        con.execute("UPDATE samples SET status='skipped' WHERE shard=? AND status IN ('prepared','attempting')",
                    (a.shard,))
    for (sid,) in con.execute("SELECT id FROM samples WHERE shard=?", (a.shard,)).fetchall():
        prune_sample(sid)
    shutil.rmtree(os.path.join(DATA, "extracted", a.shard.replace("/", "__")), ignore_errors=True)
    tar = os.path.join(DATA, a.shard)
    if os.path.exists(tar):
        os.remove(tar)
    con.execute("UPDATE shards SET status='finished', finished=? WHERE shard=?", (time.time(), a.shard))
    con.commit()
    print(json.dumps({"finished": a.shard}))


def cmd_progress(a):
    con = db()
    for r in con.execute("SELECT shard, status, n_samples, started, finished FROM shards ORDER BY started"):
        print(dict(r))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=DEFAULT_REPO)
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("list"); p.add_argument("--subset")
    p = sp.add_parser("inspect"); p.add_argument("--shard", required=True)
    p = sp.add_parser("next"); p.add_argument("--subset"); p.add_argument("--limit", type=int, default=200)
    p.add_argument("--code-ext", default=".py"); p.add_argument("--local-tar"); p.add_argument("--key-mode", choices=["stem", "dir"], default="stem")
    p = sp.add_parser("finish"); p.add_argument("--shard", required=True); p.add_argument("--force", action="store_true")
    sp.add_parser("progress")
    a = ap.parse_args()
    globals()[f"cmd_{a.cmd}"](a)


if __name__ == "__main__":
    main()
