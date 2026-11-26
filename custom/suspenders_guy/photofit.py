"""Character v2 ("photo-fit"): geometry inflated from the reference silhouette + photo colors projected
from the front camera (spec section 8: camera match, fit, project photo colors).

  blender -b --factory-startup --python custom/suspenders_guy/photofit.py -- REF.jpg REF_MASK.png OUT_DIR [--final]

How the geometry is made:
  * every mask pixel becomes a vertex on a front sheet and a back sheet;
  * depth = round "inflation": h = sqrt(d * (2r - d)), where d is the distance to the silhouette edge and
    r the local part radius (max of d nearby). Limbs get circular cross-sections, the torso a deep chest;
  * the two sheets meet at the silhouette edge (h = 0) and are welded into one closed mesh.
Limits: everything not visible from the front (back, sides, the gap between overlapping parts) is inferred.
The front colors come from the photo itself; the back reuses the same projection.
"""
import sys
from pathlib import Path

import bmesh
import bpy
import numpy as np

HEIGHT_M = 1.85          # assumed real height (scale only)
STEP = 2                 # pixel stride of the grid
DEPTH_SCALE = 0.8        # flatten the inflation slightly (bodies are deeper than wide only at the chest)
LOCAL_R_PX = 21          # neighbourhood used to estimate the local part radius


def load_mask(path):
    img = bpy.data.images.load(path)
    w, h = img.size
    a = np.array(img.pixels[:], dtype=np.float32).reshape(h, w, img.channels)[::-1, :, 0]
    return a > 0.5


def distance_and_radius(mask):
    from scipy import ndimage
    d = ndimage.distance_transform_edt(mask)
    r = ndimage.grey_dilation(d, size=(LOCAL_R_PX, LOCAL_R_PX))
    r = np.maximum(r, d)
    h = np.sqrt(np.clip(d * (2 * r - d), 0, None)) * DEPTH_SCALE
    return d, h


def build(mask, h, ref_path):
    H, W = mask.shape
    ys, xs = np.nonzero(mask)
    top, bot = ys.min(), ys.max()
    s = HEIGHT_M / (bot - top)              # metres per pixel
    cx = (xs.min() + xs.max()) / 2
    bm = bmesh.new()
    uv_layer = bm.loops.layers.uv.new("uv")
    idx = {}
    for side, sign in (("front", -1), ("back", 1)):
        for y in range(0, H, STEP):
            for x in range(0, W, STEP):
                if mask[y, x]:
                    depth = h[y, x] if h[y, x] > 0.75 else 0.0       # sheets meet at the edge
                    idx[(side, y, x)] = bm.verts.new(((x - cx) * s, sign * depth * s, (bot - y) * s))
    bm.verts.ensure_lookup_table()
    for side in ("front", "back"):
        for y in range(0, H - STEP, STEP):
            for x in range(0, W - STEP, STEP):
                q = [(side, y, x), (side, y, x + STEP), (side, y + STEP, x + STEP), (side, y + STEP, x)]
                if all(k in idx for k in q):
                    vs = [idx[k] for k in q]
                    if side == "back":
                        vs = vs[::-1]
                    f = bm.faces.new(vs)
                    for loop, k in zip(f.loops, q if side == "front" else q[::-1]):
                        loop[uv_layer].uv = (k[2] / W, 1 - k[1] / H)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=s * 0.5)   # weld front/back along the silhouette
    me = bpy.data.meshes.new("character")
    bm.to_mesh(me)
    ob = bpy.data.objects.new("character", me)
    bpy.context.scene.collection.objects.link(ob)
    for p in me.polygons:
        p.use_smooth = True
    sm = ob.modifiers.new("smooth", "CORRECTIVE_SMOOTH")
    sm.iterations = 4
    mat = bpy.data.materials.new("photo")
    mat.use_nodes = True
    nt = mat.node_tree
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = bpy.data.images.load(ref_path)
    tex.interpolation = "Cubic"
    bsdf = nt.nodes["Principled BSDF"]
    nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.7
    # the photo already contains its lighting: add it as emission so the front view reproduces it
    nt.links.new(tex.outputs["Color"], bsdf.inputs["Emission Color"])
    bsdf.inputs["Emission Strength"].default_value = 0.85
    me.materials.append(mat)
    return ob, s, (bot - top) * s


def scene(out, H, W, s, total_h, final):
    import math
    from mathutils import Vector
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = 64 if final else 16
    sc.cycles.use_denoising = True
    sc.view_settings.view_transform = "Standard"
    sc.render.resolution_x, sc.render.resolution_y = W, H
    world = bpy.data.worlds.new("w")
    sc.world = world
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.04, 0.04, 0.042, 1)
    li = bpy.data.objects.new("key", bpy.data.lights.new("key", "AREA"))
    li.data.energy, li.data.size = 60, 3
    li.location = (-2, -3, 3)
    li.rotation_euler = (Vector((0, 0, 1)) - li.location).to_track_quat("-Z", "Y").to_euler()
    sc.collection.objects.link(li)
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
    cam.data.type = "ORTHO"
    cam.data.ortho_scale = W * s            # one image pixel = one render pixel
    sc.collection.objects.link(cam)
    sc.camera = cam
    return cam


def render_views(out, cam, mask_shape, s, bot_px, cx_px, final):
    import math
    from mathutils import Vector
    sc = bpy.context.scene
    H, W = mask_shape
    # front camera reproduces the reference framing exactly (orthographic, pixel aligned)
    cam.location = ((W / 2 - cx_px) * s, -6, (bot_px - H / 2) * s)
    cam.rotation_euler = (math.pi / 2, 0, 0)
    sc.render.filepath = str(out / "front.png")
    bpy.ops.render.render(write_still=True)
    # silhouette
    sc.render.engine = "BLENDER_WORKBENCH"
    sc.display.shading.light = "FLAT"
    sc.display.shading.color_type = "SINGLE"
    sc.display.shading.single_color = (1, 1, 1)
    sc.render.film_transparent = True
    sc.render.image_settings.color_mode = "RGBA"
    sc.render.filepath = str(out / "silhouette.png")
    bpy.ops.render.render(write_still=True)
    sc.render.film_transparent = False
    sc.render.image_settings.color_mode = "RGB"
    sc.render.engine = "CYCLES"
    if final:  # perspective turnaround to show the 3D shape honestly
        cam.data.type = "PERSP"
        cam.data.lens = 70
        tgt = Vector((0, 0, 0.95))
        for az in (0, 35, 90, 180):
            a = math.radians(az)
            cam.location = (4.6 * math.sin(a), -4.6 * math.cos(a), 1.1)
            cam.rotation_euler = (tgt - cam.location).to_track_quat("-Z", "Y").to_euler()
            sc.render.filepath = str(out / f"turn_{az:03d}.png")
            bpy.ops.render.render(write_still=True)


def main():
    args = sys.argv[sys.argv.index("--") + 1:]
    ref, mask_p, out = args[0], args[1], Path(args[2]).resolve()
    final = "--final" in args
    out.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    mask = load_mask(str(Path(mask_p).resolve()))
    _, h = distance_and_radius(mask)
    ob, s, total_h = build(mask, h, str(Path(ref).resolve()))
    ys, xs = np.nonzero(mask)
    cam = scene(out, *mask.shape, s, total_h, final)
    render_views(out, cam, mask.shape, s, ys.max(), (xs.min() + xs.max()) / 2, final)
    bpy.ops.wm.save_as_mainfile(filepath=str(out / "model.blend"))
    bpy.ops.export_scene.gltf(filepath=str(out / "model.glb"), export_apply=True)
    bpy.ops.wm.stl_export(filepath=str(out / "model.stl"), apply_modifiers=True)


main()
