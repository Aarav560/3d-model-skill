import bpy, bmesh, math
# profile (radius, height) revolved around Z
PROFILE = [(0.0, 0.0), (0.06, 0.0), (0.08, 0.05), (0.09, 0.12), (0.06, 0.2), (0.035, 0.26), (0.04, 0.3), (0.0, 0.3)]
me = bpy.data.meshes.new("vase"); obj = bpy.data.objects.new("vase", me); bpy.context.collection.objects.link(obj)
bm = bmesh.new()
verts = [bm.verts.new((r, 0, z)) for r, z in PROFILE]
for a, b in zip(verts, verts[1:]):
    bm.edges.new((a, b))
bmesh.ops.spin(bm, geom=bm.verts[:] + bm.edges[:], angle=2 * math.pi, steps=64, axis=(0, 0, 1), cent=(0, 0, 0))
bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
bm.to_mesh(me); bm.free()
