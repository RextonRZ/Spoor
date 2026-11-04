import bpy, json, sys, struct, hashlib
from pathlib import Path
from mathutils import Vector
BASE=Path(__file__).resolve().parent
ROOT=BASE.parents[1]
s=bpy.context.scene
report={'blender_version':bpy.app.version_string,'engine':s.render.engine,'unit_scale':s.unit_settings.scale_length,'resolution':[s.render.resolution_x,s.render.resolution_y,s.render.resolution_percentage],'view_transform':s.view_settings.view_transform,'exposure':s.view_settings.exposure,'objects':[],'collections':[],'eevee_properties':[p.identifier for p in s.eevee.bl_rna.properties] if hasattr(s,'eevee') else [],'lights':[]}
for c in bpy.data.collections: report['collections'].append({'name':c.name,'hide_render':c.hide_render,'count':len(c.all_objects)})
for o in s.objects:
    if o.type=='LIGHT': report['lights'].append({'name':o.name,'type':o.data.type,'energy':o.data.energy,'shadow':o.data.use_shadow})
    if o.type not in {'MESH','FONT','CURVE','ARMATURE'}: continue
    cs=[o.matrix_world@Vector(c) for c in o.bound_box]
    report['objects'].append({'name':o.name,'type':o.type,'hidden':o.hide_render,'visible':o.visible_get(),'collections':[c.name for c in o.users_collection],'location':list(o.matrix_world.translation),'bbox':[[min(c[i] for c in cs) for i in range(3)],[max(c[i] for c in cs) for i in range(3)]],'vertices':len(o.data.vertices) if o.type=='MESH' else 0})
(BASE/'inspection.json').write_text(json.dumps(report,indent=2),encoding='utf8')
paths=[Path(bpy.data.filepath),ROOT/'assets/hub/hub_spec.json',ROOT/'frontend/public/hub.glb',ROOT/'frontend/scripts/export_hub_glb.py']
source={str(p.relative_to(ROOT)):{'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'size':p.stat().st_size,'mtime_ns':p.stat().st_mtime_ns} for p in paths}
(BASE/'source_fingerprints.json').write_text(json.dumps(source,indent=2),encoding='utf8')
print('INSPECT',json.dumps({k:report[k] for k in ['blender_version','engine','unit_scale','resolution','view_transform','exposure','collections','eevee_properties']}),flush=True)
