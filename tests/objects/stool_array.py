import bpy, math
SEAT_R, H, LEGS = 0.17, 0.62, 3
bpy.ops.mesh.primitive_cylinder_add(vertices=64, radius=SEAT_R, depth=0.035, location=(0, 0, H)); bpy.context.object.name = "seat"
for i in range(LEGS):
    a = 2 * math.pi * i / LEGS
    x, y = 0.12 * math.cos(a), 0.12 * math.sin(a)
    bpy.ops.mesh.primitive_cylinder_add(vertices=16, radius=0.014, depth=H, location=(x * 1.15, y * 1.15, H / 2), rotation=(-math.sin(a) * 0.12, math.cos(a) * 0.12, 0))
    bpy.context.object.name = "leg"
bpy.ops.mesh.primitive_torus_add(major_radius=0.135, minor_radius=0.008, location=(0, 0, H * 0.35)); bpy.context.object.name = "ring"
