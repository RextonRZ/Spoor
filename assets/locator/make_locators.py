"""Read-only hub locator renderer. Never saves a .blend or writes outside assets/locator.

From the project root:
  blender -b --factory-startup assets/hub/build/hub_lineAb_dressed_lit.blend \
    -P assets/locator/make_locators.py -- --zones Z11 --out assets/locator/out
Use --zones all only after the Z11 preview is approved. Pillow runs in system Python.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import struct
import subprocess
import sys
import time

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[1]
sys.dont_write_bytecode=True
sys.path.insert(0,str(BASE))
SPEC_PATH = ROOT / 'assets/hub/hub_spec.json'
GLB_PATH = ROOT / 'frontend/public/hub.glb'
HIDE_RE = re.compile(r'^(roof|ceiling|highbay_fixtures|mounted_fluorescent|structure$|led_rows$)', re.I)
PERSON_RE = re.compile(r'^(worker_|Bip01|mixamo|flow_|[fm]\d{3}_)', re.I)
WIDTH, HEIGHT = 1600, 900


def safe_path(path):
    path = Path(path).resolve()
    if not path.is_relative_to(BASE):
        raise ValueError(f'Output must stay inside {BASE}: {path}')
    return path


def write_json(path, data):
    path = safe_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=True) + '\n', encoding='utf8')


def polygons(zone):
    value = zone['polygon_m']
    return list(value.values()) if isinstance(value, dict) else [value]


def floor_z(zone):
    return -1.2 if zone['kind'] == 'yard' else 0.0


def centroid(poly):
    a = cx = cy = 0.0
    for p, q in zip(poly, poly[1:] + poly[:1]):
        cross = p[0] * q[1] - q[0] * p[1]
        a += cross
        cx += (p[0] + q[0]) * cross
        cy += (p[1] + q[1]) * cross
    return cx / (3 * a), cy / (3 * a), abs(a) / 2


def zone_center(zone):
    parts = [centroid(p) for p in polygons(zone)]
    area = sum(p[2] for p in parts)
    return [sum(p[i] * p[2] for p in parts) / area for i in (0, 1)] + [floor_z(zone)]


def inside(x, y, poly):
    hit = False
    for (ax, ay), (bx, by) in zip(poly, poly[1:] + poly[:1]):
        if (ay > y) != (by > y) and x < (bx - ax) * (y - ay) / (by - ay) + ax:
            hit = not hit
    return hit


def three(p):
    return [float(p[0]), float(p[2]), -float(p[1])]


def selected_zones(spec, selector):
    ids = {s.strip() for s in selector.split(',')}
    for scan in spec['scan_points']:
        if scan['id'] in ids:
            ids.add(scan['zone'])
    ids = {re.sub(r'^LOC-(Z\d+).*$', r'\1', x) for x in ids}
    zones = spec['zones'] if 'all' in ids else [z for z in spec['zones'] if z['id'] in ids]
    if not zones:
        raise ValueError(f'Unknown zone selector: {selector}')
    return zones


def fingerprint(path):
    return {'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'size': path.stat().st_size}


def driver(args, bpy):
    source = Path(bpy.data.filepath).resolve()
    if not source.is_file():
        raise ValueError('Open the supplied hub .blend before executing this script.')
    out = safe_path(args.out)
    raw = safe_path(out / '_raw')
    raw.mkdir(parents=True, exist_ok=True)
    spec = json.loads(SPEC_PATH.read_text(encoding='utf8'))
    zones = selected_zones(spec, args.zones)
    views = args.views.split(',')
    if any(v not in {'eye','map'} for v in views):
        raise ValueError('Views must be eye and/or map.')
    inputs = [source, SPEC_PATH, GLB_PATH]
    before = {str(p.relative_to(ROOT)): fingerprint(p) for p in inputs}
    blender = bpy.app.binary_path
    bpy.ops.wm.read_factory_settings(use_empty=True)
    python = args.python or os.environ.get('LOCATOR_PYTHON', 'C:/Python313/python.exe')
    started = time.monotonic()
    manifest_path = out / 'locators.json'
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    previous_report=out/'run_report.json'
    previous=json.loads(previous_report.read_text()) if previous_report.exists() else {}
    timings = list(previous.get('render_timings',[])) if args.resume else []
    for zone in zones:
        old = manifest.get(zone['id'], {})
        combined = {k:old[k] for k in ('eye','map') if k in old}
        for view in views:
            if args.resume and view in combined and (out/combined[view]['image']).is_file():
                print(f'REUSE {zone["id"]}_{view}',flush=True)
                continue
            samples = args.samples if view == 'eye' else args.map_samples
            completed = False
            for attempt in range(3):
                stem = f'{zone["id"]}_{view}'
                log_path = raw / f'{stem}_{samples}s.log'
                cmd = [blender, '-b', '--factory-startup', str(source), '-t', '4', '--python-exit-code', '1', '-P', str(BASE / 'make_locators.py'), '--',
                       '--render-worker', '--view', view, '--zones', zone['id'], '--out', str(out), '--samples', str(samples)]
                env = os.environ.copy()
                runtime = safe_path(BASE / 'runtime'); runtime.mkdir(exist_ok=True)
                env.update({'OMP_NUM_THREADS':'4','OPENBLAS_NUM_THREADS':'4','PYTHONDONTWRITEBYTECODE':'1','TMP':str(runtime),'TEMP':str(runtime)})
                begin = time.monotonic()
                print(f'LOCATOR {stem}: EEVEE {samples} samples, timeout 120s', flush=True)
                with log_path.open('w', encoding='utf8') as log:
                    proc = subprocess.Popen(cmd, cwd=str(ROOT), stdout=log, stderr=subprocess.STDOUT, env=env,
                        creationflags=getattr(subprocess,'BELOW_NORMAL_PRIORITY_CLASS',0)|getattr(subprocess,'CREATE_NO_WINDOW',0))
                    try:
                        code=proc.wait(timeout=120)
                    except subprocess.TimeoutExpired:
                        proc.kill(); proc.wait(); code=-1
                elapsed=time.monotonic()-begin
                timings.append({'zone':zone['id'],'view':view,'samples':samples,'seconds':round(elapsed,2),'exit_code':code})
                write_json(out/'render_timings.json',timings)
                if code==0:
                    completed=True; break
                if code!=-1:
                    raise RuntimeError(log_path.read_text(encoding='utf8',errors='replace')[-6000:])
                samples=max(2,samples//2)
                print(f'LOCATOR {stem}: exceeded 120s, retrying at {samples} samples',flush=True)
            if not completed:
                raise RuntimeError(f'Render did not finish after lower-sample retries: {stem}')
            subprocess.run([python,'-B',str(BASE/'postprocess.py'),'--out',str(out),'--zone',zone['id'],'--view',view],
                cwd=str(ROOT),check=True,env=env,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            entry=json.loads((raw/f'{stem}.json').read_text())
            combined[view]=entry
        reference=combined.get('map',combined.get('eye'))
        manifest[zone['id']]={'name':zone['name'],'label':reference['label'],'zone_alias':reference['zone_alias'],
            'image':f'{zone["id"]}_eye.png','open_in_3d':'map',
            'cams_covering':reference['cams_covering'],'coverage_note':reference.get('coverage_note'),
            'zone_polygon_three':reference['zone_polygon_three'],
            'zone_polygon_parts_three':reference['zone_polygon_parts_three'],**combined}
        write_json(manifest_path,manifest)
    after={str(p.relative_to(ROOT)):fingerprint(p) for p in inputs}
    write_json(out/'run_report.json',{'input_files_unchanged':before==after,'inputs':before,
        'render_timings':timings,'total_seconds':round(time.monotonic()-started,2),
        'engine':'EEVEE','resolution':[WIDTH,HEIGHT],'threads':4,'priority':'below normal',
        'timeout_seconds_per_image':120,'blends_saved':0,'zones_requested':args.zones,'views':views})
    if before!=after:
        raise RuntimeError('An input file changed during rendering. Inspect run_report.json.')
    print(f'LOCATORS_READY {manifest_path}',flush=True)


def entrance_and_walkway(spec,zone):
    """Derive a doorway from the store rack gap, or a zone boundary beside a walkway."""
    if zone['id']=='Z11':
        scan=next(s for s in spec['scan_points'] if s['id']=='SP-STORE-IN')
        racks=spec['fixtures']['racks']
        front=min(r['rect_m'][1] for r in racks)
        spans=sorted((r['rect_m'][0],r['rect_m'][2]) for r in racks if abs(r['rect_m'][1]-front)<.01)
        gaps=[(a[1],b[0]) for a,b in zip(spans,spans[1:]) if b[0]>a[1]]
        left,right=min(gaps,key=lambda g:abs((g[0]+g[1])/2-scan['position_m'][0]))
        entrance=[(left+right)/2,front,floor_z(zone)]
        evidence={'basis':'gap between hub_spec.fixtures.racks beside SP-STORE-IN','doorway_width_m':right-left,
                  'doorway_floor_blender':entrance,'scan_point':scan['id'],'front_normal_blender':[0,-1,0]}
    else:
        center=zone_center(zone)
        candidates=[]
        for poly in polygons(zone):
            for a,b in zip(poly,poly[1:]+poly[:1]):
                for k in range(9):
                    t=k/8; x=a[0]*(1-t)+b[0]*t; y=a[1]*(1-t)+b[1]*t
                    for w in spec['circulation']['walkways']:
                        x0,y0,x1,y1=w['rect_m']; wx=min(x1,max(x0,x)); wy=min(y1,max(y0,y))
                        candidates.append((math.hypot(x-wx,y-wy),[x,y,floor_z(zone)]))
        entrance=min(candidates,key=lambda v:v[0])[1]
        evidence={'basis':'zone polygon boundary nearest a declared walkway','doorway_floor_blender':entrance}
    return entrance,evidence


def worker(args, bpy):
    from mathutils import Vector, Matrix, Quaternion
    from bpy_extras.object_utils import world_to_camera_view
    stage_start=time.monotonic()
    scene = bpy.context.scene
    import cutaway
    cutaway.restore(scene)
    import scene_cleanup
    scene_cleanup.restore(scene)
    spec = json.loads(SPEC_PATH.read_text(encoding='utf8'))
    zone = selected_zones(spec, args.zones)[0]
    stem=f'{zone["id"]}_{args.view}'
    entrance,entrance_evidence=entrance_and_walkway(spec,zone)
    out = safe_path(args.out)
    raw = out / '_raw'
    raw.mkdir(parents=True, exist_ok=True)
    scene.frame_set(1)
    hidden = []
    for obj in scene.objects:
        collections = {c.name for c in obj.users_collection}
        hide = obj.hide_render or not obj.visible_get() or (args.view=='map' and bool(HIDE_RE.match(obj.name))) or bool(PERSON_RE.match(obj.name))
        hide |= bool(collections & {'People', 'PeopleTemplates', 'Flow'}) or obj.type == 'ARMATURE'
        hide |= 'parcel' in obj.name.lower() and obj.animation_data is not None
        if hide:
            obj.hide_render = True
            obj.hide_viewport = True
            hidden.append(obj.name)
        if obj.animation_data:
            obj.animation_data_clear()
    # The current dressed hub contains the permanent zone repairs. Legacy corrections are opt-in only.
    source_fixed=os.environ.get('LOCATOR_SOURCE_FIXED','1')!='0'
    clutter_cleanup=[] if source_fixed else scene_cleanup.clean(scene,spec)
    corrective_geometry={'source_repaired':True,'temporary_geometry_added':False} if source_fixed else {}
    if not source_fixed:
        import geometry_corrections
        if zone['id']=='Z03': corrective_geometry=geometry_corrections.apply_induction(scene,spec)
        elif zone['id']=='Z02': corrective_geometry=geometry_corrections.rectify_cartons(scene,spec)
    ceiling_cutouts=cutaway.office_ceiling(scene,spec,zone) if args.view=='map' else []
    lights=[o for o in scene.objects if o.type=='LIGHT']
    near_lights=sorted((o for o in lights if o.data.energy>0 and o.data.type!='SUN'),
        key=lambda o:(o.location.x-entrance[0])**2+(o.location.y-entrance[1])**2)[:4]
    for obj in lights:
        obj.data.use_shadow = obj.data.type=='SUN' or (args.view=='eye' and obj in near_lights)
        if obj.data.type=='SUN' and (args.view=='map' or zone['kind']=='yard'):
            obj.data.energy=4.0 if args.view=='eye' and zone['kind']=='yard' else 1.6; obj.data.angle=math.radians(18)
    scene.render.engine = 'BLENDER_EEVEE'
    scene.render.resolution_x, scene.render.resolution_y = WIDTH, HEIGHT
    scene.render.resolution_percentage = 50 if getattr(args,'preview',False) else 100
    scene.render.pixel_aspect_x = scene.render.pixel_aspect_y = 1
    scene.render.threads_mode = 'FIXED'
    scene.render.threads = 4
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGBA'
    scene.render.image_settings.color_depth = '8'
    scene.render.film_transparent = False
    scene.render.use_file_extension = True
    scene.render.use_compositing = False
    scene.render.use_sequencer = False
    scene.render.use_persistent_data = True
    scene.render.use_simplify = True
    scene.render.simplify_subdivision_render = 0
    scene.render.simplify_child_particles_render = 0
    scene.eevee.taa_render_samples = args.samples
    scene.eevee.use_raytracing = False
    scene.eevee.use_fast_gi = True
    scene.eevee.fast_gi_quality = 0.5 if args.view=='eye' else 0.25
    scene.eevee.fast_gi_ray_count = 4 if args.view=='eye' else 2
    scene.eevee.shadow_resolution_scale = 0.75 if args.view=='eye' else 0.5
    scene.eevee.shadow_ray_count = 2 if args.view=='eye' else 1
    scene.eevee.shadow_step_count = 4
    scene.view_settings.view_transform = 'AgX'
    scene.view_settings.look = 'AgX - Medium High Contrast'
    scene.view_settings.exposure = 0
    scene.view_settings.gamma = 1
    data = bpy.data.cameras.new('locator_temporary')
    camera = bpy.data.objects.new('locator_temporary', data)
    scene.collection.objects.link(camera)
    scene.camera = camera
    data.type = 'PERSP'
    data.lens = 27 if args.view=='eye' else 38
    data.sensor_width = 36
    data.sensor_fit = 'HORIZONTAL'
    data.clip_start, data.clip_end = 0.1, 500
    data.shift_x = data.shift_y = 0
    data.dof.use_dof = False
    floor_center=Vector(zone_center(zone))
    all_xy=[p for poly in polygons(zone) for p in poly]
    xmin,xmax=min(p[0] for p in all_xy),max(p[0] for p in all_xy)
    ymin,ymax=min(p[1] for p in all_xy),max(p[1] for p in all_xy)
    depsgraph=bpy.context.evaluated_depsgraph_get()
    tanh=18/data.lens; tanv=tanh*HEIGHT/WIDTH
    candidates=[]
    if args.mask_existing or getattr(args,'reuse_cameras',False):
        saved=json.loads((out/'locators.json').read_text())[zone['id']][args.view]
        center=Vector(saved['camera']['target'])
        camera.location=Vector(saved['camera']['location'])
        data.lens=saved['camera']['lens']
        tanh=18/data.lens; tanv=tanh*HEIGHT/WIDTH
        entrance_evidence=saved['entrance']
        candidates=saved['proof']['camera_candidates']
        best={'view':args.view,'reused_camera':True}
    elif args.view=='eye':
        from camera_planning import choose_eye
        def cast(origin,direction,distance):
            return scene.ray_cast(depsgraph,origin,direction,distance=distance)
        location,center,entrance_evidence,best=choose_eye(spec,zone,cast,inside,polygons,entrance,entrance_evidence)
        camera.location=location
        data.lens=entrance_evidence.get('lens_mm',data.lens)
        tanh=18/data.lens; tanv=tanh*HEIGHT/WIDTH
    else:
        center=floor_center
        padding=1.0
        frame_points=[Vector((x,y,z)) for x in (xmin-padding,xmax+padding)
            for y in (ymin-padding,ymax+padding) for z in (center.z,center.z+3.1)]
        samples=[]
        for ix in range(28):
            for iy in range(18):
                x=xmin+(ix+.5)*(xmax-xmin)/28; y=ymin+(iy+.5)*(ymax-ymin)/18
                if any(inside(x,y,p) for p in polygons(zone)): samples.append(Vector((x,y,center.z+.035)))
        for elevation in (40,44):
            for azimuth in (30,60,120,150,210,240,270,285,300,315,330):
                el,az=math.radians(elevation),math.radians(azimuth)
                away=Vector((math.cos(az)*math.cos(el),math.sin(az)*math.cos(el),math.sin(el)))
                rotation=(-away).to_track_quat('-Z','Y'); inv=rotation.inverted(); distance=1
                for point in frame_points:
                    v=inv@(point-center)
                    distance=max(distance,v.z+abs(v.x)/(tanh*.96),v.z+abs(v.y)/(tanv*.96))
                location=center+away*distance
                visible=wall_blocks=0
                for point in samples:
                    direction=point-location
                    hit,pos,normal,face,obj,matrix=scene.ray_cast(depsgraph,location,direction.normalized(),distance=direction.length-.02)
                    if not hit: visible+=1
                    elif obj.name.startswith('wall_'): wall_blocks+=1
                exterior=0
                for sx in range(16):
                    for sy in range(9):
                        ray=rotation@Vector((((sx+.5)/16*2-1)*tanh,((sy+.5)/9*2-1)*tanv,-1)).normalized()
                        hit,pos,normal,face,obj,matrix=scene.ray_cast(depsgraph,location,ray,distance=250)
                        if not hit: exterior+=1
                        elif obj.name in {'ground','yard_west','yard_north'}:
                            if zone['kind']!='yard' or not any(inside(pos.x,pos.y,p) for p in polygons(zone)): exterior+=1
                candidates.append({'azimuth_deg':azimuth,'elevation_deg':elevation,
                    'floor_visible_fraction':visible/len(samples),'wall_block_fraction':wall_blocks/len(samples),
                    'exterior_view_fraction':exterior/144,'location':list(location),'distance':distance})
        candidates.sort(key=lambda c:(c['exterior_view_fraction']>.015,
            -c['floor_visible_fraction'] if c['exterior_view_fraction']<=.015 else c['exterior_view_fraction'],
            c['wall_block_fraction']))
        if zone['kind']=='yard':
            candidates.sort(key=lambda c:(-c['floor_visible_fraction'],c['exterior_view_fraction']))
        best=candidates[0]; camera.location=Vector(best['location'])
    temporary_lights=scene_cleanup.scanner_light(scene) if args.view=='eye' and zone['id']=='Z04' else []
    camera.rotation_euler=(center-camera.location).to_track_quat('-Z','Y').to_euler()
    bpy.context.view_layer.update()
    if args.preflight:
        return {'zone':zone['id'],'camera':{'location':list(camera.location),'target':list(center),'lens':data.lens},'entrance':entrance_evidence}
    print('CAMERA_PLANNED_SECONDS',round(time.monotonic()-stage_start,2),flush=True)
    def project(point):
        p=world_to_camera_view(scene,camera,Vector(point))
        return [p.x*WIDTH,(1-p.y)*HEIGHT]
    floor_polygons=[[[x,y,floor_center.z+0.035] for x,y in p] for p in polygons(zone)]
    # Floor tint, alpha blended in Pillow against the original scene. Record an occlusion-aware
    # triangle mesh mask using camera rays, so racks and cages remain naturally in front.
    # 28x18 floor cells above choose the view; the final 400x225 mask uses the same ray tests.
    mask_w,mask_h=(200,112) if args.view=='eye' else (400,225)
    if getattr(args,'preview',False): mask_w,mask_h=1,1
    frame=data.view_frame(scene=scene)
    bl,tl,tr,br=frame[2],frame[3],frame[0],frame[1]
    zone_mask=bytearray(mask_w*mask_h); surface_mask=bytearray(mask_w*mask_h)
    camrot=camera.matrix_world.to_quaternion()
    for yy in range(mask_h):
        for xx in range(mask_w):
            u,v=(xx+.5)/mask_w,(yy+.5)/mask_h
            local=tl.lerp(tr,u).lerp(bl.lerp(br,u),v)
            ray=camrot@local.normalized()
            if ray.z>=0: continue
            hit,pos,normal,face,obj,matrix=scene.ray_cast(depsgraph,camera.location,ray,distance=250)
            if not hit: continue
            # Original physical floor surfaces only; props and fixtures are kept out of the colour match.
            indoor=obj.name=='floor_slab' or (obj.name.startswith('floor_') and abs(pos.z)<.05)
            yard=obj.name in {'ground','yard_west','yard_north'}
            if indoor: surface_mask[yy*mask_w+xx]=255
            elif yard: surface_mask[yy*mask_w+xx]=128
            if (indoor or yard) and abs(pos.z-floor_center.z)<.08 and any(inside(pos.x,pos.y,p) for p in polygons(zone)):
                zone_mask[yy*mask_w+xx]=255
    pgm=f'P5\n{mask_w} {mask_h}\n255\n'.encode()
    (raw/f'{stem}_surface.pgm').write_bytes(pgm+surface_mask)
    if args.view=='map': (raw/f'{stem}_floor.pgm').write_bytes(pgm+zone_mask)
    print('FLOOR_MASK_SECONDS',round(time.monotonic()-stage_start,2),flush=True)
    if args.mask_existing:
        return {'zone':zone['id'],'view':args.view,'mask_only':True}
    # Camera coverage uses declared duty areas, never a generic frustum assertion.
    covering=[]
    coverage=[]
    for cam in spec['cameras']:
        duty=cam.get('duty_area_m',{})
        if not duty: continue
        x0,x1=duty['x']; y0,y1=duty['y']
        overlap=any(inside(x0+(i+.5)*(x1-x0)/12,y0+(j+.5)*(y1-y0)/12,p)
                    for p in polygons(zone) for i in range(12) for j in range(12))
        if overlap:
            covering.append(cam['id'])
            coverage.append({'id':cam['id'],'position_blender':cam['position_m']+[cam['height_m']],
                'screen_xy':project(cam['position_m']+[cam['height_m']]),'basis':'declared duty area overlaps zone',
                'scope':'entrance only; BLIND_NW has no coverage' if zone['id']=='Z11' and cam['id']=='CAM_19' else 'partial zone coverage'})
    # glTF exporter proof: transformed world origins of identifiable nearby static fixtures.
    with GLB_PATH.open('rb') as f:
        f.read(12); n,t=struct.unpack('<II',f.read(8)); gltf=json.loads(f.read(n))
    nodes=gltf['nodes']; parents={ch:i for i,node in enumerate(nodes) for ch in node.get('children',[])}
    def world(i):
        node=nodes[i]
        if 'matrix' in node:
            values=node['matrix']; m=Matrix([[values[c*4+r] for c in range(4)] for r in range(4)])
        else:
            q=node.get('rotation',[0,0,0,1]); m=Matrix.LocRotScale(Vector(node.get('translation',[0,0,0])),
                Quaternion((q[3],q[0],q[1],q[2])),Vector(node.get('scale',[1,1,1])))
        return world(parents[i])@m if i in parents else m
    anchors=[]
    anchor_names=['cage_empty_00','cage_empty_05','cage_empty_12','steel_frame_shelves_01.001','steel_frame_shelves_01.002']
    for name in anchor_names:
        obj=bpy.data.objects.get(name)
        match=next((i for i,n in enumerate(nodes) if n.get('extras',{}).get('spoor_id',n.get('name'))==name),None)
        if obj is not None and match is not None:
            expected=Vector(three(obj.matrix_world.translation)); actual=world(match).translation
            anchors.append({'name':name,'blender_world':list(obj.matrix_world.translation),'three_expected':list(expected),
                'glb_world':list(actual),'error_metres':(expected-actual).length,'blender_pixel':project(obj.matrix_world.translation)})
    scan=next((s for s in spec['scan_points'] if s['id']=='SP-STORE-IN'),None) if zone['id']=='Z11' else None
    polygon_three=[[three(p) for p in poly] for poly in floor_polygons]
    entry={'name':zone['name'],'label':'Exception store' if zone['id']=='Z11' else zone['name'].replace('\u2013','-').replace('\u2014','-'),
        'view':args.view,'image':f'{stem}.png','entrance':entrance_evidence,'camera':{'location':list(camera.location),'rotation':list(camera.rotation_euler),
            'rotation_units':'radians, XYZ Euler','lens':data.lens,'sensor_width':data.sensor_width,'sensor_fit':'HORIZONTAL',
            'target':list(center),'resolution':[WIDTH,HEIGHT]},
        'three_camera':{'position':three(camera.location),'target':three(center),
            'fov_deg':math.degrees(2*math.atan(tanv))},
        'zone_polygon_three':polygon_three[0] if len(polygon_three)==1 else polygon_three,
        'zone_polygon_parts_three':polygon_three,
        'cams_covering':covering,'coverage_details':coverage,
        'zone_alias':f'LOC-{zone["id"]}-EXCEPTION' if zone['id']=='Z11' else f'LOC-{zone["id"]}',
        'floor_highlight':{'enabled':args.view=='map','color':'#5558EE','opacity':0.35,'edge_color':'#ADAEFF','edge_width_px':2.5,'height_above_floor_m':0.035},
        'render_profile':{'hidden_name_regex':HIDE_RE.pattern if args.view=='map' else r'(?!)','hidden_objects':hidden,'ceiling_cutouts':ceiling_cutouts,'clutter_cleanup':clutter_cleanup,'geometry_corrections':corrective_geometry,'temporary_lights':temporary_lights,'samples':args.samples,'engine':'EEVEE',
            'people_hidden':True,'moving_parcels_hidden':True,'static_fixtures_retained':True},
        'compass':{'north_blender':[0,1,0],'basis':spec['meta']['frame'],
            'screen_vector':[project(center+Vector((0,1,0)))[i]-project(center)[i] for i in (0,1)]},
        'proof':{'export_script':'frontend/scripts/export_hub_glb.py','export_yup':True,'unit_scale':scene.unit_settings.scale_length,
            'coordinate_mapping':'Blender (x,y,z) -> glTF (x,z,-y), metres','anchors':anchors,
            'polygon_pixels_blender':[[project(p) for p in poly] for poly in floor_polygons],
            'camera_candidates':candidates,'source_blend':str(Path(bpy.data.filepath).relative_to(ROOT)),
            'glb':str(GLB_PATH.relative_to(ROOT))}}
    if scan:
        entry['scan_point']={'id':scan['id'],'position_three':three(scan['position_m']),'screen_xy':project(scan['position_m'])}
        entry['coverage_note']='CAM 19 watches the entrance. BLIND_NW behind the racks has no coverage.'
    if args.view=='map' and spec.get('blind_corner',{}).get('zone')==zone['id']:
        blind=[[x,y,floor_center.z+.04] for x,y in spec['blind_corner']['polygon']]
        entry['blind_corner']={'id':spec['blind_corner']['id'],'polygon_three':[three(p) for p in blind],
            'screen_polygon':[project(p) for p in blind],'coverage':'none'}
    if zone['id']=='Z11':
        entry['proof']['existing_glb_limitation']='The existing frontend/public/hub.glb predates this store dressing: store_header and sign_stor_board are absent, and shelf contents differ. Camera alignment is verified using the zone polygon and three cage origins. Source assets remain unchanged.'
    write_json(raw/f'{stem}.json',entry)
    scene.render.filepath=str(raw/f'{stem}.png')
    print('LOCATOR_CAMERA '+json.dumps(best),flush=True)
    render_start=time.monotonic()
    bpy.ops.render.render(write_still=True)
    print('RENDER_SECONDS',round(time.monotonic()-render_start,2),flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--zones',default='Z11')
    parser.add_argument('--out',default=str(BASE/'out'))
    parser.add_argument('--samples',type=int,default=32)
    parser.add_argument('--map-samples',type=int,default=16)
    parser.add_argument('--views',default='eye,map')
    parser.add_argument('--view',choices=['eye','map'],default='map')
    parser.add_argument('--python')
    parser.add_argument('--render-worker',action='store_true')
    parser.add_argument('--resume',action='store_true')
    parser.add_argument('--batch-worker',action='store_true')
    parser.add_argument('--preflight',action='store_true')
    parser.add_argument('--preview',action='store_true')
    parser.add_argument('--mask-existing',action='store_true')
    parser.add_argument('--reuse-cameras',action='store_true')
    argv=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else sys.argv[1:]
    args=parser.parse_args(argv)
    import bpy
    if args.batch_worker:
        import batch_runner
        batch_runner.worker(args,bpy,sys.modules[__name__])
    elif args.preflight:
        spec=json.loads(SPEC_PATH.read_text(encoding='utf8'))
        planned=[]; errors=[]
        for z in selected_zones(spec,args.zones):
            args.zones=z['id']; args.view='eye'
            try:
                planned.append(worker(args,bpy)); print('PLANNED',z['id'],flush=True)
            except Exception as error:
                errors.append({'zone':z['id'],'error':str(error)}); print('PLAN_ERROR',z['id'],str(error),flush=True)
        write_json(Path(args.out)/'camera_plan.json',{'planned':planned,'errors':errors})
    elif args.render_worker or args.mask_existing: worker(args,bpy)
    else:
        import batch_runner
        batch_runner.run(args,bpy,sys.modules[__name__])

if __name__=='__main__':
    main()
