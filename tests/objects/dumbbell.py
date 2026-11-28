import bpy, math
L, BAR_R, PLATE_R, PLATE_T = 0.35, 0.014, 0.07, 0.03
bpy.ops.mesh.primitive_cylinder_add(vertices=32, radius=BAR_R, depth=L, rotation=(0, math.pi / 2, 0)); bpy.context.object.name = "bar"
for s in (-1, 1):
    for k in range(2):
        x = s * (L / 2 - PLATE_T / 2 - k * PLATE_T)
        bpy.ops.mesh.primitive_cylinder_add(vertices=8, radius=PLATE_R * (1 - 0.15 * k), depth=PLATE_T, location=(x, 0, 0), rotation=(0, math.pi / 2, 0))
        bpy.context.object.name = "plate"
