import bpy
bpy.ops.mesh.primitive_cylinder_add(vertices=64, radius=0.09, depth=0.02, location=(0, 0, 0.01)); bpy.context.object.name = "base"
bpy.ops.mesh.primitive_cylinder_add(vertices=32, radius=0.008, depth=0.4, location=(0, 0, 0.22)); bpy.context.object.name = "pole"
bpy.ops.mesh.primitive_cone_add(vertices=64, radius1=0.14, radius2=0.07, depth=0.16, location=(0, 0, 0.47)); bpy.context.object.name = "shade"
