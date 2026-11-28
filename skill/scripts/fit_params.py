"""Fine-tune named dimensions of an attempt against the reference silhouettes.

    python fit_params.py --id ID --code attempt.py --params LEG_W,TOP_T,HEIGHT [--iters 60] [--out fitted.py]

Claude fixes topology and missing parts; this fixes millimetres. The attempt must declare
each parameter at the top level as `NAME = <number>` on its own line. The optimiser
(Powell, bounded to +-40% of the start value by default) rewrites those lines, captures
the program through the rig without occupancy, and maximises

    0.5 * min view IoU + 0.5 * mean view IoU   against the VISIBLE reference silhouettes

It only uses what an image shows (runs/ID/ref/masks.npz), never the sealed score, so
the same tool works for photos and cannot overfit the hidden metric. Score the fitted
program with `run_sample.py attempt` like any other round. Writes the best program to --out
(default: attempt name + _fitted.py) and prints the change in each parameter.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import capture, sample_dirs  # noqa: E402
from score import iou  # noqa: E402

VIEWS = ("front", "right", "top", "iso")


def read_params(src, names):
    vals = {}
    for n in names:
        m = re.search(rf"^{re.escape(n)}\s*=\s*([-+0-9.eE]+)\s*(#.*)?$", src, re.M)
        if not m:
            sys.exit(f"parameter {n} must be a top-level line `{n} = <number>`")
        vals[n] = float(m.group(1))
    return vals


def write_params(src, vals):
    for n, v in vals.items():
        src = re.sub(rf"^({re.escape(n)}\s*=\s*)([-+0-9.eE]+)", lambda m: f"{m.group(1)}{v:.6g}", src, count=1, flags=re.M)
    return src


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--id", required=True)
    ap.add_argument("--code", required=True)
    ap.add_argument("--params", required=True)
    ap.add_argument("--iters", type=int, default=60)
    ap.add_argument("--range", type=float, default=0.4, help="relative bound around each start value")
    ap.add_argument("--out")
    a = ap.parse_args()
    names = [n.strip() for n in a.params.split(",") if n.strip()]
    src = open(a.code).read()
    x0 = read_params(src, names)
    d = sample_dirs(a.id)
    frame = os.path.join(d["ref"], "frame.json")
    ref = np.load(os.path.join(d["ref"], "masks.npz"))
    work = tempfile.mkdtemp(prefix="fit_")
    cache = {}
    best = {"f": -1.0, "vals": dict(x0), "score": None}

    def evaluate(vec):
        vals = {n: float(x0[n] * (1 + v)) if x0[n] != 0 else float(v) for n, v in zip(names, vec)}
        key = tuple(round(v, 7) for v in vals.values())
        if key in cache:
            return cache[key]
        p = os.path.join(work, "prog.py")
        open(p, "w").write(write_params(src, vals))
        cap = os.path.join(work, "cap")
        st = capture(p, cap, frame=frame, occupancy=False)
        if not st.get("ok"):
            cache[key] = 1.0
            return 1.0
        av = np.load(os.path.join(cap, "views.npz"))
        ious = [iou(ref[f"{v}_mask"], av[f"{v}_mask"]) for v in VIEWS]
        f = 0.5 * min(ious) + 0.5 * float(np.mean(ious))
        if f > best["f"]:
            best.update(f=f, vals=vals, score={"view_iou": dict(zip(VIEWS, [round(x, 4) for x in ious]))})
        cache[key] = -f
        return -f

    from scipy.optimize import minimize

    bounds = [(-a.range, a.range)] * len(names)
    f0 = -evaluate(np.zeros(len(names)))
    minimize(evaluate, np.zeros(len(names)), method="Powell", bounds=bounds,
             options={"maxfev": a.iters, "xtol": 1e-4, "ftol": 1e-5})
    out = a.out or a.code.replace(".py", "_fitted.py")
    open(out, "w").write(write_params(src, best["vals"]))
    print(json.dumps({"start_fit": round(f0, 5), "best_fit": round(best["f"], 5), "view_iou": best["score"],
                      "evaluations": len(cache), "params": {n: [x0[n], round(best["vals"][n], 6)] for n in names},
                      "written": out, "next": "score it with run_sample.py attempt"}, indent=1))


if __name__ == "__main__":
    main()
