"""Attempter-side preview: render the attempt mesh from the (inferred) reference cameras and
place it next to the reference images. Uses only inputs + the attempt itself (no GT).

  python skill/scripts/preview.py <attempt_dir> <round_dir> <subset>
writes <round_dir>/preview.jpg (rows = views, left = reference, right = attempt).
"""
from __future__ import annotations

import json
import math
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
# reference camera azimuth per view index (see skill/references/frame_convention.md)
REF_AZ = {"factories_geo": (45, 135, 225, 315), "instances_geo": (200, 290, 20, 110)}
REF_EL = {"factories_geo": 22, "instances_geo": 25}
SIZE = 320


def _blender_render(mesh: str, out_dir: str, azs, el) -> None:
    import bpy
    import numpy as np
    from mathutils import Vector
    bpy.ops.wm.read_factory_settings(use_empty=True)
    d = np.load(mesh)
    me = bpy.data.meshes.new("m")
    me.from_pydata(d["verts"].tolist(), [], d["faces"].tolist())
    sc = bpy.context.scene
    sc.collection.objects.link(bpy.data.objects.new("m", me))
    sc.render.engine = "BLENDER_WORKBENCH"
    sc.render.resolution_x = sc.render.resolution_y = SIZE
    sc.display.shading.light = "STUDIO"
    cam = bpy.data.objects.new("c", bpy.data.cameras.new("c"))
    cam.data.lens = 50
    sc.collection.objects.link(cam)
    sc.camera = cam
    v = d["verts"]
    c, diag = (v.min(0) + v.max(0)) / 2, float(np.linalg.norm(np.ptp(v, 0)))
    for i, az in enumerate(azs):
        e, a = math.radians(el), math.radians(az)
        dv = np.array([math.cos(e) * math.cos(a), math.cos(e) * math.sin(a), math.sin(e)])
        cam.location = (c + dv * diag * 1.9).tolist()
        cam.rotation_euler = Vector((-dv).tolist()).to_track_quat("-Z", "Y").to_euler()
        sc.render.filepath = f"{out_dir}/pv_{i}.png"
        bpy.ops.render.render(write_still=True)


def make(attempt_dir: str, round_dir: str, subset: str) -> str:
    sys.path.insert(0, str(HERE))
    import run_sample
    import cv2
    import numpy as np
    rd = Path(round_dir)
    subprocess.run(run_sample.blender_cmd(Path(__file__).resolve(),
                                          ["--blender", str(rd / "pred.npz"), str(rd), subset]),
                   capture_output=True, text=True, timeout=600)
    rows = []
    for i in range(4):
        ref = cv2.resize(cv2.imread(str(Path(attempt_dir) / "input" / f"view_{i:02d}.png")), (SIZE, SIZE))
        mine = cv2.imread(str(rd / f"pv_{i}.png"))
        mine = cv2.resize(mine, (SIZE, SIZE)) if mine is not None else np.zeros_like(ref)
        rows.append(np.hstack([ref, mine]))
    out = rd / "preview.jpg"
    cv2.imwrite(str(out), np.vstack([np.hstack(rows[:2]), np.hstack(rows[2:])]), [cv2.IMWRITE_JPEG_QUALITY, 80])
    for i in range(4):
        (rd / f"pv_{i}.png").unlink(missing_ok=True)
    return str(out)


if __name__ == "__main__":
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    if args[0] == "--blender":
        mesh, out_dir, subset = args[1:4]
        _blender_render(mesh, out_dir, REF_AZ[subset], REF_EL[subset])
    else:
        print(make(*args[:3]))
