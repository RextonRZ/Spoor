"""Hide a ceiling embedded in a merged mesh, in memory only; restore before the next view."""
_ORIGINAL={}


def restore(scene):
    import bpy
    for name,original in list(_ORIGINAL.items()):
        obj=scene.objects.get(name)
        if obj:
            temporary=obj.data; obj.data=original
            if temporary.users==0 and temporary.name.startswith('locator_ceiling_cutaway'):
                bpy.data.meshes.remove(temporary)
    _ORIGINAL.clear()


def office_ceiling(scene,spec,zone):
    import bmesh
    if zone['kind']!='office': return []
    obj=scene.objects.get('fixtures')
    if not obj: raise RuntimeError('Missing merged office fixtures mesh')
    poly=zone['polygon_m']; xs=[p[0] for p in poly]; ys=[p[1] for p in poly]
    x0,x1,y0,y1=min(xs),max(xs),min(ys),max(ys)
    height=spec['fixtures']['office']['wall_height_m']; eps=.0001
    _ORIGINAL[obj.name]=obj.data
    obj.data=obj.data.copy(); obj.data.name='locator_ceiling_cutaway'
    bm=bmesh.new(); bm.from_mesh(obj.data)
    faces=[]
    for face in bm.faces:
        points=[obj.matrix_world@v.co for v in face.verts]
        if all(p.z>=height-eps and x0-eps<=p.x<=x1+eps and y0-eps<=p.y<=y1+eps for p in points): faces.append(face)
    count=len(faces)
    bmesh.ops.delete(bm,geom=faces,context='FACES_ONLY')
    bm.to_mesh(obj.data); bm.free(); obj.data.update()
    return [{'object':'fixtures','bounds_xz_three':[x0,-y1,x1,-y0],'min_y_three':height,
             'faces_hidden':count,'basis':'spec office footprint and wall height; ceiling faces only'}]
