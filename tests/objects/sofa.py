import bpy
def rbox(n, loc, s, bev=0.03):
    bpy.ops.mesh.primitive_cube_add(location=loc); o = bpy.context.object; o.name = n; o.scale = (s[0]/2, s[1]/2, s[2]/2)
    bpy.ops.object.transform_apply(scale=True); m = o.modifiers.new("b", "BEVEL"); m.width = bev; m.segments = 4; m.limit_method = "NONE"; return o
rbox("base", (0, 0, 0.22), (2.0, 0.9, 0.24))
for i in (-1, 0, 1):
    rbox("cushion", (i * 0.6, -0.05, 0.4), (0.58, 0.75, 0.14), 0.05)
rbox("back", (0, 0.36, 0.62), (2.0, 0.18, 0.6))
for s in (-1, 1):
    rbox("arm", (s * 0.95, 0, 0.42), (0.16, 0.9, 0.44))
for sx in (-1, 1):
    for sy in (-1, 1):
        bpy.ops.mesh.primitive_cylinder_add(vertices=16, radius=0.03, depth=0.1, location=(sx * 0.9, sy * 0.38, 0.05)); bpy.context.object.name = "foot"
