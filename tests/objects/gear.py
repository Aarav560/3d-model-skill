import bpy, bmesh, math
TEETH, R_ROOT, R_TIP, THICK, BORE = 18, 0.040, 0.046, 0.012, 0.008
pts = []
for i in range(TEETH):
    a0 = 2 * math.pi * i / TEETH
    step = 2 * math.pi / TEETH
    for f, r in ((0.0, R_ROOT), (0.15, R_TIP), (0.45, R_TIP), (0.6, R_ROOT)):
        a = a0 + f * step
        pts.append((r * math.cos(a), r * math.sin(a)))
me = bpy.data.meshes.new("gear"); obj = bpy.data.objects.new("gear", me); bpy.context.collection.objects.link(obj)
bm = bmesh.new()
vs = [bm.verts.new((x, y, 0)) for x, y in pts]
face = bm.faces.new(vs)
res = bmesh.ops.extrude_face_region(bm, geom=[face])
moved = [g for g in res["geom"] if isinstance(g, bmesh.types.BMVert)]
bmesh.ops.translate(bm, vec=(0, 0, THICK), verts=moved)
bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
bm.to_mesh(me); bm.free()
bpy.ops.mesh.primitive_cylinder_add(vertices=48, radius=BORE, depth=THICK * 3, location=(0, 0, THICK / 2))
cut = bpy.context.object
m = obj.modifiers.new("bore", "BOOLEAN"); m.object = cut; m.operation = "DIFFERENCE"
cut.hide_render = True; cut.hide_set(True)
