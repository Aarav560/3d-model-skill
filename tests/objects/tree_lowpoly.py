import bpy
bpy.ops.mesh.primitive_cylinder_add(vertices=8, radius=0.12, depth=1.0, location=(0, 0, 0.5)); bpy.context.object.name = "trunk"
for i, (r, z) in enumerate(((0.9, 1.3), (0.7, 1.9), (0.45, 2.4))):
    bpy.ops.mesh.primitive_cone_add(vertices=8, radius1=r, depth=0.9, location=(0, 0, z)); bpy.context.object.name = "leaves"
