"""Estimate the dataset's reference-render camera (azimuth/elevation per view) from
TRAIN samples only: render the GT mesh with a grid of perspective cameras and match
silhouettes against a background-difference mask of the reference PNG.

  python skill/scripts/calibrate_ref_camera.py mesh.npz ref_dir out.json
(runs inside Blender via run_sample.blender_cmd; scoring of masks is done here too)
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np

AZ = list(range(0, 360, 15))
EL = [10, 20, 30, 40, 50]
LENS_MM = 50.0


def ref_mask(png: str) -> np.ndarray:
    import bpy  # noqa: F401  (Blender image loader keeps this script dependency-free)
    img = bpy.data.images.load(png)
    w, h = img.size
    px = np.array(img.pixels[:], dtype=np.float32).reshape(h, w, 4)[::-1, :, :3] * 255
    border = np.concatenate([px[:8].reshape(-1, 3), px[-8:].reshape(-1, 3), px[:, :8].reshape(-1, 3), px[:, -8:].reshape(-1, 3)])
    bg = np.median(border, 0)
    diff = np.abs(px - bg).max(2)
    return diff > 18


def crop_norm(m: np.ndarray, n: int = 128) -> np.ndarray:
    ys, xs = np.nonzero(m)
    if len(ys) == 0:
        return np.zeros((n, n), bool)
    y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    c = m[y0:y1, x0:x1].astype(np.float32)
    s = max(c.shape)
    pad = np.zeros((s, s), np.float32)
    pad[(s - c.shape[0]) // 2:(s - c.shape[0]) // 2 + c.shape[0], (s - c.shape[1]) // 2:(s - c.shape[1]) // 2 + c.shape[1]] = c
    idx = (np.arange(n) * s / n).astype(int)
    return pad[np.ix_(idx, idx)] > 0.5


def main() -> None:
    import bpy
    from mathutils import Vector
    args = sys.argv[sys.argv.index("--") + 1:]
    mesh, ref_dir, out = args[:3]
    bpy.ops.wm.read_factory_settings(use_empty=True)
    d = np.load(mesh)
    v, f = d["verts"].astype(np.float64), d["faces"]
    me = bpy.data.meshes.new("m")
    me.from_pydata(v.tolist(), [], f.tolist())
    ob = bpy.data.objects.new("m", me)
    sc = bpy.context.scene
    sc.collection.objects.link(ob)
    sc.render.engine = "BLENDER_WORKBENCH"
    sc.render.film_transparent = True
    sc.render.resolution_x = sc.render.resolution_y = 256
    sc.render.image_settings.color_mode = "RGBA"
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
    cam.data.lens = LENS_MM
    sc.collection.objects.link(cam)
    sc.camera = cam
    lo, hi = v.min(0), v.max(0)
    c, diag = (lo + hi) / 2, np.linalg.norm(hi - lo)
    refs = [crop_norm(ref_mask(str(Path(ref_dir) / f"view_{i:02d}.png"))) for i in range(4)]
    tmp = Path(out).with_suffix(".tmp.png")
    scores = {}
    for el in EL:
        for az in AZ:
            e, a = math.radians(el), math.radians(az)
            dvec = np.array([math.cos(e) * math.cos(a), math.cos(e) * math.sin(a), math.sin(e)])
            cam.location = (c + dvec * diag * 2.2).tolist()
            cam.rotation_euler = Vector((-dvec).tolist()).to_track_quat("-Z", "Y").to_euler()
            sc.render.filepath = str(tmp)
            bpy.ops.render.render(write_still=True)
            im = bpy.data.images.load(str(tmp))
            px = np.array(im.pixels[:], dtype=np.float32).reshape(256, 256, 4)[::-1]
            bpy.data.images.remove(im)
            m = crop_norm(px[..., 3] > 0.5)
            scores[(az, el)] = [float((m & r).sum() / max((m | r).sum(), 1)) for r in refs]
    best = []
    for i in range(4):
        (az, el), s = max(scores.items(), key=lambda kv: kv[1][i])
        best.append({"view": i, "azimuth": az, "elevation": el, "iou": round(s[i], 3)})
    Path(out).write_text(json.dumps(best, indent=1))
    tmp.unlink(missing_ok=True)
    print("CALIB " + json.dumps(best))


if __name__ == "__main__":
    main()
