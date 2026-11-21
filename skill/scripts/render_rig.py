"""Fixed scoring render rig (separate from pretty renders).

4 canonical orthographic cameras (azimuth 45/135/225/315 deg, elevation 30 deg), one
neutral studio light (Workbench), single grey material, transparent film composited
onto white, fixed resolution. Workbench is deterministic, so no sampling seed is needed.

The frame (center + scale) always comes from the GROUND-TRUTH mesh, so a prediction
that is the wrong size or offset is penalised instead of being normalised away.

  python skill/scripts/render_rig.py mesh.npz frame_mesh.npz out_dir
writes out_dir/view_0{0..3}.png (RGBA) and out_dir/rig.json.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

RIG_VERSION = "rig-v1"
RES = 512
AZIMUTHS = (45.0, 135.0, 225.0, 315.0)
ELEVATION = 30.0
MARGIN = 1.10  # ortho scale = bbox diagonal * margin; whole GT always in frame


def frame_of(npz_path: str) -> dict:
    import numpy as np
    v = np.load(npz_path)["verts"].astype(np.float64)
    lo, hi = v.min(0), v.max(0)
    return {"center": ((lo + hi) / 2).tolist(), "diag": float(np.linalg.norm(hi - lo))}


def render(mesh_npz: str, frame: dict, out_dir: str) -> list[str]:
    import bpy
    import numpy as np

    bpy.ops.wm.read_factory_settings(use_empty=True)
    d = np.load(mesh_npz)
    verts, faces = d["verts"].astype(np.float64), d["faces"]
    me = bpy.data.meshes.new("m")
    me.vertices.add(len(verts))
    me.vertices.foreach_set("co", verts.ravel())
    me.loops.add(faces.size)
    me.loops.foreach_set("vertex_index", faces.ravel())
    me.polygons.add(len(faces))
    me.polygons.foreach_set("loop_start", np.arange(0, faces.size, 3))
    me.polygons.foreach_set("loop_total", np.full(len(faces), 3))
    me.update(calc_edges=True)
    me.validate(clean_customdata=False)
    ob = bpy.data.objects.new("m", me)
    sc = bpy.context.scene
    sc.collection.objects.link(ob)

    sc.render.engine = "BLENDER_WORKBENCH"
    sh = sc.display.shading
    sh.light = "STUDIO"
    sh.color_type = "SINGLE"
    sh.single_color = (0.8, 0.8, 0.8)
    sh.show_backface_culling = False
    sh.show_cavity = False
    sh.show_shadows = False
    sh.show_object_outline = False
    sc.display.render_aa = "8"
    sc.render.film_transparent = True
    sc.render.resolution_x = sc.render.resolution_y = RES
    sc.render.resolution_percentage = 100
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_mode = "RGBA"
    sc.view_settings.view_transform = "Standard"

    c = np.array(frame["center"])
    diag = max(frame["diag"], 1e-6)
    cam_data = bpy.data.cameras.new("cam")
    cam_data.type = "ORTHO"
    cam_data.ortho_scale = diag * MARGIN
    cam_data.clip_start = diag * 0.01
    cam_data.clip_end = diag * 10
    cam = bpy.data.objects.new("cam", cam_data)
    sc.collection.objects.link(cam)
    sc.camera = cam

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    paths = []
    el = math.radians(ELEVATION)
    for i, az_deg in enumerate(AZIMUTHS):
        az = math.radians(az_deg)
        direction = np.array([math.cos(el) * math.cos(az), math.cos(el) * math.sin(az), math.sin(el)])
        cam.location = (c + direction * diag * 2).tolist()
        from mathutils import Vector
        cam.rotation_euler = Vector((-direction).tolist()).to_track_quat("-Z", "Y").to_euler()
        p = str(out / f"view_{i:02d}.png")
        sc.render.filepath = p
        bpy.ops.render.render(write_still=True)
        paths.append(p)
    (out / "rig.json").write_text(json.dumps({
        "rig_version": RIG_VERSION, "res": RES, "azimuths": AZIMUTHS, "elevation": ELEVATION,
        "frame": frame, "blender_version": bpy.app.version_string}, indent=1))
    return paths


if __name__ == "__main__":
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    mesh, frame_mesh, out = args[:3]
    render(mesh, frame_of(frame_mesh), out)
