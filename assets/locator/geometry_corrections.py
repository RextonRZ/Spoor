"""Temporary locator corrections. No source writes or Blender save operators.

The hub owner can reuse induction_boxes() when rebuilding the permanent hub.
"""
import math


def components(obj):
    mesh=obj.data; adjacency=[[] for _ in mesh.vertices]
    for e in mesh.edges:
        a,b=e.vertices; adjacency[a].append(b); adjacency[b].append(a)
    seen=set(); rows=[]; vertex_faces={}
    for f in mesh.polygons:
        for i in f.vertices: vertex_faces.setdefault(i,[]).append(f)
    for start in range(len(mesh.vertices)):
        if start in seen: continue
        todo=[start]; seen.add(start); ids=[]
        while todo:
            i=todo.pop(); ids.append(i)
            for j in adjacency[i]:
                if j not in seen: seen.add(j); todo.append(j)
        pts=[obj.matrix_world@mesh.vertices[i].co for i in ids]
        lo=[min(p[k] for p in pts) for k in range(3)]; hi=[max(p[k] for p in pts) for k in range(3)]
        mats={mesh.materials[f.material_index].name for i in ids for f in vertex_faces.get(i,[])}
        rows.append({'ids':ids,'lo':lo,'hi':hi,'mats':mats})
    return rows


def induction_boxes(scene,spec):
    """Fill missing flat-run structure and small automatic-transfer gaps using measured source bounds."""
    from mathutils import Vector,Matrix
    import sys
    from pathlib import Path
    sys.dont_write_bytecode=True
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'hub'))
    import line_a_geom
    la,mouths,induct,merges=line_a_geom.derive(spec.get('line_a'))
    main=next(c for c in spec['machines']['conveyors'] if c['id']=='induction')
    x0,y=main['path'][0]; h=main['height']
    rows=components(scene.objects['conveyors'])
    flat=next(r for r in rows if 'belt_rubber' in r['mats'] and abs(r['lo'][0]-x0)<.01 and abs(r['hi'][2]-h)<.01)
    x1=flat['hi'][0]; width=flat['hi'][1]-flat['lo'][1]; result=[]
    def add(label,low,high,mat='painted_frame'):
        center=Vector([(a+b)/2 for a,b in zip(low,high)]); dims=Vector([b-a for a,b in zip(low,high)])
        result.append({'label':label,'matrix':Matrix.Translation(center)@Matrix.Diagonal((*dims,1)), 'material':mat})
    # The flat run was emitted before build_hub.py changed ax to the ramp start. Its rails and legs were omitted.
    add('flat induction south guide',[x0,y-width/2-.05,h-.14],[x1,y-width/2-.01,h+.04])
    spans=[(x0,x1)]
    for (sx,sy),(ex,ey) in induct:
        cut_width=la['induct_w']/abs((ey-sy)/math.hypot(ex-sx,ey-sy))
        opening=(ex-cut_width/2-.04,ex+cut_width/2+.04)
        spans=[(a,b) for lo,hi in spans for a,b in ((lo,min(hi,opening[0])),(max(lo,opening[1]),hi)) if b-a>.02]
        add('induct merge transfer plate',[ex-cut_width/2,y+width/2,h-.012],[ex+cut_width/2,ey,h],'galvanised_steel')
    for lo,hi in spans: add('flat induction north guide',[lo,y+width/2+.01,h-.14],[hi,y+width/2+.05,h+.04])
    n=max(1,int((x1-x0)/2))
    for k in range(n):
        x=x0+(x1-x0)*k/n
        for side in (-1,1):
            edge=y+side*(width/2-.03)
            add('flat induction support leg',[x-.04,edge-.03,0],[x+.04,edge+.03,h-.12],'galvanised_steel')
    # Feed-to-gravity-roller noses: join the 70 mm gap with a short sloped plate, keeping the operator aisle open.
    low_y,table_y=line_a_geom.table_ys(la); feed_edge=la['feed_y']-la['feed_half']
    for mouth in mouths:
        p0=Vector((mouth,table_y,la['table_top'][0]-.006)); p1=Vector((mouth,feed_edge,h-.006))
        delta=p1-p0; rot=delta.to_track_quat('Y','Z').to_matrix().to_4x4()
        result.append({'label':'feed to roller transfer plate','matrix':Matrix.Translation((p0+p1)/2)@rot@Matrix.Diagonal((la['table_w'],delta.length,.012,1)),'material':'galvanised_steel'})
    return result


def apply_induction(scene,spec):
    import bpy,bmesh
    from mathutils import Matrix
    convert=Matrix(((1,0,0,0),(0,0,1,0),(0,-1,0,0),(0,0,0,1)))
    result=[]
    for index,item in enumerate(induction_boxes(scene,spec)):
        mesh=bpy.data.meshes.new('locator_geometry_mesh'); bm=bmesh.new(); bmesh.ops.create_cube(bm,size=1); bm.to_mesh(mesh); bm.free()
        mat=bpy.data.materials.get(item['material']); mesh.materials.append(mat)
        obj=bpy.data.objects.new(f'locator_geometry_{index:02d}',mesh); scene.collection.objects.link(obj)
        obj.matrix_world=item['matrix']; obj['locator_temporary_geometry']=True
        m=convert@item['matrix']@convert.inverted()
        result.append({'label':item['label'],'matrix_three':[m[r][c] for c in range(4) for r in range(4)],
                       'material':item['material'],'color':'#a6afb3' if item['material']=='galvanised_steel' else '#9a9e9f'})
    return {'temporary_only':True,'source_assets_unchanged':True,'boxes':result,
            'reason':'Missing flat induction guides/legs and unbridged feed/induct transfer noses',
            'manual_operator_gap_retained':True}


def rectify_cartons(scene,spec):
    """Square crushed carton tops and separate overlapping cartons on their existing benches."""
    from mathutils import Vector
    import scene_cleanup
    obj=scene.objects['parcels_static_merged']; rows=components(obj)
    benches=[b for b in spec['fixtures']['benches'] if b['name'].startswith('bag-opening')]
    cartons=[]; props=[]
    for row in rows:
        lo,hi=row['lo'],row['hi']; cx,cy=(lo[0]+hi[0])/2,(lo[1]+hi[1])/2
        bench=next((b for b in benches if b['rect_m'][0]<cx<b['rect_m'][2] and b['rect_m'][1]<cy<b['rect_m'][3] and abs(lo[2]-b['height_m'])<.05),None)
        if not bench or len(row['ids'])<=4: continue
        row['bench']=bench; props.append(row)
        if row['mats']=={'cardboard'} and len(row['ids'])==8: cartons.append(row)
    scene_cleanup.working_mesh(obj); mesh=obj.data; edits={}; inverse=obj.matrix_world.inverted()
    def write(i,p):
        old=obj.matrix_world@mesh.vertices[i].co
        if (old-p).length<1e-7: return
        edits.setdefault(i,{'old':list(old)})['new']=list(p); mesh.vertices[i].co=inverse@p
    def overlap(a,b,pad=.025): return a[0]<b[2]+pad and b[0]<a[2]+pad and a[1]<b[3]+pad and b[1]<a[3]+pad
    occupied=[(p['lo'][0],p['lo'][1],p['hi'][0],p['hi'][1]) for p in props if p not in cartons]
    report=[]
    for row in sorted(cartons,key=lambda r:-(r['hi'][0]-r['lo'][0])*(r['hi'][1]-r['lo'][1])):
        lo,hi=row['lo'],row['hi']; bottom=[obj.matrix_world@mesh.vertices[i].co for i in row['ids'] if abs((obj.matrix_world@mesh.vertices[i].co).z-lo[2])<.005]
        assert len(bottom)==4
        # The intact bottom rectangle is the template for four vertical sides and a level top.
        for i in row['ids']:
            p=obj.matrix_world@mesh.vertices[i].co
            if p.z>lo[2]+.01:
                foot=min(bottom,key=lambda q:(q.x-p.x)**2+(q.y-p.y)**2)
                write(i,Vector((foot.x,foot.y,hi[2])))
        bounds=(lo[0],lo[1],hi[0],hi[1]); dx=dy=0
        if any(overlap(bounds,p) for p in occupied):
            a,b,c,d=row['bench']['rect_m']; candidates=[]
            for ix in range(33):
                for iy in range(59):
                    xx=a+.12+ix*.05; yy=b+.12+iy*.05
                    shiftx=xx-(lo[0]+hi[0])/2; shifty=yy-(lo[1]+hi[1])/2
                    rect=(lo[0]+shiftx,lo[1]+shifty,hi[0]+shiftx,hi[1]+shifty)
                    if rect[0]<a+.06 or rect[2]>c-.06 or rect[1]<b+.06 or rect[3]>d-.06: continue
                    if any(overlap(rect,p) for p in occupied): continue
                    candidates.append((shiftx**2+shifty**2,shiftx,shifty,rect))
            if not candidates: raise RuntimeError('No supported, non-overlapping carton placement on bag-opening bench')
            _,dx,dy,bounds=min(candidates)
        attached=list(row['ids'])
        for part in rows:
            if len(part['ids'])!=4 or abs(part['lo'][2]-hi[2])>.012: continue
            cx,cy=(part['lo'][0]+part['hi'][0])/2,(part['lo'][1]+part['hi'][1])/2
            if lo[0]-.005<=cx<=hi[0]+.005 and lo[1]-.005<=cy<=hi[1]+.005: attached.extend(part['ids'])
        for i in attached:
            p=obj.matrix_world@mesh.vertices[i].co; write(i,p+Vector((dx,dy,0)))
        occupied.append(bounds)
        report.append({'original_bounds':[lo,hi],'translation_blender':[dx,dy,0],'rectangular_top_z':hi[2],'bench':row['bench']['name']})
    mesh.update()
    convert=lambda p:[p[0],p[2],-p[1]]
    return {'temporary_only':True,'source_assets_unchanged':True,'boxes':[],
            'cartons':report,'vertex_edits':[{'object':obj.name,'old_three':convert(e['old']),'new_three':convert(e['new'])} for e in edits.values()],
            'reason':'Square damaged carton tops and separate overlapping cartons; keep labels/tape attached and props on the bench'}
