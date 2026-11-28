"""Fixed scoring rig: run a Blender Python program headless and capture its geometry.

Usage (inside the venv that has the `bpy` wheel):

    python render_rig.py --code PROGRAM.py --out DIR [--frame FRAME.json] [--res 256]

What it writes to DIR:
    status.json     ok / error, traceback, timings, Blender version
    geometry.npz    world-space triangle mesh of every visible renderable object
    views.npz       per canonical view: mask, depth, normal (ray-cast, deterministic)
    occupancy.npz   inside/outside voxel grid in the frame cube (ray parity, 3-axis vote)
    frame.json      the normalisation frame (only written when --frame is not given)
    view_<name>.png shaded image per view (what Claude looks at)
    sil_<name>.png  silhouette per view

The rig never depends on a GPU or an OpenGL context: images come from BVH ray casts,
so the same program always gives the same pixels on any machine.

Frame: every comparison happens in the *reference* object's frame (bounding-box centre
and diagonal). Pass the reference's frame.json with --frame when capturing an attempt,
so scale and position errors in the attempt count against it.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
import traceback

import numpy as np

RIG_VERSION = "rig-1.0"

# Canonical orthographic views: name -> (azimuth deg, elevation deg).
# Azimuth 0 looks along +Y (camera sits at -Y, "front"), 90 looks along -X ("right").
VIEWS = {
    "front": (0.0, 0.0),
    "right": (90.0, 0.0),
    "top": (0.0, 90.0),
    "iso": (45.0, 35.264),
}
ORTHO_MARGIN = 1.10  # view width = diagonal * margin
OCC_RES = 48
LIGHT_DIR = np.array([-0.45, -0.6, 0.66])
LIGHT_DIR = LIGHT_DIR / np.linalg.norm(LIGHT_DIR)


def view_basis(az_deg: float, el_deg: float):
    """Return (forward, right, up) unit vectors for a camera looking at the origin."""
    az, el = math.radians(az_deg), math.radians(el_deg)
    # camera position direction (from target to camera)
    cam = np.array([math.sin(az) * math.cos(el), -math.cos(az) * math.cos(el), math.sin(el)])
    fwd = -cam
    world_up = np.array([0.0, 0.0, 1.0])
    if abs(np.dot(fwd, world_up)) > 0.999:  # top view: screen up is +Y
        world_up = np.array([0.0, 1.0, 0.0])
    right = np.cross(fwd, world_up)
    right /= np.linalg.norm(right)
    up = np.cross(right, fwd)
    return fwd, right, up


def run_program(code_path: str) -> None:
    import bpy

    bpy.ops.wm.read_factory_settings(use_empty=True)
    src = open(code_path, encoding="utf-8").read()
    g = {"__name__": "__main__", "__file__": os.path.abspath(code_path)}
    exec(compile(src, code_path, "exec"), g)


def collect_geometry():
    """Evaluated, world-space, triangulated geometry of all visible renderable objects."""
    import bpy

    depsgraph = bpy.context.evaluated_depsgraph_get()
    verts_all, faces_all, parts = [], [], []
    offset = 0
    kinds = {"MESH", "CURVE", "SURFACE", "META", "FONT", "CURVES"}
    for obj in bpy.context.scene.objects:
        if obj.type not in kinds:
            continue
        if obj.hide_render or obj.hide_get():
            continue
        ev = obj.evaluated_get(depsgraph)
        try:
            me = ev.to_mesh()
        except RuntimeError:
            continue
        if me is None:
            continue
        me.calc_loop_triangles()
        n_v = len(me.vertices)
        n_t = len(me.loop_triangles)
        if n_v == 0 or n_t == 0:
            ev.to_mesh_clear()
            continue
        co = np.empty(n_v * 3, dtype=np.float64)
        me.vertices.foreach_get("co", co)
        co = co.reshape(-1, 3)
        mw = np.array(ev.matrix_world, dtype=np.float64)
        co = co @ mw[:3, :3].T + mw[:3, 3]
        tri = np.empty(n_t * 3, dtype=np.int64)
        me.loop_triangles.foreach_get("vertices", tri)
        tri = tri.reshape(-1, 3) + offset
        verts_all.append(co)
        faces_all.append(tri)
        parts.append({"name": obj.name, "verts": n_v, "tris": n_t})
        offset += n_v
        ev.to_mesh_clear()
    if not verts_all:
        return np.zeros((0, 3)), np.zeros((0, 3), dtype=np.int64), parts
    return np.concatenate(verts_all), np.concatenate(faces_all), parts


def make_frame(verts: np.ndarray) -> dict:
    lo, hi = verts.min(0), verts.max(0)
    center = (lo + hi) / 2
    diag = float(np.linalg.norm(hi - lo))
    if diag <= 0:
        diag = 1.0
    return {
        "center": center.tolist(),
        "diag": diag,
        "bbox_min": lo.tolist(),
        "bbox_max": hi.tolist(),
        "dims": (hi - lo).tolist(),
        "view_width": diag * ORTHO_MARGIN,
    }


def build_bvh(verts, faces):
    from mathutils.bvhtree import BVHTree

    return BVHTree.FromPolygons([tuple(v) for v in verts], [tuple(f) for f in faces], all_triangles=True)


def cast_view(bvh, frame, az, el, res):
    from mathutils import Vector

    fwd, right, up = view_basis(az, el)
    c = np.array(frame["center"])
    w = frame["view_width"]
    start_back = frame["diag"] * 2.0
    px = w / res
    mask = np.zeros((res, res), dtype=bool)
    depth = np.full((res, res), np.nan, dtype=np.float32)
    normal = np.zeros((res, res, 3), dtype=np.float32)
    d = Vector(fwd.tolist())
    max_dist = start_back * 2.0
    for r in range(res):
        v = (res / 2 - (r + 0.5)) * px
        row_base = c + up * v - fwd * start_back
        for col in range(res):
            u = ((col + 0.5) - res / 2) * px
            o = row_base + right * u
            loc, nrm, _idx, dist = bvh.ray_cast(Vector(o.tolist()), d, max_dist)
            if loc is not None:
                mask[r, col] = True
                depth[r, col] = dist - start_back
                n = np.array(nrm)
                if np.dot(n, fwd) > 0:  # make normals face the camera
                    n = -n
                normal[r, col] = n
    return mask, depth, normal, (fwd, right, up)


def shade(mask, depth, normal, fwd, frame):
    """Simple deterministic shading: lambert from a fixed light + view-facing fill."""
    lam = np.clip(normal @ LIGHT_DIR, 0, 1)
    fill = np.clip(-(normal @ fwd), 0, 1)
    val = 0.18 + 0.55 * lam + 0.27 * fill
    img = np.ones(mask.shape, dtype=np.float32)
    img[mask] = val[mask]
    # depth-edge darkening helps Claude read overlapping parts
    dd = np.nan_to_num(depth, nan=np.nanmax(depth) if np.any(mask) else 0)
    gy, gx = np.gradient(dd)
    edge = (np.hypot(gx, gy) > frame["diag"] * 0.02) & mask
    img[edge] *= 0.55
    return (np.clip(img, 0, 1) * 255).astype(np.uint8)


def occupancy(bvh, frame, res=OCC_RES):
    """Inside/outside grid by ray parity along x, y and z, majority vote."""
    from mathutils import Vector

    c = np.array(frame["center"])
    half = frame["diag"] / 2 * 1.02
    axis_pts = (np.arange(res) + 0.5) / res * 2 * half - half
    votes = np.zeros((res, res, res), dtype=np.int8)
    eps = frame["diag"] * 1e-6
    for axis in range(3):
        a1, a2 = [i for i in range(3) if i != axis]
        d = np.zeros(3)
        d[axis] = 1.0
        dv = Vector(d.tolist())
        for i in range(res):
            for j in range(res):
                o = c.copy()
                o[a1] += axis_pts[i]
                o[a2] += axis_pts[j]
                o[axis] = c[axis] - half * 1.5
                hits = []
                cur = Vector(o.tolist())
                travelled = 0.0
                while True:
                    loc, _n, _ix, dist = bvh.ray_cast(cur, dv, half * 4)
                    if loc is None:
                        break
                    travelled += dist
                    hits.append(travelled)
                    cur = loc + dv * eps
                    travelled += eps
                    if len(hits) > 200:
                        break
                if len(hits) < 2:
                    continue
                coords = axis_pts + half * 1.5  # distance from ray origin to voxel centres
                inside = (np.searchsorted(np.array(hits), coords) % 2) == 1
                idx = [slice(None)] * 3
                idx[a1], idx[a2] = i, j
                votes[tuple(idx)] += inside.astype(np.int8)
    return votes >= 2


def save_png(path, arr):
    import cv2

    cv2.imwrite(path, arr)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--code", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--frame", help="frame.json of the reference; omit when capturing a reference")
    ap.add_argument("--res", type=int, default=256)
    ap.add_argument("--no-occupancy", action="store_true")
    args = ap.parse_args(argv)
    os.makedirs(args.out, exist_ok=True)
    status = {"rig_version": RIG_VERSION, "code": os.path.abspath(args.code)}
    t0 = time.time()
    try:
        import bpy

        status["blender_version"] = bpy.app.version_string
        run_program(args.code)
        t1 = time.time()
        verts, faces, parts = collect_geometry()
        status["parts"] = parts
        status["n_verts"], status["n_tris"] = int(len(verts)), int(len(faces))
        if len(faces) == 0:
            raise RuntimeError("program produced no renderable geometry")
        np.savez_compressed(os.path.join(args.out, "geometry.npz"), verts=verts, faces=faces)
        if args.frame:
            frame = json.load(open(args.frame))
        else:
            frame = make_frame(verts)
            json.dump(frame, open(os.path.join(args.out, "frame.json"), "w"), indent=2)
        status["own_dims"] = (verts.max(0) - verts.min(0)).tolist()
        bvh = build_bvh(verts, faces)
        out = {}
        for name, (az, el) in VIEWS.items():
            m, dpt, nrm, basis = cast_view(bvh, frame, az, el, args.res)
            out[f"{name}_mask"], out[f"{name}_depth"], out[f"{name}_normal"] = m, dpt, nrm
            img = shade(m, dpt, nrm, basis[0], frame)
            save_png(os.path.join(args.out, f"view_{name}.png"), img)
            save_png(os.path.join(args.out, f"sil_{name}.png"), np.where(m, 0, 255).astype(np.uint8))
        np.savez_compressed(os.path.join(args.out, "views.npz"), **out)
        if not args.no_occupancy:
            occ = occupancy(bvh, frame)
            np.savez_compressed(os.path.join(args.out, "occupancy.npz"), occ=occ)
        status["ok"] = True
        status["t_program"] = round(t1 - t0, 3)
        status["t_total"] = round(time.time() - t0, 3)
    except BaseException as e:  # noqa: BLE001 - a crash in the program is a scored outcome
        status["ok"] = False
        status["error"] = f"{type(e).__name__}: {e}"
        status["traceback"] = traceback.format_exc()[-4000:]
        status["t_total"] = round(time.time() - t0, 3)
    json.dump(status, open(os.path.join(args.out, "status.json"), "w"), indent=2)
    print(json.dumps({k: status.get(k) for k in ("ok", "error", "n_tris", "t_total")}))
    return 0 if status.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
