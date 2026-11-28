import bpy
TOP_W, TOP_D, TOP_T, H, LEG = 1.6, 0.9, 0.05, 0.75, 0.06
bpy.ops.mesh.primitive_cube_add(location=(0, 0, H - TOP_T / 2))
top = bpy.context.object; top.name = "top"; top.scale = (TOP_W / 2, TOP_D / 2, TOP_T / 2)
for sx in (-1, 1):
    for sy in (-1, 1):
        bpy.ops.mesh.primitive_cube_add(location=(sx * (TOP_W / 2 - 0.1), sy * (TOP_D / 2 - 0.1), (H - TOP_T) / 2))
        leg = bpy.context.object; leg.name = "leg"; leg.scale = (LEG / 2, LEG / 2, (H - TOP_T) / 2)
