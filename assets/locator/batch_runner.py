"""Single low-priority Blender worker with per-image checkpoints and an external watchdog."""
import hashlib,json,os,subprocess,time
from pathlib import Path


def run(args,bpy,m):
    source=Path(bpy.data.filepath).resolve(); out=m.safe_path(args.out); raw=out/'_raw'; raw.mkdir(parents=True,exist_ok=True)
    spec=json.loads(m.SPEC_PATH.read_text(encoding='utf8')); zones=m.selected_zones(spec,args.zones); views=args.views.split(',')
    if any(v not in {'eye','map'} for v in views): raise ValueError('Unknown view')
    manifest_path=out/'locators.json'; manifest=json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    jobs=[]; reused=[]
    for z in zones:
        for view in views:
            existing=manifest.get(z['id'],{}).get(view)
            if args.resume and existing and (out/existing['image']).exists(): reused.append(f'{z["id"]}_{view}')
            else: jobs.append({'zone':z['id'],'view':view,'samples':args.samples if view=='eye' else args.map_samples,'attempt':0,'reuse_camera':getattr(args,'reuse_cameras',False)})
    inputs=[source,m.SPEC_PATH,m.GLB_PATH]; before={str(p.relative_to(m.ROOT)):m.fingerprint(p) for p in inputs}
    old_report=out/'run_report.json'; previous=json.loads(old_report.read_text()) if old_report.exists() else {}
    journal=raw/'batch_timings.json'
    history=json.loads(journal.read_text()) if journal.exists() else []
    merged=[]
    for record in previous.get('render_timings',[])+history:
        if record not in merged: merged.append(record)
    previous['render_timings']=merged
    m.write_json(raw/'batch_timings.json',[])
    m.write_json(raw/'batch_jobs.json',jobs)
    m.write_json(raw/'batch_state.json',{'status':'starting','started':time.time()})
    python=args.python or os.environ.get('LOCATOR_PYTHON','C:/Python313/python.exe')
    blender=bpy.app.binary_path; bpy.ops.wm.read_factory_settings(use_empty=True)
    start=time.monotonic(); total=len(jobs); timeout_records=[]
    runtime=m.safe_path(m.BASE/'runtime'); runtime.mkdir(exist_ok=True)
    env=os.environ.copy(); env.update({'OMP_NUM_THREADS':'4','OPENBLAS_NUM_THREADS':'4','PYTHONDONTWRITEBYTECODE':'1','TMP':str(runtime),'TEMP':str(runtime),'LOCATOR_PYTHON':python})
    last_message=None
    while jobs:
        m.write_json(raw/'batch_jobs.json',jobs)
        m.write_json(raw/'batch_state.json',{'status':'starting','started':time.time()})
        cmd=[blender,'-b','--factory-startup',str(source),'-t','4','--python-exit-code','1','-P',str(m.BASE/'make_locators.py'),'--','--batch-worker','--out',str(out)]
        with (raw/'batch_worker.log').open('a',encoding='utf8') as log:
            proc=subprocess.Popen(cmd,cwd=str(m.ROOT),stdout=log,stderr=subprocess.STDOUT,env=env,
                creationflags=getattr(subprocess,'BELOW_NORMAL_PRIORITY_CLASS',0)|getattr(subprocess,'CREATE_NO_WINDOW',0))
            timed_out=None
            while proc.poll() is None:
                try: state=json.loads((raw/'batch_state.json').read_text())
                except (json.JSONDecodeError,OSError): time.sleep(.5); continue
                message=(state.get('status'),state.get('zone'),state.get('view'))
                if message!=last_message:
                    print('BATCH_STATE '+json.dumps(state),flush=True); last_message=message
                if time.time()-state.get('started',time.time())>120 and state.get('status') in {'running','starting'}:
                    timed_out=state; proc.kill(); proc.wait(); break
                time.sleep(.5)
            code=proc.wait()
        completed={(r['zone'],r['view']) for r in json.loads((raw/'batch_timings.json').read_text()) if r['exit_code']==0}
        jobs=[j for j in jobs if (j['zone'],j['view']) not in completed]
        if timed_out:
            if not jobs: break
            job=next((j for j in jobs if j['zone']==timed_out.get('zone') and j['view']==timed_out.get('view')),jobs[0])
            timeout_records.append({'zone':job['zone'],'view':job['view'],'samples':job['samples'],'seconds':120,'exit_code':-1})
            job['attempt']+=1; job['samples']=max(4,job['samples']//2)
            if job['attempt']>2: raise RuntimeError(f'Image timed out after lower-sample retries: {job}')
            print(f'RETRY {job["zone"]}_{job["view"]} at {job["samples"]} samples',flush=True)
        elif code!=0:
            raise RuntimeError((raw/'batch_worker.log').read_text(encoding='utf8',errors='replace')[-7000:])
        elif jobs:
            raise RuntimeError('Batch worker exited without completing its remaining jobs')
    after={str(p.relative_to(m.ROOT)):m.fingerprint(p) for p in inputs}
    timings=json.loads((raw/'batch_timings.json').read_text())
    m.write_json(out/'run_report.json',{'input_files_unchanged':before==after,'inputs':before,
        'render_timings':previous.get('render_timings',[])+timeout_records+timings,
        'total_seconds':round(time.monotonic()-start,2),'new_images':total,'reused_images':reused,
        'engine':'EEVEE','resolution':[m.WIDTH,m.HEIGHT],'threads':4,'priority':'below normal',
        'timeout_seconds_per_image':120,'blends_saved':0,'zones_requested':args.zones,'views':views,'persistent_worker':True})
    if before!=after: raise RuntimeError('A source asset changed during the batch; inspect run_report.json')
    print('ALL_LOCATORS_READY '+str(manifest_path),flush=True)


def worker(args,bpy,m):
    from types import SimpleNamespace
    out=m.safe_path(args.out); raw=out/'_raw'
    jobs=json.loads((raw/'batch_jobs.json').read_text()); spec=json.loads(m.SPEC_PATH.read_text(encoding='utf8'))
    original={o.name:(o.hide_render,o.hide_viewport) for o in bpy.context.scene.objects}
    lights={o.name:(o.data.energy,o.data.angle if o.data.type=='SUN' else None) for o in bpy.context.scene.objects if o.type=='LIGHT'}
    manifest_path=out/'locators.json'
    for index,job in enumerate(jobs):
        zid,view=job['zone'],job['view']; started=time.time()
        m.write_json(raw/'batch_state.json',{'status':'running','zone':zid,'view':view,'started':started,'index':index+1,'count':len(jobs)})
        for o in list(bpy.context.scene.objects):
            if o.name in original: o.hide_render,o.hide_viewport=original[o.name]
            elif o.type=='CAMERA' and o.name.startswith('locator_temporary'):
                data=o.data; bpy.data.objects.remove(o,do_unlink=True)
                if data.users==0: bpy.data.cameras.remove(data)
                continue
            if o.name in lights:
                o.data.energy=lights[o.name][0]
                if o.data.type=='SUN': o.data.angle=lights[o.name][1]
        bpy.context.view_layer.update()
        options=SimpleNamespace(zones=zid,view=view,out=str(out),samples=job['samples'],mask_existing=False,preflight=False,reuse_cameras=job.get('reuse_camera',False))
        m.worker(options,bpy)
        python=os.environ.get('LOCATOR_PYTHON','C:/Python313/python.exe')
        subprocess.run([python,'-B',str(m.BASE/'postprocess.py'),'--out',str(out),'--zone',zid,'--view',view],
            check=True,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        entry=json.loads((raw/f'{zid}_{view}.json').read_text())
        manifest=json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
        old=manifest.get(zid,{}); combined={k:old[k] for k in ('eye','map') if k in old}; combined[view]=entry
        z=next(z for z in spec['zones'] if z['id']==zid); reference=combined.get('map',combined.get('eye'))
        manifest[zid]={'name':z['name'],'label':reference['label'],'zone_alias':reference['zone_alias'],
            'image':f'{zid}_eye.png','open_in_3d':'map','cams_covering':reference['cams_covering'],
            'coverage_note':reference.get('coverage_note'),'zone_polygon_three':reference['zone_polygon_three'],
            'zone_polygon_parts_three':reference['zone_polygon_parts_three'],**combined}
        m.write_json(manifest_path,manifest)
        elapsed=time.time()-started
        timings=json.loads((raw/'batch_timings.json').read_text())
        timings.append({'zone':zid,'view':view,'samples':job['samples'],'seconds':round(elapsed,2),'exit_code':0})
        m.write_json(raw/'batch_timings.json',timings)
        m.write_json(raw/'batch_state.json',{'status':'completed','zone':zid,'view':view,'started':time.time(),'seconds':round(elapsed,2),'index':index+1,'count':len(jobs)})
    m.write_json(raw/'batch_state.json',{'status':'finished','started':time.time(),'count':len(jobs)})
