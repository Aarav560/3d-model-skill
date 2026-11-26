"""Milestone 4 practice driver (TRAIN samples only; held-out samples are refused).

  prepare <sample_id>                 sealed inputs + GT preprocessing (same as attempt.py)
  round   <sample_id> <code.py>       score a practice round (+ preview)
  reveal  <sample_id>                 AFTER the final round: GT rig views vs best attempt + overlap diff -> reveal.jpg
  lesson  <sample_id> <tag> <text>    log what differed / the lesson (tags: proportion, missing_part, boolean,
                                      orientation, thin_structure, code_error, camera, material)
Everything is appended to runs/training_log.jsonl (local; derived from CC BY-NC-SA data, never committed).
"""
from __future__ import annotations

import json
import sqlite3
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
import attempt  # noqa: E402
import preview  # noqa: E402

SKILL = "train-practice"
LOG = ROOT / "runs" / "training_log.jsonl"


def key(sid):
    return sid.rsplit("/", 1)[1]


def log(rec):
    rec["t"] = time.time()
    with open(LOG, "a") as f:
        f.write(json.dumps(rec) + "\n")


def check_train(sid):
    split = sqlite3.connect(ROOT / "evals" / "manifest.sqlite").execute(
        "SELECT split FROM samples WHERE id=?", (sid,)).fetchone()
    if not split or split[0] != "train":
        sys.exit(f"refused: {sid} is not a train sample")


def rounds(k):
    return sorted((ROOT / "runs" / "attempts" / k).glob("round_*"))


def do_round(sid, code):
    check_train(sid)
    rnd = len(rounds(key(sid))) + 1
    res = attempt.score_attempt(sid, code, rnd, SKILL)
    al = res["aligned"]
    if al.get("runs_clean"):
        preview.make(str(ROOT / "runs" / "attempts" / key(sid)), str(ROOT / "runs" / "attempts" / key(sid) / f"round_{rnd:02d}"),
                     sid.split("/")[1])
    out = {"event": "round", "sample": sid, "round": rnd, "iou_min": al.get("iou_min"),
           "views": [al.get(f"iou_v{i}") for i in range(4)], "chamfer_pct": al.get("chamfer_pct"), "error": res.get("error")}
    log(out)
    print(json.dumps(out))


def reveal(sid):
    import cv2
    import numpy as np
    check_train(sid)
    k = key(sid)
    best = max(rounds(k), key=lambda d: json.loads((d / "score.json").read_text())["aligned"].get("iou_min", 0))
    rows = []
    for i in range(4):
        g = cv2.imread(str(ROOT / "runs" / "sealed" / k / "gt_r" / f"view_{i:02d}.png"), cv2.IMREAD_UNCHANGED)
        a = cv2.imread(str(best / "aligned_r" / f"view_{i:02d}.png"), cv2.IMREAD_UNCHANGED)
        on_white = lambda im: (im[..., :3] * (im[..., 3:] / 255) + 255 * (1 - im[..., 3:] / 255)).astype(np.uint8)
        mg, ma = g[..., 3] > 127, a[..., 3] > 127
        ov = np.full((*mg.shape, 3), 255, np.uint8)
        ov[mg & ma] = (150, 150, 150)
        ov[mg & ~ma] = (0, 170, 0)      # GT only (missing in attempt)
        ov[ma & ~mg] = (0, 0, 220)      # attempt only (extra)
        rows.append(np.hstack([on_white(g), on_white(a), ov]))
    sheet = cv2.resize(np.vstack(rows), None, fx=0.5, fy=0.5)
    cv2.imwrite(str(ROOT / "runs" / "attempts" / k / "reveal.jpg"), sheet, [cv2.IMWRITE_JPEG_QUALITY, 85])
    log({"event": "reveal", "sample": sid, "best_round": best.name,
         "iou_min": json.loads((best / "score.json").read_text())["aligned"]["iou_min"]})
    print(ROOT / "runs" / "attempts" / k / "reveal.jpg")


def lesson(sid, tag, text):
    log({"event": "lesson", "sample": sid, "tag": tag, "text": text})


if __name__ == "__main__":
    cmd, *a = sys.argv[1:]
    if cmd == "prepare":
        check_train(a[0]); attempt.prepare(a[0])
    elif cmd == "round":
        do_round(*a)
    elif cmd == "reveal":
        reveal(a[0])
    elif cmd == "lesson":
        lesson(a[0], a[1], " ".join(a[2:]))
