import bpy, bmesh, math
PROFILE = [(0, 0), (0.035, 0), (0.037, 0.005), (0.037, 0.15), (0.03, 0.18), (0.013, 0.21), (0.013, 0.24), (0.015, 0.24), (0.015, 0.25), (0, 0.25)]
me = bpy.data.meshes.new("bottle"); obj = bpy.data.objects.new("bottle", me); bpy.context.collection.objects.link(obj)
bm = bmesh.new(); vs = [bm.verts.new((r, 0, z)) for r, z in PROFILE]
for a, b in zip(vs, vs[1:]): bm.edges.new((a, b))
bmesh.ops.spin(bm, geom=bm.verts[:] + bm.edges[:], angle=2 * math.pi, steps=48, axis=(0, 0, 1), cent=(0, 0, 0))
bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6); bm.to_mesh(me); bm.free()
