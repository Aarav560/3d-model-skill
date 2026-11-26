"""Fit the dataset's reference-render camera model on TRAIN samples (GT mesh known).

Camera model (one shared set of numbers for the whole subset, if the renderer is fixed):
  view i azimuth = AZ0 + 90*i, elevation EL, perspective lens LENS (36 mm sensor),
  distance = DIST * bbox_diag from the bbox centre, aimed at the bbox centre + (0, 0, DZ * diag).
Objective: mean silhouette IoU between GT-mesh renders and the reference alpha masks (4 views).

  blender -b --factory-startup --python skill/scripts/calibrate_cams.py -- OUT.json gt1.npz refdir1 [gt2.npz refdir2 ...]
"""
import json
import math
import sys

import bpy
import numpy as np
from mathutils import Vector

import os
RES = int(os.environ.get("CALIB_RES", "192"))
INIT = os.environ.get("CALIB_INIT")   # "az0,el,lens,dist,dz" -> skip the coarse grid


def load_ref_masks(d):
    out = []
    for i in range(4):
        img = bpy.data.images.load(f"{d}/view_{i:02d}.png")
        w, h = img.size
        a = np.array(img.pixels[:], dtype=np.float32).reshape(h, w, 4)[::-1, :, 3]
        bpy.data.images.remove(img)
        k = w // RES
        out.append(a[: k * RES, : k * RES].reshape(RES, k, RES, k).mean((1, 3)) > 0.5)
    return out


def setup():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_WORKBENCH"
    sc.render.film_transparent = True
    sc.render.resolution_x = sc.render.resolution_y = RES
    sc.render.image_settings.color_mode = "RGBA"
    sc.display.shading.light = "FLAT"
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
    sc.collection.objects.link(cam)
    sc.camera = cam
    return cam


def load_mesh(npz, name):
    d = np.load(npz)
    me = bpy.data.meshes.new(name)
    me.from_pydata(d["verts"].tolist(), [], d["faces"].tolist())
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    v = d["verts"]
    return ob, (v.min(0) + v.max(0)) / 2, float(np.linalg.norm(np.ptp(v, 0)))


def place(cam, params, i, c, diag):
    az0, el, lens, dist, dz = params
    cam.data.lens = lens
    a, e = math.radians(az0 + 90 * i), math.radians(el)
    tgt = Vector((c[0], c[1], c[2] + dz * diag))
    dv = Vector((math.cos(e) * math.cos(a), math.cos(e) * math.sin(a), math.sin(e)))
    cam.location = tgt + dv * dist * diag
    cam.rotation_euler = (-dv).to_track_quat("-Z", "Y").to_euler()


def render_mask(path):
    bpy.context.scene.render.filepath = path
    bpy.ops.render.render(write_still=True)
    img = bpy.data.images.load(path)
    a = np.array(img.pixels[:], dtype=np.float32).reshape(RES, RES, 4)[::-1, :, 3] > 0.5
    bpy.data.images.remove(img)
    return a


def objective(params, cam, items, tmp):
    ious = []
    for ob, c, diag, refs in items:
        for o in bpy.context.scene.objects:
            if o.type == "MESH":
                o.hide_render = o is not ob
        for i in range(4):
            place(cam, params, i, c, diag)
            m = render_mask(tmp)
            r = refs[i]
            ious.append((m & r).sum() / max((m | r).sum(), 1))
    return float(np.mean(ious))


def main():
    args = sys.argv[sys.argv.index("--") + 1:]
    out, pairs = args[0], list(zip(args[1::2], args[2::2]))
    cam = setup()
    items = []
    for j, (npz, refdir) in enumerate(pairs):
        ob, c, diag = load_mesh(npz, f"m{j}")
        items.append((ob, c, diag, load_ref_masks(refdir)))
    tmp = out + ".tmp.png"
    # coarse grid over azimuth offset / elevation, then Nelder-Mead on all 5 params
    best = (-1, None)
    grid = [] if INIT else [(a, e) for a in range(0, 360, 30) for e in (15, 25, 35)]
    if INIT:
        best = (0.0, tuple(float(x) for x in INIT.split(",")))
    for az0, el in grid:
        p = (az0, el, 50.0, 2.0, 0.0)
        s = objective(p, cam, items, tmp)
        if s > best[0]:
            best = (s, p)
    from scipy.optimize import minimize
    res = minimize(lambda p: -objective(p, cam, items, tmp), np.array(best[1], float), method="Nelder-Mead",
                   options={"maxfev": int(os.environ.get("CALIB_FEV", "160")), "xatol": 0.2, "fatol": 1e-4,
                            "initial_simplex": [np.array(best[1]) + d for d in
                                                ([0, 0, 0, 0, 0], [6, 0, 0, 0, 0], [0, 4, 0, 0, 0], [0, 0, 10, 0, 0],
                                                 [0, 0, 0, 0.3, 0], [0, 0, 0, 0, 0.05])]})
    p = [round(float(x), 4) for x in res.x]
    result = {"params": dict(zip(["az0", "el", "lens", "dist", "dz"], p)), "mean_iou": round(-float(res.fun), 4),
              "grid_best": best, "samples": [q[1] for q in pairs]}
    open(out, "w").write(json.dumps(result, indent=1))
    print("CALIB " + json.dumps(result))


main()
