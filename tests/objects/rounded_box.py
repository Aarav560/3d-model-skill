import bpy
bpy.ops.mesh.primitive_cube_add(location=(0, 0, 0.05)); o = bpy.context.object; o.name = "case"; o.scale = (0.12, 0.07, 0.05)
bpy.ops.object.transform_apply(scale=True)
m = o.modifiers.new("bevel", "BEVEL"); m.width = 0.012; m.segments = 6; m.limit_method = "NONE"
