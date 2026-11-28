import bpy, math
R, TIRE_R, SPOKES, HUB = 0.33, 0.035, 12, 0.04
bpy.ops.mesh.primitive_torus_add(major_radius=R, minor_radius=TIRE_R, major_segments=96, minor_segments=16, rotation=(math.pi / 2, 0, 0)); bpy.context.object.name = "tire"
bpy.ops.mesh.primitive_cylinder_add(vertices=32, radius=HUB, depth=0.08, rotation=(math.pi / 2, 0, 0)); bpy.context.object.name = "hub"
for i in range(SPOKES):
    a = 2 * math.pi * i / SPOKES
    L = R - HUB
    bpy.ops.mesh.primitive_cylinder_add(vertices=8, radius=0.004, depth=L, location=((HUB + L / 2) * math.cos(a), 0, (HUB + L / 2) * math.sin(a)), rotation=(0, math.pi / 2 - a, 0))
    bpy.context.object.name = "spoke"
