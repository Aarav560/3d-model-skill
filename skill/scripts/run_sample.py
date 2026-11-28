"""The per-sample practice loop: prepare a reference, score attempts, reveal, log failures.

    python run_sample.py prepare --id ID --gt PATH_TO_GROUND_TRUTH.py [--category C] [--shard S]
    python run_sample.py next [--split train|heldout]        # print the next sample to attempt
    python run_sample.py brief --id ID                       # what you may look at (no ground truth)
    python run_sample.py attempt --id ID --code attempt.py    # capture, score, diff; one round
    python run_sample.py reveal --id ID                      # only after the final attempt
    python run_sample.py fail --id ID --tags proportion,missing_part --note "..."
    python run_sample.py status                              # aggregate numbers and failure rate

Ground truth lives in runs/ID/.sealed/ and the gt_path in the manifest. Reading either
before `reveal` breaks hard rule 1 and invalidates the sample.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import (EVALS, FAILURE_TAGS, MAX_ROUNDS, MIN_GAIN, SKILL_VERSION, capture, combined,  # noqa: E402
                    db, sample_dirs, split_for)
from score import score  # noqa: E402

VISIBLE = [f"{k}_{v}.png" for k in ("view", "sil") for v in ("front", "right", "top", "iso")]


def cmd_prepare(a):
    d = sample_dirs(a.id)
    os.makedirs(d["sealed"], exist_ok=True)
    st = capture(a.gt, d["sealed"], res=a.res)
    con = db()
    split = a.split or split_for(a.id)
    if not st.get("ok"):
        con.execute("INSERT OR REPLACE INTO samples(id, shard, subset, category, split, status, gt_path, note, updated)"
                    " VALUES(?,?,?,?,?,?,?,?,?)", (a.id, a.shard, a.subset, a.category, split, "ref_error",
                                                   os.path.abspath(a.gt), (st.get("error") or "")[:500], time.time()))
        con.commit()
        print(json.dumps({"id": a.id, "status": "ref_error", "error": st.get("error")}))
        return 1
    os.makedirs(d["ref"], exist_ok=True)
    for f in VISIBLE:
        shutil.copy(os.path.join(d["sealed"], f), os.path.join(d["ref"], f))
    frame = json.load(open(os.path.join(d["sealed"], "frame.json")))
    shutil.copy(os.path.join(d["sealed"], "frame.json"), os.path.join(d["ref"], "frame.json"))
    # Only the silhouette masks are copied: they are what the images show, so measure.py can read
    # exact sizes. Depth and normals stay sealed, so practice matches the photo setting.
    import numpy as np

    v = np.load(os.path.join(d["sealed"], "views.npz"))
    np.savez_compressed(os.path.join(d["ref"], "masks.npz"), **{k: v[k] for k in v.files if k.endswith("_mask")})
    brief = {
        "id": a.id, "category": a.category, "split": split,
        "bbox_dims_xyz": [round(x, 6) for x in frame["dims"]],
        "bbox_min": [round(x, 6) for x in frame["bbox_min"]],
        "bbox_max": [round(x, 6) for x in frame["bbox_max"]],
        "view_width_world": round(frame["view_width"], 6), "res_px": a.res,
        "world_per_px": round(frame["view_width"] / a.res, 7),
        "views": {"front": "camera at -Y looking +Y: screen right=+X, up=+Z",
                  "right": "camera at +X looking -X: screen right=+Y, up=+Z",
                  "top": "camera at +Z looking down: screen right=+X, up=+Y",
                  "iso": "camera at (+X,-Y,+Z) looking at the centre (azimuth 45, elevation 35.3)"},
        "images": [os.path.join(d["ref"], f) for f in VISIBLE],
        "rules": "Ground truth is sealed. Do not open runs/ID/.sealed or the gt_path before `reveal`.",
    }
    json.dump(brief, open(os.path.join(d["base"], "brief.json"), "w"), indent=2)
    con.execute("INSERT OR REPLACE INTO samples(id, shard, subset, category, split, status, gt_path, attempts,"
                " blender_version, updated) VALUES(?,?,?,?,?,?,?,?,?,?)",
                (a.id, a.shard, a.subset, a.category, split, "prepared", os.path.abspath(a.gt), 0,
                 st.get("blender_version"), time.time()))
    con.commit()
    print(json.dumps({"id": a.id, "status": "prepared", "split": split, "t": st.get("wall")}))
    return 0


def cmd_next(a):
    con = db()
    q = "SELECT id, split, category, attempts FROM samples WHERE status IN ('prepared','attempting')"
    args = []
    if a.split:
        q += " AND split=?"
        args.append(a.split)
    q += " ORDER BY status DESC, updated LIMIT 1"
    row = con.execute(q, args).fetchone()
    print(json.dumps(dict(row) if row else {"id": None, "note": "nothing prepared; run shard_manager.py next"}))


def cmd_brief(a):
    print(open(os.path.join(sample_dirs(a.id)["base"], "brief.json")).read())


def _history(con, sid):
    return [dict(r) for r in con.execute("SELECT * FROM attempts WHERE sample=? ORDER BY round", (sid,))]


def cmd_attempt(a):
    con = db()
    s = con.execute("SELECT * FROM samples WHERE id=?", (a.id,)).fetchone()
    if s is None:
        sys.exit(f"unknown sample {a.id}")
    if s["revealed"]:
        sys.exit("ground truth already revealed: further attempts would not count")
    hist = _history(con, a.id)
    rnd = len(hist) + 1
    if rnd > MAX_ROUNDS and not a.force:
        sys.exit(f"round limit {MAX_ROUNDS} reached: reveal and log the failure")
    d = sample_dirs(a.id)
    adir = os.path.join(d["attempts"], f"{rnd:02d}")
    os.makedirs(adir, exist_ok=True)
    shutil.copy(a.code, os.path.join(adir, "code.py"))
    st = capture(os.path.join(adir, "code.py"), os.path.join(adir, "capture"),
                 frame=os.path.join(d["sealed"], "frame.json"), res=a.res)
    r = score(d["sealed"], os.path.join(adir, "capture"), os.path.join(adir, "diff"))
    r["combined"] = combined(r)
    r["round"] = rnd
    if not st.get("ok"):
        r["traceback_tail"] = (st.get("traceback") or "")[-1500:]
    json.dump(r, open(os.path.join(adir, "score.json"), "w"), indent=2)
    con.execute("INSERT OR REPLACE INTO attempts VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (a.id, rnd, time.time(), int(r["ok"]), int(r["pass"]), r["sil_iou_min"], r.get("depth_agree_min"),
                 r.get("far_error_max"), r["chamfer"], r.get("fscore"), r.get("vol_iou"), r["combined"],
                 SKILL_VERSION, st.get("blender_version")))
    best = max([h["combined"] for h in hist] + [r["combined"]])
    best_round = rnd if r["combined"] >= best else max(hist, key=lambda h: h["combined"])["round"]
    status = "passed" if r["pass"] or any(h["pass"] for h in hist) else "attempting"
    con.execute("UPDATE samples SET attempts=?, best_score=?, best_attempt=?, passed=?, status=?, skill_version=?,"
                " updated=? WHERE id=?", (rnd, best, best_round, int(status == "passed"), status, SKILL_VERSION,
                                         time.time(), a.id))
    con.commit()
    # stop-rule advice
    gains = [h["combined"] for h in hist] + [r["combined"]]
    stop = None
    if r["pass"]:
        stop = "PASS: stop, reveal, record the lesson"
    elif rnd >= MAX_ROUNDS:
        stop = "round limit reached: reveal, tag the failure with `fail`"
    elif len(gains) >= 3 and gains[-1] - gains[-2] < MIN_GAIN and gains[-2] - gains[-3] < MIN_GAIN:
        stop = "two rounds in a row gained < 0.5%: stop, reveal, tag the failure"
    out = {k: r.get(k) for k in ("round", "ok", "pass", "combined", "sil_iou", "depth_agree", "far_error",
                                  "chamfer", "fscore", "vol_iou", "dims_ratio", "worst_view", "worst_regions",
                                  "error", "traceback_tail")}
    out["best_combined"] = best
    if r["ok"]:
        out["compare_image"] = contact_sheet(d["ref"], os.path.join(adir, "capture"), os.path.join(adir, "diff"),
                                             os.path.join(adir, "compare.png"))
    out["stop"] = stop
    out["diff_image"] = os.path.join(adir, "diff", "diff_all.png")
    out["attempt_views"] = [os.path.join(adir, "capture", f"view_{v}.png") for v in ("front", "right", "top", "iso")]
    out["worst_regions"] = (out.get("worst_regions") or [])[:3]
    for reg in out["worst_regions"]:
        reg.pop("screen_axes", None)
    print(json.dumps({k: v for k, v in out.items() if v is not None}, indent=None))


def contact_sheet(ref_dir, cap_dir, diff_dir, path):
    """One image to look at: reference row, attempt row, difference row."""
    import cv2
    import numpy as np

    rows = []
    for folder, pat, label in ((ref_dir, "view_{}.png", "reference"), (cap_dir, "view_{}.png", "attempt"),
                               (diff_dir, "diff_{}.png", "diff: green=missing red=extra")):
        tiles = []
        for v in ("front", "right", "top", "iso"):
            im = cv2.imread(os.path.join(folder, pat.format(v)))
            cv2.putText(im, f"{label[:9]} {v}", (4, im.shape[0] - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (0, 0, 160), 1)
            tiles.append(im)
        rows.append(np.hstack(tiles))
    cv2.imwrite(path, np.vstack(rows))
    return path


def cmd_reveal(a):
    con = db()
    s = con.execute("SELECT * FROM samples WHERE id=?", (a.id,)).fetchone()
    con.execute("UPDATE samples SET revealed=1, updated=? WHERE id=?", (time.time(), a.id))
    if s["status"] == "attempting":
        con.execute("UPDATE samples SET status='failed' WHERE id=?", (a.id,))
    con.commit()
    print(json.dumps({"id": a.id, "gt_path": s["gt_path"], "best_round": s["best_attempt"],
                      "best_combined": s["best_score"], "passed": bool(s["passed"])}))


def cmd_fail(a):
    tags = [t.strip() for t in a.tags.split(",") if t.strip()]
    bad = [t for t in tags if t not in FAILURE_TAGS]
    if bad:
        sys.exit(f"unknown tags {bad}; use {FAILURE_TAGS}")
    con = db()
    con.execute("UPDATE samples SET failure_tags=?, note=?, status=CASE WHEN passed=1 THEN status ELSE 'failed' END,"
                " updated=? WHERE id=?", (",".join(tags), a.note, time.time(), a.id))
    con.commit()
    s = dict(con.execute("SELECT * FROM samples WHERE id=?", (a.id,)).fetchone())
    path = os.path.join(EVALS, "failures.csv")
    new = not os.path.exists(path)
    with open(path, "a", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["t", "id", "subset", "category", "split", "attempts", "best_combined", "tags", "note",
                        "skill_version"])
        w.writerow([time.strftime("%Y-%m-%d %H:%M"), s["id"], s["subset"], s["category"], s["split"],
                    s["attempts"], s["best_score"], s["failure_tags"], s["note"], s["skill_version"]])
    print(json.dumps({"logged": a.id, "tags": tags}))


def cmd_status(a):
    con = db()
    rows = [dict(r) for r in con.execute("SELECT * FROM samples")]
    done = [r for r in rows if r["status"] in ("passed", "failed")]
    out = {"samples": len(rows), "finished": len(done),
           "passed": sum(1 for r in done if r["passed"]),
           "failed": sum(1 for r in done if not r["passed"]),
           "ref_errors": sum(1 for r in rows if r["status"] == "ref_error"),
           "pending": sum(1 for r in rows if r["status"] in ("prepared", "attempting"))}
    out["failure_rate"] = round(out["failed"] / len(done), 4) if done else None
    for split in ("train", "heldout"):
        sd = [r for r in done if r["split"] == split]
        out[f"{split}_pass_rate"] = round(sum(r["passed"] for r in sd) / len(sd), 4) if sd else None
    tags = {}
    for r in done:
        for t in (r["failure_tags"] or "").split(","):
            if t:
                tags[t] = tags.get(t, 0) + 1
    out["failure_tags"] = dict(sorted(tags.items(), key=lambda kv: -kv[1]))
    out["shards"] = [dict(r) for r in con.execute("SELECT shard, status, n_samples FROM shards")]
    print(json.dumps(out, indent=1))


def main():
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("prepare"); p.add_argument("--id", required=True); p.add_argument("--gt", required=True)
    p.add_argument("--category"); p.add_argument("--shard"); p.add_argument("--subset"); p.add_argument("--split")
    p.add_argument("--res", type=int, default=256)
    p = sp.add_parser("next"); p.add_argument("--split")
    p = sp.add_parser("brief"); p.add_argument("--id", required=True)
    p = sp.add_parser("attempt"); p.add_argument("--id", required=True); p.add_argument("--code", required=True)
    p.add_argument("--res", type=int, default=256); p.add_argument("--force", action="store_true")
    p = sp.add_parser("reveal"); p.add_argument("--id", required=True)
    p = sp.add_parser("fail"); p.add_argument("--id", required=True); p.add_argument("--tags", required=True)
    p.add_argument("--note", default="")
    sp.add_parser("status")
    a = ap.parse_args()
    return globals()[f"cmd_{a.cmd}"](a) or 0


if __name__ == "__main__":
    sys.exit(main())
