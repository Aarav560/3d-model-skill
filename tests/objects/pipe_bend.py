import bpy, math
# quarter-circle pipe made from a bevelled curve
curve = bpy.data.curves.new("pipe", "CURVE"); curve.dimensions = "3D"
sp = curve.splines.new("POLY"); N = 24; R = 0.3
sp.points.add(N)
for i in range(N + 1):
    a = (math.pi / 2) * i / N
    sp.points[i].co = (R * math.cos(a), 0, R * math.sin(a), 1)
curve.bevel_depth = 0.04; curve.bevel_resolution = 6; curve.use_fill_caps = True
obj = bpy.data.objects.new("pipe", curve); bpy.context.collection.objects.link(obj)
for loc, rot in (((R, 0, -0.05), (0, 0, 0)), ((-0.05, 0, R), (0, math.pi / 2, 0))):
    bpy.ops.mesh.primitive_cylinder_add(vertices=32, radius=0.055, depth=0.1, location=loc, rotation=rot); bpy.context.object.name = "flange"
