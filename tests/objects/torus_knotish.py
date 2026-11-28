import bpy, math
curve = bpy.data.curves.new("knot", "CURVE"); curve.dimensions = "3D"
sp = curve.splines.new("POLY"); N = 200; sp.points.add(N - 1); sp.use_cyclic_u = True
p, q = 2, 3
for i in range(N):
    t = 2 * math.pi * i / N
    r = 0.5 + 0.2 * math.cos(q * t)
    sp.points[i].co = (r * math.cos(p * t), r * math.sin(p * t), 0.2 * math.sin(q * t), 1)
curve.bevel_depth = 0.07; curve.bevel_resolution = 4
obj = bpy.data.objects.new("knot", curve); bpy.context.collection.objects.link(obj)
