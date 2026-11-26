"""Diagnostic (TRAIN samples only, after reveal): score an attempt rotated by 0/90/180/270 deg about Z
against GT to measure a systematic orientation offset in how reference images are read.

  python skill/scripts/yaw_probe.py <sample_id> [<sample_id> ...]
"""
import json
import math
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
import attempt  # noqa: E402
import score as scorer  # noqa: E402
import train  # noqa: E402


def probe(sid):
    train.check_train(sid)
    k = sid.rsplit("/", 1)[1]
    sealed = ROOT / "runs" / "sealed" / k
    rounds = sorted((ROOT / "runs" / "attempts" / k).glob("round_*"))
    r1 = rounds[0]
    out = {}
    for deg in (0, 90, 180, 270):
        d = ROOT / "runs" / "yaw_probe" / k / f"yaw{deg}"
        d.mkdir(parents=True, exist_ok=True)
        p = np.load(r1 / "pred.npz")
        v = p["verts"].astype(np.float64)
        c = (v.min(0) + v.max(0)) / 2
        a = math.radians(deg)
        R = np.array([[math.cos(a), -math.sin(a), 0], [math.sin(a), math.cos(a), 0], [0, 0, 1]])
        np.savez_compressed(d / "pred.npz", verts=((v - c) @ R.T + c).astype(np.float32), faces=p["faces"])
        attempt._align(d / "pred.npz", sealed / "gt.npz", d / "al.npz")
        attempt._render(d / "al.npz", sealed / "gt.npz", d / "r")
        out[deg] = scorer.image_metrics(str(sealed / "gt_r"), str(d / "r"))["iou_min"]
    print(json.dumps({"sample": k, "iou_by_yaw": out}))
    return out


if __name__ == "__main__":
    for s in sys.argv[1:]:
        probe(s)
