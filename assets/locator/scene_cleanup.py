"""Hide unsupported loose bag-opening props in memory without changing fixtures or source files."""
_ORIGINAL={}


def restore(scene):
    import bpy
    for name,original in list(_ORIGINAL.items()):
        obj=scene.objects.get(name)
        if obj:
            temporary=obj.data; obj.data=original
            if temporary.users==0 and temporary.name.startswith('locator_supported_props'):
                bpy.data.meshes.remove(temporary)
    _ORIGINAL.clear()
    for obj in list(scene.objects):
        if obj.get('locator_temporary_geometry'):
            data=obj.data; bpy.data.objects.remove(obj,do_unlink=True)
            if data.users==0: bpy.data.meshes.remove(data)
        elif obj.get('locator_temporary_light'):
            data=obj.data; bpy.data.objects.remove(obj,do_unlink=True)
            if data.users==0: bpy.data.lights.remove(data)


def working_mesh(obj):
    if obj.name not in _ORIGINAL:
        _ORIGINAL[obj.name]=obj.data; obj.data=obj.data.copy(); obj.data.name='locator_supported_props_'+obj.name
    return obj.data


def clean(scene,spec):
    import bmesh
    benches=[b['rect_m'] for b in spec['fixtures']['benches'] if b['name'].startswith('bag-opening')]
    report=[]
    for name in ('parcels_static_merged','clutter_procedural'):
        obj=scene.objects.get(name)
        if not obj: continue
        mesh=obj.data; adjacency=[[] for _ in mesh.vertices]
        for edge in mesh.edges:
            a,b=edge.vertices; adjacency[a].append(b); adjacency[b].append(a)
        visited=set(); remove=[]; bounds=[]
        for first in range(len(mesh.vertices)):
            if first in visited: continue
            pending=[first]; visited.add(first); component=[]
            while pending:
                index=pending.pop(); component.append(index)
                for other in adjacency[index]:
                    if other not in visited: visited.add(other); pending.append(other)
            points=[obj.matrix_world@mesh.vertices[i].co for i in component]
            lo=[min(p[i] for p in points) for i in range(3)]; hi=[max(p[i] for p in points) for i in range(3)]
            x,y=(lo[0]+hi[0])/2,(lo[1]+hi[1])/2
            small=hi[0]-lo[0]<1.5 and hi[1]-lo[1]<1.5
            suspended=.6<lo[2] and hi[2]<1.7
            in_work_area=5.6<=x<=13 and 17<=y<=29
            supported=any(x0-.04<=x<=x1+.04 and y0-.04<=y<=y1+.04 for x0,y0,x1,y1 in benches)
            if small and suspended and in_work_area and not supported:
                remove.extend(component); bounds.append([lo,hi])
        if remove:
            _ORIGINAL[name]=obj.data; obj.data=mesh.copy(); obj.data.name='locator_supported_props_'+name
            bm=bmesh.new(); bm.from_mesh(obj.data); bm.verts.ensure_lookup_table()
            bmesh.ops.delete(bm,geom=[bm.verts[i] for i in remove],context='VERTS')
            bm.to_mesh(obj.data); bm.free(); obj.data.update()
            report.append({'object':name,'hidden_loose_islands':len(bounds),'bounds_blender':bounds,
                'reason':'loose props above floor without a supporting bag-opening bench; fixtures retained'})
    return report


def scanner_light(scene):
    import bpy
    from mathutils import Vector
    obj=scene.objects.get('scan_tunnel_DWS-01')
    emitter=[]
    for face in obj.data.polygons:
        material=obj.data.materials[face.material_index]
        if material and 'lightbar' in material.name.lower():
            emitter.extend(obj.matrix_world@obj.data.vertices[i].co for i in face.vertices)
    if not emitter: return []
    top=max(p.z for p in emitter); emitter=[p for p in emitter if p.z>=top-.12]
    center=sum(emitter,Vector())/len(emitter); center.z-=.03
    data=bpy.data.lights.new('locator_scanner_fill','AREA'); data.energy=70; data.shape='RECTANGLE'
    data.size=1.8; data.size_y=1.2; data.color=(1.0,.94,.88); data.use_shadow=True
    light=bpy.data.objects.new('locator_scanner_fill',data); scene.collection.objects.link(light)
    light.location=center; light['locator_temporary_light']=True
    return [{'basis':'actual scanner lightbar geometry','location':list(center),'energy_w':70}]
