import bpy, math
HEAD_AF, HEAD_H, SHANK_R, SHANK_L = 0.013, 0.0055, 0.004, 0.03
bpy.ops.mesh.primitive_cylinder_add(vertices=6, radius=HEAD_AF / math.sqrt(3), depth=HEAD_H, location=(0, 0, SHANK_L + HEAD_H / 2))
bpy.context.object.name = "head"
bpy.ops.mesh.primitive_cylinder_add(vertices=48, radius=SHANK_R, depth=SHANK_L, location=(0, 0, SHANK_L / 2))
bpy.context.object.name = "shank"
bpy.ops.mesh.primitive_cone_add(vertices=48, radius1=SHANK_R * 0.6, radius2=SHANK_R, depth=0.0015, location=(0, 0, -0.00075))
bpy.context.object.name = "chamfer_tip"
