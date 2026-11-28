import bpy
W, D, H, T, N = 0.8, 0.3, 1.8, 0.018, 5
def box(name, loc, size):
    bpy.ops.mesh.primitive_cube_add(location=loc)
    o = bpy.context.object; o.name = name; o.scale = (size[0] / 2, size[1] / 2, size[2] / 2); return o
for sx in (-1, 1):
    box("side", (sx * (W / 2 - T / 2), 0, H / 2), (T, D, H))
box("back", (0, D / 2 - 0.003, H / 2), (W, 0.006, H))
inner = W - 2 * T
for i in range(N):
    z = T / 2 + i * (H - T) / (N - 1)
    box("shelf", (0, 0, z), (inner, D, T))
