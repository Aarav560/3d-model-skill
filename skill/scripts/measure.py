"""Read exact sizes off silhouettes instead of eyeballing pixels.

    python measure.py --id ID --view front [--rows 12] [--cols 0] [--attempt N]
    python measure.py --masks PATH/masks.npz --frame PATH/frame.json --view top

For the chosen view it prints, in world units:
  * the silhouette's extent along the view's screen axes (which world axes they are);
  * a row profile: at evenly spaced heights, every filled interval (start..end, width).
    Gaps between intervals are gaps in the object (between legs, inside a ring...);
  * optionally a column profile.
With --attempt N it measures that attempt's capture instead, so you can compare the
same numbers side by side.

Row/column lines are listed in world coordinates of the screen axes:
  front: right=+X up=+Z     right: right=+Y up=+Z     top: right=+X up=+Y
  iso  : screen axes are oblique; use it for shape, not sizes.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import sample_dirs  # noqa: E402

AXES = {"front": ("X", "Z", 0, 2), "right": ("Y", "Z", 1, 2), "top": ("X", "Y", 0, 1), "iso": ("u", "v", None, None)}


def intervals(line):
    idx = np.flatnonzero(line)
    if idx.size == 0:
        return []
    breaks = np.flatnonzero(np.diff(idx) > 1)
    starts = np.r_[idx[0], idx[breaks + 1]]
    ends = np.r_[idx[breaks], idx[-1]]
    return list(zip(starts, ends))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--id")
    ap.add_argument("--attempt", type=int)
    ap.add_argument("--masks")
    ap.add_argument("--frame")
    ap.add_argument("--view", default="front", choices=list(AXES))
    ap.add_argument("--rows", type=int, default=12)
    ap.add_argument("--cols", type=int, default=0)
    a = ap.parse_args()
    if a.id:
        d = sample_dirs(a.id)
        frame = json.load(open(os.path.join(d["ref"], "frame.json")))
        if a.attempt:
            v = np.load(os.path.join(d["attempts"], f"{a.attempt:02d}", "capture", "views.npz"))
        else:
            v = np.load(os.path.join(d["ref"], "masks.npz"))
    else:
        frame = json.load(open(a.frame))
        v = np.load(a.masks)
    m = v[f"{a.view}_mask"]
    res = m.shape[0]
    px = frame["view_width"] / res
    hname, vname, hi, vi = AXES[a.view]
    c = frame["center"]
    ch = c[hi] if hi is not None else 0.0
    cv = c[vi] if vi is not None else 0.0

    def u(col):
        return ch + (col + 0.5 - res / 2) * px

    def w(row):
        return cv + (res / 2 - (row + 0.5)) * px

    if not m.any():
        print("empty silhouette")
        return
    rows = np.flatnonzero(m.any(1))
    cols = np.flatnonzero(m.any(0))
    print(f"view={a.view}  screen right={hname}  up={vname}  pixel={px:.6g} world units "
          f"(+-{px / 2:.3g})")
    print(f"extent {hname}: {u(cols[0]) - px / 2:.5g} .. {u(cols[-1]) + px / 2:.5g}  "
          f"(width {(cols[-1] - cols[0] + 1) * px:.5g})")
    print(f"extent {vname}: {w(rows[-1]) - px / 2:.5g} .. {w(rows[0]) + px / 2:.5g}  "
          f"(height {(rows[-1] - rows[0] + 1) * px:.5g})")
    print(f"area {m.sum() * px * px:.5g} (filled share of bbox {m.sum() / ((rows[-1] - rows[0] + 1) * (cols[-1] - cols[0] + 1)):.3f})")
    if a.rows:
        print(f"\nrow profile ({vname} = ..., filled {hname} intervals):")
        for r in np.linspace(rows[0], rows[-1], a.rows).round().astype(int):
            iv = intervals(m[r])
            txt = "  ".join(f"[{u(s) - px / 2:.4g}..{u(e) + px / 2:.4g} w={(e - s + 1) * px:.4g}]" for s, e in iv)
            print(f"  {vname}={w(r):.5g}: {txt}")
    if a.cols:
        print(f"\ncolumn profile ({hname} = ..., filled {vname} intervals):")
        for col in np.linspace(cols[0], cols[-1], a.cols).round().astype(int):
            iv = intervals(m[:, col][::-1])  # bottom to top
            txt = "  ".join(f"[{w(res - 1 - s) - px / 2:.4g}..{w(res - 1 - e) + px / 2:.4g}]" for s, e in iv)
            print(f"  {hname}={u(col):.5g}: {txt}")


if __name__ == "__main__":
    main()
