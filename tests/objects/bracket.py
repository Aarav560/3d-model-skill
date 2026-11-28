import bpy
T, W, L1, L2, HOLE = 0.004, 0.03, 0.06, 0.05, 0.003
bpy.ops.mesh.primitive_cube_add(location=(L1 / 2, 0, T / 2)); a = bpy.context.object; a.name = "flange_a"; a.scale = (L1 / 2, W / 2, T / 2)
bpy.ops.mesh.primitive_cube_add(location=(T / 2, 0, L2 / 2)); b = bpy.context.object; b.name = "flange_b"; b.scale = (T / 2, W / 2, L2 / 2)
for o, loc, rot in ((a, (L1 * 0.7, 0, T / 2), (0, 0, 0)), (b, (T / 2, 0, L2 * 0.7), (0, 1.5708, 0))):
    bpy.ops.mesh.primitive_cylinder_add(vertices=32, radius=HOLE, depth=0.02, location=loc, rotation=rot)
    c = bpy.context.object; m = o.modifiers.new("hole", "BOOLEAN"); m.object = c; m.operation = "DIFFERENCE"; c.hide_render = True; c.hide_set(True)
