import bpy, math
R, H, WALL = 0.045, 0.1, 0.004
bpy.ops.mesh.primitive_cylinder_add(vertices=64, radius=R, depth=H, location=(0, 0, H / 2))
body = bpy.context.object; body.name = "body"
bpy.ops.mesh.primitive_cylinder_add(vertices=64, radius=R - WALL, depth=H, location=(0, 0, H / 2 + WALL))
cut = bpy.context.object
m = body.modifiers.new("hollow", "BOOLEAN"); m.object = cut; m.operation = "DIFFERENCE"
cut.hide_render = True; cut.hide_set(True)
bpy.ops.mesh.primitive_torus_add(major_radius=0.028, minor_radius=0.006, location=(R + 0.015, 0, H * 0.55), rotation=(math.pi / 2, 0, 0))
bpy.context.object.name = "handle"
