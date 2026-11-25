"""Stylized character replica: broad-chested man in a cream shirt, red tie, maroon suspenders
with chest pouches, navy trousers, black shoes. Built from a single front reference image.

Run inside Blender (official 5.0.1 binary):
  blender -b --factory-startup --python custom/suspenders_guy/build.py -- OUT_DIR [--final]

Writes OUT_DIR/beauty.png (Cycles, denoised), OUT_DIR/silhouette.png (flat mask, same camera),
OUT_DIR/model.blend and OUT_DIR/model.glb. Units are metres; Z up; the character faces -Y.
Body volumes use skin modifiers on small "armature" polylines + subdivision, one object per
material region (shirt, forearms, trousers, head) so each region keeps its own material.
"""
import math
import sys
from pathlib import Path

import bpy

# ----------------------------------------------------------------------------- dimensions
H = 1.85                                  # total height
# torso / shirt: (z, rx, ry) along the spine
TORSO = [(0.97, 0.15, 0.12), (1.06, 0.17, 0.135), (1.18, 0.26, 0.17), (1.32, 0.33, 0.2), (1.46, 0.33, 0.17)]
NECK = (1.55, 0.082)
SHOULDER = (0.245, 1.48, 0.12)            # x, z, radius of the shirt at the shoulder joint
ELBOW = (0.335, 1.1, 0.092)               # x, z, radius (rolled sleeve ends here)
FOREARM_MID = (0.305, 0.97, 0.088)         # "popeye" forearm bulge
WRIST = (0.24, 0.8, 0.058)   # forearm runs into the fist (no wrist gap)
FIST = (0.235, 0.77, 0.088)
# trousers
PELVIS = (0.86, 0.16, 0.12)
HIP = (0.095, 0.76, 0.095)
KNEE = {-1: 0.1, 1: 0.17}, 0.42, 0.064
ANKLE = {-1: 0.1, 1: 0.24}, 0.11, 0.054   # asymmetric stance: the +X leg steps out
SHOE = (0.115, 0.27, 0.085)               # width, length, height
BELT_Z, BELT_H = 1.0, 0.045
# head
HEAD_C = (0.0, 0.0, 1.71)
HEAD_R = (0.15, 0.145, 0.18)
JAW_R = (0.15, 0.125, 0.09)
NOSE_R = 0.042
# tie & suspenders
TIE_TOP, TIE_BOTTOM, TIE_W0, TIE_W1 = 1.47, 1.04, 0.07, 0.14
STRAP_R, STRAP_X = 0.021, 0.13
POUCH = (0.085, 0.05, 0.13)              # width, depth, height
POUCH_Z = 1.12

COLORS = {
    "shirt": (0.80, 0.70, 0.52), "skin": (0.80, 0.52, 0.36), "tie": (0.78, 0.26, 0.21),
    "strap": (0.38, 0.09, 0.10), "pants": (0.012, 0.018, 0.045), "shoe": (0.02, 0.02, 0.02),
    "hair": (0.05, 0.03, 0.02), "metal": (0.75, 0.75, 0.78), "eye": (0.02, 0.02, 0.02),
}


# ----------------------------------------------------------------------------- helpers
def material(name, rough=0.6, metal=0.0):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes.get("Principled BSDF")
    b.inputs["Base Color"].default_value = (*COLORS[name], 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    return m


def finish(ob, mat, subsurf=2):
    if subsurf:
        s = ob.modifiers.new("smooth", "SUBSURF")
        s.levels = s.render_levels = subsurf
    ob.data.materials.append(mat)
    for p in ob.data.polygons:
        p.use_smooth = True
    return ob


def skin_object(name, verts, edges, radii, mat, subsurf=2):
    """Polyline 'armature' -> skin modifier volume. radii: (rx, ry) per vertex."""
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, edges, [])
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    ob.modifiers.new("skin", "SKIN")
    for i, r in enumerate(radii):
        me.skin_vertices[0].data[i].radius = r
    me.skin_vertices[0].data[0].use_root = True
    return finish(ob, mat, subsurf)


def ellipsoid(name, center, radii, mat, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=16, radius=1, location=center, rotation=rot)
    ob = bpy.context.active_object
    ob.name = name
    ob.scale = radii
    return finish(ob, mat, 1)


def rbox(name, center, size, mat, bevel=0.01, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_cube_add(size=1, location=center, rotation=rot)
    ob = bpy.context.active_object
    ob.name = name
    ob.scale = size
    bpy.ops.object.transform_apply(scale=True)
    b = ob.modifiers.new("bevel", "BEVEL")
    b.width, b.segments = bevel, 3
    return finish(ob, mat, 0)


def chest_front_y(z):
    """Approximate y of the shirt surface at height z (front = -y)."""
    pts = sorted(TORSO)
    for (z0, _, y0), (z1, _, y1) in zip(pts, pts[1:]):
        if z0 <= z <= z1:
            t = (z - z0) / (z1 - z0)
            return -((y0 + (y1 - y0) * t) + 0.02)
    return -(pts[-1][2] + 0.02)


# ----------------------------------------------------------------------------- parts
def shirt(m):
    v = [(0, 0, z) for z, _, _ in TORSO]
    r = [(rx, ry) for _, rx, ry in TORSO]
    e = [(i, i + 1) for i in range(len(v) - 1)]
    top = len(v) - 1
    for s in (-1, 1):  # shoulders + upper arms (sleeves)
        i = len(v)
        v += [(s * SHOULDER[0], 0, SHOULDER[1]), (s * ELBOW[0], 0, ELBOW[1])]
        r += [(SHOULDER[2], SHOULDER[2] * 0.95), (ELBOW[2], ELBOW[2])]
        e += [(top, i), (i, i + 1)]
    skin_object("shirt", v, e, r, m["shirt"])
    for s in (-1, 1):  # rolled sleeve cuffs
        bpy.ops.mesh.primitive_torus_add(major_radius=ELBOW[2] * 0.85, minor_radius=0.035,
                                         location=(s * ELBOW[0] * 0.99, 0, ELBOW[1] + 0.01),
                                         rotation=(0, s * 0.35, 0))
        finish(bpy.context.active_object, m["shirt"], 1)
    for s in (-1, 1):  # open collar flaps
        rbox(f"collar_{s}", (s * 0.075, -0.07, 1.52), (0.09, 0.02, 0.07), m["shirt"], 0.008,
             rot=(0.5, 0, s * -0.5))


def arms(m):
    for s in (-1, 1):
        skin_object(f"forearm_{s}",
                    [(s * ELBOW[0], 0, ELBOW[1] + 0.02), (s * FOREARM_MID[0], -0.01, FOREARM_MID[1]), (s * WRIST[0], -0.01, WRIST[1])],
                    [(0, 1), (1, 2)],
                    [(ELBOW[2] * 0.85,) * 2, (FOREARM_MID[2],) * 2, (WRIST[2],) * 2], m["skin"])
        f = rbox(f"fist_{s}", (s * FIST[0], -0.01, FIST[1]), (FIST[2] * 1.3, FIST[2] * 1.45, FIST[2] * 1.5), m["skin"], 0.03)
        sub = f.modifiers.new("smooth", "SUBSURF")   # rounded, clenched-fist block
        sub.levels = sub.render_levels = 2
        for p in f.data.polygons:
            p.use_smooth = True


def head(m):
    skin_object("neck", [(0, 0, 1.44), (0, 0.0, NECK[0])], [(0, 1)], [(NECK[1] * 1.2,) * 2, (NECK[1],) * 2], m["skin"])
    cx, cy, cz = HEAD_C
    ellipsoid("skull", (cx, cy + 0.01, cz + 0.03), (0.13, 0.135, 0.15), m["skin"])
    ellipsoid("jaw", (cx, cy - 0.03, cz - 0.07), (0.15, 0.12, 0.085), m["skin"])          # big square jaw
    ellipsoid("chin", (cx, cy - 0.105, cz - 0.12), (0.075, 0.05, 0.045), m["skin"])
    for s in (-1, 1):
        ellipsoid(f"chin_lobe_{s}", (s * 0.025, cy - 0.125, cz - 0.12), (0.035, 0.03, 0.035), m["skin"])  # cleft chin
    ellipsoid("nose", (cx, cy - 0.14, cz - 0.005), (0.03, 0.035, 0.04), m["skin"])
    ellipsoid("brow", (cx, cy - 0.11, cz + 0.035), (0.12, 0.045, 0.028), m["skin"])
    for s in (-1, 1):
        ellipsoid(f"ear_{s}", (s * 0.135, cy + 0.01, cz - 0.005), (0.022, 0.035, 0.045), m["skin"])
        ellipsoid(f"eye_{s}", (s * 0.045, cy - 0.118, cz + 0.012), (0.016, 0.008, 0.009), m["eye"])
        ellipsoid(f"eyebrow_{s}", (s * 0.052, cy - 0.142, cz + 0.042), (0.04, 0.013, 0.012), m["hair"], rot=(0, s * -0.2, 0))
    ellipsoid("hair", (cx, cy + 0.03, cz + 0.1), (0.145, 0.15, 0.095), m["hair"])        # slicked back
    ellipsoid("hair_front", (cx + 0.02, cy - 0.07, cz + 0.13), (0.12, 0.07, 0.04), m["hair"], rot=(0.25, 0, -0.15))
    for s in (-1, 1):
        ellipsoid(f"sideburn_{s}", (s * 0.128, cy - 0.01, cz + 0.03), (0.02, 0.04, 0.05), m["hair"])


def trousers(m):
    v = [(0, 0, BELT_Z + 0.02), (0, 0, PELVIS[0])]
    r = [(TORSO[0][1], TORSO[0][2]), (PELVIS[1], PELVIS[2])]
    e = [(0, 1)]
    for s in (-1, 1):
        i = len(v)
        v += [(s * HIP[0], 0, HIP[1]), (s * KNEE[0][s], 0, KNEE[1]), (s * ANKLE[0][s], 0, ANKLE[1])]
        r += [(HIP[2],) * 2, (KNEE[2],) * 2, (ANKLE[2],) * 2]
        e += [(1, i), (i, i + 1), (i + 1, i + 2)]
    skin_object("trousers", v, e, r, m["pants"])
    for s in (-1, 1):
        rbox(f"shoe_{s}", (s * ANKLE[0][s], -0.06, SHOE[2] / 2), (SHOE[0], SHOE[1], SHOE[2]), m["shoe"], 0.03,
             rot=(0, 0, s * 0.25))
    bpy.ops.mesh.primitive_cylinder_add(radius=1, depth=BELT_H, location=(0, 0, BELT_Z))
    belt = bpy.context.active_object
    belt.scale = (TORSO[0][1] + 0.012, TORSO[0][2] + 0.012, 1)
    finish(belt, m["pants"], 0)
    rbox("buckle", (0, -(TORSO[0][2] + 0.02), BELT_Z), (0.05, 0.01, 0.04), m["metal"], 0.004)


def tie(m):
    import bmesh
    bm = bmesh.new()
    rows = []
    n = 12
    for i in range(n + 1):
        t = i / n
        z = TIE_TOP + (TIE_BOTTOM - TIE_TOP) * t
        w = TIE_W0 + (TIE_W1 - TIE_W0) * t
        y = chest_front_y(z) - 0.005
        rows.append((bm.verts.new((-w / 2 + 0.01 * t, y, z)), bm.verts.new((w / 2 + 0.01 * t, y, z))))
    tip = bm.verts.new((0.01, chest_front_y(TIE_BOTTOM) - 0.005, TIE_BOTTOM - 0.06))
    for a, b in zip(rows, rows[1:]):
        bm.faces.new((a[0], a[1], b[1], b[0]))
    bm.faces.new((rows[-1][0], rows[-1][1], tip))
    me = bpy.data.meshes.new("tie")
    bm.to_mesh(me)
    ob = bpy.data.objects.new("tie", me)
    bpy.context.scene.collection.objects.link(ob)
    ob.modifiers.new("thick", "SOLIDIFY").thickness = 0.012
    finish(ob, m["tie"], 1)
    ellipsoid("tie_knot", (0, chest_front_y(1.48) - 0.03, 1.49), (0.045, 0.03, 0.035), m["tie"])


def suspenders(m):
    for s in (-1, 1):
        pts = [(s * STRAP_X * 0.75, chest_front_y(1.02), 1.02), (s * STRAP_X, chest_front_y(1.2), 1.2),
               (s * STRAP_X * 1.15, chest_front_y(1.36), 1.36), (s * 0.15, -0.09, 1.5),
               (s * 0.15, 0.09, 1.5), (s * 0.11, 0.18, 1.3), (s * 0.06, 0.15, 1.02)]
        cu = bpy.data.curves.new(f"strap_{s}", "CURVE")
        cu.dimensions = "3D"
        sp = cu.splines.new("NURBS")
        sp.points.add(len(pts) - 1)
        for p, co in zip(sp.points, pts):
            p.co = (*co, 1)
        sp.use_endpoint_u = True
        sp.order_u = 3
        cu.bevel_depth = STRAP_R
        cu.bevel_resolution = 2
        ob = bpy.data.objects.new(f"strap_{s}", cu)
        bpy.context.scene.collection.objects.link(ob)
        ob.data.materials.append(m["strap"])
        rbox(f"pouch_{s}", (s * STRAP_X, chest_front_y(POUCH_Z) - POUCH[1] / 2, POUCH_Z), POUCH, m["strap"], 0.012)
        rbox(f"clip_{s}", (s * STRAP_X * 1.1, chest_front_y(1.3) - 0.02, 1.3), (0.03, 0.012, 0.035), m["metal"], 0.004)


# ----------------------------------------------------------------------------- scene
def setup_scene(out: Path, final: bool):
    sc = bpy.context.scene
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
    cam.data.lens = 70
    sc.collection.objects.link(cam)
    cam.location = (-0.3, -4.6, 1.1)
    from mathutils import Vector
    cam.rotation_euler = (Vector((0, 0, 0.95)) - cam.location).to_track_quat("-Z", "Y").to_euler()
    sc.camera = cam
    sc.render.resolution_x = sc.render.resolution_y = 430
    sc.view_settings.view_transform = "Standard"
    world = sc.world or bpy.data.worlds.new("w")
    sc.world = world
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.035, 0.035, 0.037, 1)
    # backdrop floor (catches the soft shadow, like the reference)
    bpy.ops.mesh.primitive_plane_add(size=30, location=(0, 0, 0))
    floor = bpy.context.active_object
    fm = bpy.data.materials.new("floor")
    fm.use_nodes = True
    fm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.009, 0.009, 0.01, 1)
    floor.data.materials.append(fm)
    for name, loc, energy, size in (("key", (-2.5, -3.0, 4.0), 140, 2.5), ("fill", (3.0, -2.5, 2.0), 40, 3.0),
                                    ("rim", (1.5, 3.0, 3.0), 220, 1.5)):
        li = bpy.data.objects.new(name, bpy.data.lights.new(name, "AREA"))
        li.data.energy, li.data.size = energy, size
        li.location = loc
        li.rotation_euler = (Vector((0, 0, 1.0)) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
        sc.collection.objects.link(li)
    return floor


def render(out: Path, floor, final: bool):
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = 128 if final else 24
    sc.cycles.use_denoising = True
    if final:
        sc.render.resolution_x = sc.render.resolution_y = 860
    sc.render.filepath = str(out / "beauty.png")
    bpy.ops.render.render(write_still=True)
    if final:  # turnaround views (same distance, orbiting the character)
        cam = sc.camera
        from mathutils import Vector
        base = cam.location.copy()
        for az in (35, 90, 180, 270):
            a = math.radians(az)
            cam.location = (base.x * math.cos(a) - base.y * math.sin(a), base.x * math.sin(a) + base.y * math.cos(a), base.z)
            cam.rotation_euler = (Vector((0, 0, 0.95)) - cam.location).to_track_quat("-Z", "Y").to_euler()
            sc.render.filepath = str(out / f"turn_{az:03d}.png")
            bpy.ops.render.render(write_still=True)
        cam.location = base
        cam.rotation_euler = (Vector((0, 0, 0.95)) - base).to_track_quat("-Z", "Y").to_euler()
        sc.render.resolution_x = sc.render.resolution_y = 430
    # flat silhouette from the same camera (no floor)
    floor.hide_render = True
    sc.render.engine = "BLENDER_WORKBENCH"
    sc.display.shading.light = "FLAT"
    sc.display.shading.color_type = "SINGLE"
    sc.display.shading.single_color = (1, 1, 1)
    sc.render.film_transparent = True
    sc.render.image_settings.color_mode = "RGBA"
    sc.render.filepath = str(out / "silhouette.png")
    bpy.ops.render.render(write_still=True)
    floor.hide_render = False


def main():
    args = sys.argv[sys.argv.index("--") + 1:]
    out = Path(args[0]).resolve()
    final = "--final" in args
    out.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    m = {k: material(k) for k in COLORS}
    m["shoe"].node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.25
    m["metal"].node_tree.nodes["Principled BSDF"].inputs["Metallic"].default_value = 1.0
    m["shirt"].node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.8
    shirt(m); arms(m); head(m); trousers(m); tie(m); suspenders(m)
    floor = setup_scene(out, final)
    render(out, floor, final)
    floor.hide_set(True)
    bpy.ops.wm.save_as_mainfile(filepath=str(out / "model.blend"))
    bpy.data.objects.remove(floor)
    for o in [o for o in bpy.data.objects if o.type in {"CAMERA", "LIGHT"}]:
        bpy.data.objects.remove(o)
    bpy.ops.export_scene.gltf(filepath=str(out / "model.glb"), export_apply=True)


main()
