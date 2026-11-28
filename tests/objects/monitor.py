import bpy
def box(n, loc, s):
    bpy.ops.mesh.primitive_cube_add(location=loc); o = bpy.context.object; o.name = n; o.scale = (s[0]/2, s[1]/2, s[2]/2); return o
box("screen", (0, 0, 0.36), (0.62, 0.025, 0.37))
box("neck", (0, 0.04, 0.16), (0.05, 0.02, 0.24))
box("foot", (0, 0.02, 0.01), (0.25, 0.18, 0.02))
