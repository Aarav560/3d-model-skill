import bpy, bmesh
W, D, WALL_H, ROOF_H = 6.0, 4.0, 2.8, 1.6
bpy.ops.mesh.primitive_cube_add(location=(0, 0, WALL_H / 2)); b = bpy.context.object; b.name = "walls"; b.scale = (W / 2, D / 2, WALL_H / 2)
me = bpy.data.meshes.new("roof"); roof = bpy.data.objects.new("roof", me); bpy.context.collection.objects.link(roof)
bm = bmesh.new(); o = 0.3
p = [(-W/2-o, -D/2-o, WALL_H), (W/2+o, -D/2-o, WALL_H), (W/2+o, 0, WALL_H+ROOF_H), (-W/2-o, 0, WALL_H+ROOF_H), (-W/2-o, D/2+o, WALL_H), (W/2+o, D/2+o, WALL_H)]
v = [bm.verts.new(x) for x in p]
bm.faces.new((v[0], v[1], v[2], v[3])); bm.faces.new((v[3], v[2], v[5], v[4])); bm.faces.new((v[0], v[3], v[4])); bm.faces.new((v[1], v[5], v[2])); bm.faces.new((v[0], v[4], v[5], v[1]))
bm.to_mesh(me); bm.free()
bpy.ops.mesh.primitive_cube_add(location=(W / 2 * 0.5, -D / 2 - 0.05, WALL_H + ROOF_H * 0.6)); c = bpy.context.object; c.name = "chimney"; c.scale = (0.25, 0.25, 0.6)
