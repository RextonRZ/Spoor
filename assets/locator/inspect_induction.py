"""Inspect source Line A joins and bag-opening cartons without changing or saving the hub."""
import sys,json,math
from pathlib import Path
sys.dont_write_bytecode=True
BASE=Path(__file__).resolve().parent; ROOT=BASE.parents[1]
sys.path.insert(0,str(ROOT/'assets/hub'))
import bpy,line_a_geom
spec=json.loads((ROOT/'assets/hub/hub_spec.json').read_text(encoding='utf8'))
la,mouths,induct,merges=line_a_geom.derive(spec.get('line_a'))

def components(obj):
    mesh=obj.data; adj=[[] for v in mesh.vertices]
    for e in mesh.edges:
        a,b=e.vertices; adj[a].append(b); adj[b].append(a)
    visited=set(); rows=[]
    vertex_faces={}
    for f in mesh.polygons:
        for i in f.vertices: vertex_faces.setdefault(i,[]).append(f)
    for start in range(len(mesh.vertices)):
        if start in visited: continue
        todo=[start]; visited.add(start); ids=[]
        while todo:
            i=todo.pop(); ids.append(i)
            for j in adj[i]:
                if j not in visited: visited.add(j); todo.append(j)
        points=[obj.matrix_world@mesh.vertices[i].co for i in ids]
        lo=[min(v[k] for v in points) for k in range(3)]; hi=[max(v[k] for v in points) for k in range(3)]
        fs={f.index:f for i in ids for f in vertex_faces.get(i,[])}
        mats=sorted({mesh.materials[f.material_index].name for f in fs.values()})
        rows.append({'ids':ids,'min':lo,'max':hi,'materials':mats,'vertex_count':len(ids),
                     'vertices':[list(v) for v in points] if len(points)<=8 else None})
    return rows

convs=components(bpy.context.scene.objects['conveyors'])
local=[r for r in convs if r['max'][0]>=4 and r['min'][0]<=23 and r['max'][1]>=8.5 and r['min'][1]<=13]
belts=[r for r in local if any('belt' in m for m in r['materials'])]
boxes=[]
for name in ('parcels_static_merged','clutter_procedural'):
    ob=bpy.context.scene.objects.get(name)
    if not ob: continue
    for r in components(ob):
        x,y,z=[(a+b)/2 for a,b in zip(r['min'],r['max'])]
        if 6.1<=x<=8.1 and 24<=y<=27 and .85<=z<=1.6:
            boxes.append({'object':name,**r})
report={'line_a':la,'mouths':mouths,'induct':induct,'merges':merges,'conveyor_components':local,'belt_components':belts,'bench2_props':boxes,
        'source_blend':bpy.data.filepath,'saved':False}
p=BASE/'out/induction_geometry_inspection.json'; p.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
print('BELTS '+json.dumps([{k:r[k] for k in ('min','max','materials','vertex_count')} for r in belts]))
print('BENCH2 '+json.dumps(boxes))
