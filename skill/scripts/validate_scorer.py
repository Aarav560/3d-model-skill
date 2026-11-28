"""Milestone 1 exit test: prove the scorer reproduces ~1.0 for ground-truth code and
falls for real errors.

    python validate_scorer.py --objects DIR_OF_PROGRAMS --work WORKDIR [--limit N]

For every program it captures a reference, then scores:
  identical      the same code captured again (must score ~1.0 and PASS)
  reordered      same geometry built after a dummy object is added and removed (PASS)
  scale_0.5pct   uniform scale x1.005 about the centre (small, should usually PASS)
  scale_3pct     uniform scale x1.03 (should FAIL)
  shift_2pct     translated by 2% of the diagonal along X (should FAIL)
  squash_5pct    Z scaled by 0.95 (should FAIL)
  drop_part      smallest visible part removed (should FAIL when the part is visible)
Results go to WORKDIR/validation.csv and a summary is printed.
"""
import argparse
import csv
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable

POST = {
    "identical": "",
    "reordered": "bpy.ops.mesh.primitive_cube_add(location=(99,99,99)); bpy.data.objects.remove(bpy.context.object)\n",
    "scale_0.5pct": "_xf(1.005, 1.005, 1.005, 0)\n",
    "scale_3pct": "_xf(1.03, 1.03, 1.03, 0)\n",
    "shift_2pct": "_xf(1, 1, 1, 0.02)\n",
    "squash_5pct": "_xf(1, 1, 0.95, 0)\n",
    "drop_part": "_drop_smallest()\n",
}
EXPECT = {"identical": True, "reordered": True, "scale_0.5pct": None, "scale_3pct": False,
          "shift_2pct": False, "squash_5pct": False, "drop_part": None}

HELPERS = r'''
import bpy, mathutils
def _vis():
    bpy.context.view_layer.update()  # matrix_world is stale until the depsgraph updates
    return [o for o in bpy.context.scene.objects if o.type in {"MESH","CURVE","SURFACE","META","FONT"} and not o.hide_render and not o.hide_get()]
def _bbox(objs):
    import numpy as np
    pts = [o.matrix_world @ mathutils.Vector(c) for o in objs for c in o.bound_box]
    a = np.array([tuple(p) for p in pts]); return a.min(0), a.max(0)
def _xf(sx, sy, sz, shift):
    import numpy as np
    objs = _vis(); lo, hi = _bbox(objs); c = (lo + hi) / 2; diag = float(np.linalg.norm(hi - lo))
    S = mathutils.Matrix.Diagonal((sx, sy, sz, 1.0))
    T = mathutils.Matrix.Translation(mathutils.Vector(tuple(c)) + mathutils.Vector((shift * diag, 0, 0)))
    Ti = mathutils.Matrix.Translation(-mathutils.Vector(tuple(c)))
    M = T @ S @ Ti
    roots = [o for o in bpy.context.scene.objects if o.parent is None]
    for o in roots:
        o.matrix_world = M @ o.matrix_world
def _drop_smallest():
    objs = _vis()
    if len(objs) < 2:
        return
    import numpy as np
    def vol(o):
        lo, hi = _bbox([o]); return float(np.prod(np.maximum(hi - lo, 1e-9)))
    o = min(objs, key=vol); o.hide_render = True
'''


def run(code, out, frame=None):
    cmd = [PY, os.path.join(HERE, "render_rig.py"), "--code", code, "--out", out]
    if frame:
        cmd += ["--frame", frame]
    subprocess.run(cmd, capture_output=True, text=True, timeout=600)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--objects", required=True)
    ap.add_argument("--work", required=True)
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()
    sys.path.insert(0, HERE)
    from score import score

    progs = sorted(f for f in os.listdir(a.objects) if f.endswith(".py"))
    if a.limit:
        progs = progs[: a.limit]
    rows = []
    for p in progs:
        name = p[:-3]
        src = open(os.path.join(a.objects, p)).read()
        base = os.path.join(a.work, name)
        os.makedirs(base, exist_ok=True)
        ref = os.path.join(base, "ref")
        run(os.path.join(a.objects, p), ref)
        st = json.load(open(os.path.join(ref, "status.json")))
        if not st.get("ok"):
            print(name, "REFERENCE FAILED", st.get("error"))
            rows.append({"object": name, "variant": "reference", "ok": False})
            continue
        for var, post in POST.items():
            code = os.path.join(base, f"{var}.py")
            open(code, "w").write(src + "\n" + HELPERS + post)
            out = os.path.join(base, var)
            run(code, out, os.path.join(ref, "frame.json"))
            r = score(ref, out)
            exp = EXPECT[var]
            rows.append({"object": name, "variant": var, "ok": r["ok"], "pass": r["pass"],
                         "sil_iou_min": r["sil_iou_min"], "depth_agree_min": r["depth_agree_min"], "chamfer": r["chamfer"], "fscore": r.get("fscore"),
                         "vol_iou": r.get("vol_iou"), "expected_pass": exp,
                         "as_expected": "" if exp is None else (r["pass"] == exp)})
            print(f"{name:16s} {var:13s} pass={r['pass']!s:5s} iou_min={r['sil_iou_min']:.4f} depth_min={r['depth_agree_min']:.4f} chamfer={r['chamfer']:.5f} vol_iou={r.get('vol_iou')}")
    with open(os.path.join(a.work, "validation.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=sorted({k for r in rows for k in r}))
        w.writeheader(); w.writerows(rows)
    print("\nSUMMARY")
    for var in POST:
        rr = [r for r in rows if r.get("variant") == var]
        if not rr:
            continue
        n_pass = sum(1 for r in rr if r.get("pass"))
        mi = min(r["sil_iou_min"] for r in rr)
        mc = max(r["chamfer"] for r in rr)
        print(f"{var:13s} pass {n_pass}/{len(rr)}  worst iou_min {mi:.4f}  worst chamfer {mc:.5f}")


if __name__ == "__main__":
    main()
