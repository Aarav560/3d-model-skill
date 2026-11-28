import bpy
SEAT, SEAT_H, T, BACK_H, LEG = 0.45, 0.45, 0.04, 0.45, 0.04
def box(name, loc, size):
    bpy.ops.mesh.primitive_cube_add(location=loc)
    o = bpy.context.object; o.name = name; o.scale = (size[0] / 2, size[1] / 2, size[2] / 2)
    return o
box("seat", (0, 0, SEAT_H - T / 2), (SEAT, SEAT, T))
for sx in (-1, 1):
    for sy in (-1, 1):
        box("leg", (sx * (SEAT / 2 - LEG / 2), sy * (SEAT / 2 - LEG / 2), (SEAT_H - T) / 2), (LEG, LEG, SEAT_H - T))
box("back", (0, SEAT / 2 - T / 2, SEAT_H + BACK_H / 2), (SEAT, T, BACK_H))
for sx in (-1, 1):
    box("post", (sx * (SEAT / 2 - LEG / 2), SEAT / 2 - LEG / 2, SEAT_H + BACK_H / 2), (LEG, LEG, BACK_H))
