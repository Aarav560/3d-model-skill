"""Run a Blender Python program (or import a GLB) headless in bpy and dump the
resulting world-space triangle mesh to .npz (verts float32 Nx3, faces int32 Mx3).

Each call runs in its own subprocess so a crashing / hanging program cannot take the
harness down and every run starts from an empty factory-settings scene.

  python skill/scripts/run_sample.py code  path/to/code.py  out.npz [--seed 0] [--timeout 900]
  python skill/scripts/run_sample.py glb   path/to/object.glb out.npz
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent


def _empty_scene():
    import bpy
    bpy.ops.wm.read_factory_settings(use_empty=True)


def _dump_scene(out: str) -> dict:
    """Collect every visible mesh-like object, evaluated (modifiers/GeoNodes applied),
    in world space, into one triangle soup."""
    import bpy
    import numpy as np

    dg = bpy.context.evaluated_depsgraph_get()
    V, F, off, n_obj = [], [], 0, 0
    for inst in dg.object_instances:  # includes GeoNodes / collection instances
        ob = inst.object
        if ob.type not in {"MESH", "CURVE", "SURFACE", "META", "FONT", "CURVES", "POINTCLOUD"}:
            continue
        orig = ob.original
        if orig.hide_render or orig.hide_get():
            continue
        try:
            me = ob.to_mesh()
        except RuntimeError:
            continue
        if me is None or len(me.polygons) == 0:
            ob.to_mesh_clear()
            continue
        me.calc_loop_triangles()
        nv, nt = len(me.vertices), len(me.loop_triangles)
        co = np.empty(nv * 3, np.float32)
        me.vertices.foreach_get("co", co)
        tri = np.empty(nt * 3, np.int32)
        me.loop_triangles.foreach_get("vertices", tri)
        co = co.reshape(-1, 3)
        M = np.array(inst.matrix_world, dtype=np.float64)
        co = (co @ M[:3, :3].T + M[:3, 3]).astype(np.float32)
        V.append(co)
        F.append(tri.reshape(-1, 3) + off)
        off += nv
        n_obj += 1
        ob.to_mesh_clear()
    verts = np.concatenate(V) if V else np.zeros((0, 3), np.float32)
    faces = np.concatenate(F) if F else np.zeros((0, 3), np.int32)
    np.savez_compressed(out, verts=verts, faces=faces)
    return {"objects": n_obj, "verts": int(len(verts)), "faces": int(len(faces))}


def _child(mode: str, src: str, out: str, seed: int) -> None:
    """Runs inside the subprocess."""
    import bpy
    _empty_scene()
    if mode == "glb":
        bpy.ops.import_scene.gltf(filepath=src)
    else:
        os.environ["SEED"] = str(seed)
        code = Path(src).read_text()
        os.chdir(Path(src).parent)
        g = {"__name__": "__main__", "__file__": src}
        exec(compile(code, src, "exec"), g)
    info = _dump_scene(out)
    info["blender_version"] = bpy.app.version_string
    print("RESULT_JSON " + json.dumps(info), flush=True)


def run(mode: str, src: str, out: str, seed: int = 0, timeout: int = 900) -> dict:
    """Launch the child process; returns {'ok': bool, 'seconds', 'error'?, ...mesh info}."""
    t0 = time.time()
    env = dict(os.environ, SEED=str(seed))
    env.pop("HF_TOKEN", None)  # dataset/attempt code never sees the token
    src, out = str(Path(src).resolve()), str(Path(out).resolve())
    cmd = [sys.executable, str(Path(__file__).resolve()), "--child", mode, src, out, "--seed", str(seed)]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=env)
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"timeout after {timeout}s", "seconds": time.time() - t0}
    res = {"ok": False, "seconds": round(time.time() - t0, 1)}
    for line in p.stdout.splitlines():
        if line.startswith("RESULT_JSON "):
            res.update(json.loads(line[len("RESULT_JSON "):]))
            res["ok"] = res.get("faces", 0) > 0
            if not res["ok"]:
                res["error"] = "no geometry produced"
    if "blender_version" not in res:
        tail = (p.stderr or p.stdout).strip().splitlines()[-6:]
        res["error"] = " | ".join(tail)[-600:] or f"exit code {p.returncode}"
    return res


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--child", action="store_true")
    ap.add_argument("mode", choices=["code", "glb"])
    ap.add_argument("src")
    ap.add_argument("out")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--timeout", type=int, default=900)
    a = ap.parse_args()
    if a.child:
        _child(a.mode, a.src, a.out, a.seed)
    else:
        print(json.dumps(run(a.mode, a.src, a.out, a.seed, a.timeout), indent=1))


if __name__ == "__main__":
    main()
