"""Subject-first eye cameras derived from specified workstations, walking routes and crossover geometry."""
import math


def fit(location,points,lens):
    from mathutils import Vector
    target=sum(points,Vector())/len(points); distance=(target-location).length
    tanh=18/lens; tanv=tanh*9/16
    for _ in range(8):
        rotation=(target-location).to_track_quat('-Z','Y'); inv=rotation.inverted()
        local=[inv@(p-location) for p in points]
        if any(p.z>=-.05 for p in local): return target,99
        xs=[p.x/(-p.z*tanh) for p in local]; ys=[p.y/(-p.z*tanv) for p in local]
        dx=(min(xs)+max(xs))/2*tanh; dy=(min(ys)+max(ys))/2*tanv
        if abs(dx)+abs(dy)<1e-5: break
        direction=rotation@Vector((dx,dy,-1)).normalized(); target=location+direction*distance
    return target,max(max(abs(x) for x in xs),max(abs(y) for y in ys))


def box(x0,y0,z0,x1,y1,z1):
    from mathutils import Vector
    return [Vector((x,y,z)) for x in (x0,x1) for y in (y0,y1) for z in (z0,z1)]


def mesh_points(name):
    import bpy
    obj=bpy.context.scene.objects[name]
    return [obj.matrix_world@v.co for v in obj.data.vertices]


def choose(spec,zone,cast):
    from mathutils import Vector
    zid=zone['id']; lens=28.0 if zone['id'] in {'Z01','Z02','Z03','Z06','Z07','Z08','Z10'} else 26.0; candidates=[]
    walk={w['id']:w for w in spec['circulation']['walkways']}
    loops=spec['machines']['loop']; crossing={c['id']:c for c in spec['circulation']['crossovers']}
    allowed=set(); interest=[]
    if zid=='Z01':
        doors=[d for d in spec['building']['doors'] if d['kind']=='dock' and d['wall']=='W'][-3:]
        y0=min(d['centre'][1]-d['width']/2 for d in doors); y1=max(d['centre'][1]+d['width']/2 for d in doors)
        paths=[v['path'] for v in spec['machines']['conveyors'] if v['id'] in {'telescopic_'+d['id'] for d in doors}]
        xmin=min(p[0] for path in paths for p in path); xmax=max(p[0] for path in paths for p in path)
        points=box(xmin,y0,0,xmax,y1,5.0); interest=box(0,y0,1,xmax,y1,3)
        allowed={'wall_W','doors_docks','dock_furniture','dock_guard_posts','conveyors'}
        route=walk['W5']; a,b,c,d=route['rect_m']
        for x in (12.0,12.8,13.4): candidates.append((Vector((x,(b+d)/2,1.6)),{'walkway':route['id'],'camera_floor_z_m':0}))
    elif zid=='Z02':
        bench=next(b for b in spec['fixtures']['benches'] if b['name']=='bag-opening bench 2')
        x0,y0,x1,y1=bench['rect_m']; points=box(x0,y0,0,x1,y1,bench['height_m']+.4)
        interest=box(x0,y0,bench['height_m'],x1,y1,bench['height_m'])
        allowed={'fixtures','parcels_static_merged'}
        route=walk['W5']; a,b,c,d=route['rect_m']
        for offset in (1,1.5,2):
            x=(x0+x1)/2+(x1-x0)*offset
            candidates.append((Vector((x,(b+d)/2,1.6)),{'walkway':route['id'],'camera_floor_z_m':0}))
    elif zid=='Z03':
        poly=zone['polygon_m']; x0=min(p[0] for p in poly); x1=max(p[0] for p in poly)
        y0=min(p[1] for p in poly); y1=max(p[1] for p in poly)
        diverters=mesh_points('line_a_diverters')
        xmin=min(p.x for p in diverters)-.6; xmax=max(p.x for p in diverters)+.6
        points=[p for p in mesh_points('conveyors') if xmin<=p.x<=xmax and y0<=p.y<=y1 and p.z<=1.2]
        interest=[p for p in points if p.z>.85][::max(1,len(points)//80)]
        allowed={'conveyors','line_a_diverters'}; c=crossing['XO-2']; n=math.ceil(c['deck_m']/.19)
        ya,yb=c['south_stair_y']; run=(yb-ya)/n
        for k in (3,4,5,6):
            floor=c['deck_m']*(k+1)/n
            location=Vector((c['x']-c['width']*.4,ya+(k+.5)*run,floor+1.6))
            candidates.append((location,{'walkway':c['id'],'walkway_is_elevated':True,
                'walkway_rect_m':[c['x']-c['width']/2,ya,c['x']+c['width']/2,yb],
                'camera_floor_z_m':floor,'crossing_stair':'south','stair_step_index':k}))
    elif zid=='Z04':
        points=mesh_points('scan_tunnel_DWS-01'); allowed={'scan_tunnel_DWS-01','conveyors'}
        interest=box(19.5,8.7,1.55,19.5,10.3,2.75)
        c=crossing['XO-2']; n=math.ceil(c['deck_m']/.19); ya,yb=c['south_stair_y']; run=(yb-ya)/n
        for k in (0,1,2,3,4,5,6,7,8,9,10):
            floor=c['deck_m']*(k+1)/n; y=ya+(k+.5)*run
            for fraction in (-.4,-.25,0,.25,.4):
                x=c['x']+fraction*c['width']
                candidates.append((Vector((x,y,floor+1.6)),{'walkway':c['id'],'walkway_is_elevated':True,
                    'walkway_rect_m':[c['x']-c['width']/2,ya,c['x']+c['width']/2,yb],
                    'camera_floor_z_m':floor,'crossing_stair':'south','stair_step_index':k}))
        zebra=next(z for z in spec['circulation']['zebra_crossings'] if z['id']=='ZX2')
        a,b,c,d=zebra['rect_m']
        for fraction in (.65,.8,.95):
            candidates.append((Vector((c-.1,b+(d-b)*fraction,1.6)),{'walkway':zebra['id'],
                'walking_surface_kind':'zebra','walkway_rect_m':zebra['rect_m'],'camera_floor_z_m':0}))
        route=walk['W4']; a,b,c,d=route['rect_m']
        for y in (b+.3,b+.8,b+1.4):
            candidates.append((Vector((c-.1,y,1.6)),{'walkway':route['id'],'camera_floor_z_m':0}))
    elif zid=='Z05':
        import bpy
        c=crossing['XO-1']; floor=c['deck_m']
        points=[]
        for obj in bpy.context.scene.objects:
            if obj.name.startswith('carrier_'):
                points.extend([obj.matrix_world@Vector(p) for p in obj.bound_box if (obj.matrix_world@Vector(p)).x>=loops['east_cx']-loops['radius']])
        interest=points[::max(1,len(points)//70)]; allowed={'loop_deck_rails','loop_fence_mesh','loop_fence_posts'}
        for y in (loops['cy'],sum(c['bridge_y'])/2):
            candidates.append((Vector((c['x'],y,floor+1.6)),{'walkway':c['id'],'walkway_is_elevated':True,
                'walkway_rect_m':[c['x']-c['width']/2,c['bridge_y'][0],c['x']+c['width']/2,c['bridge_y'][1]],
                'camera_floor_z_m':floor,'crossing_deck':True}))
    elif zid=='Z06':
        chutes=spec['machines']['chutes'][3:6]
        x0=min(c['x'] for c in chutes)-.65; x1=max(c['x'] for c in chutes)+.65
        points=[]
        for name in ('chutes','bag_frames','bag_frame_clips','sacks_merged'):
            points.extend(p for p in mesh_points(name) if x0<=p.x<=x1 and 19.45<=p.y<=21.55)
        interest=[p for p in points if .8<=p.z<=1.75][::max(1,len(points)//60)]
        allowed={'chutes','bag_frames','bag_frame_clips','sacks_merged','loop_deck_rails'}
        route=walk['W3']; a,b,c,d=route['rect_m']
        for x in (x1+1.5,x1+2.5,x1+3.5):
            for y in ((b+d)/2,d-.12): candidates.append((Vector((x,y,1.6)),{'walkway':route['id'],'camera_floor_z_m':0}))
    elif zid=='Z07':
        chute=next(c for c in spec['machines']['chutes'] if c['id']=='REJECT'); x=chute['x']
        points=box(x-.75,19.5,0,x+.75,21.3,1.8); interest=box(x-.55,20.0,.3,x+.55,21.1,1.5)
        allowed={'chutes','reject_bin','bag_frames','loop_deck_rails'}
        route=walk['W3']; a,b,c,d=route['rect_m']
        for dx in (-.5,0,.5): candidates.append((Vector((x+dx,(b+d)/2,1.6)),{'walkway':route['id'],'camera_floor_z_m':0}))
    elif zid=='Z10':
        poly=zone['polygon_m']; x1=max(p[0] for p in poly); y0=min(p[1] for p in poly); y1=max(p[1] for p in poly)
        points=box(x1-6,y0,0,x1,y1,1.9); interest=box(x1-5,y0+.7,.5,x1-1,y1-.7,1.5)
        allowed={'cage_loads_merged'}; route=walk['W2']; a,b,c,d=route['rect_m']
        for x in (a+.15,(a+c)/2):
            for y in ((y0+y1)/2,y0+1.5): candidates.append((Vector((x,y,1.6)),{'walkway':route['id'],'camera_floor_z_m':0}))
    elif zid=='Z12':
        door=next(d for d in spec['building']['doors'] if d['id']=='D08'); x,y=door['centre']
        points=box(x-door['width']/2-.25,y-.5,0,x+door['width']/2+.25,y+.2,5.0)
        interest=box(x-door['width']/2,y,0.5,x+door['width']/2,y,3)
        allowed={'wall_N','doors_docks','dock_furniture','rfid_portals','cage_loads_merged'}
        route=walk['W6']; a,b,c,d=route['rect_m']
        for dx in (-1,0,1): candidates.append((Vector((x+dx,(b+d)/2,1.6)),{'walkway':route['id'],'camera_floor_z_m':0,'dock':door['id']}))
    elif zid=='Z08':
        bench=next(b for b in spec['fixtures']['benches'] if b['name']=='exception bench')
        x0,y0,x1,y1=bench['rect_m']; points=box(x0,y0,0,x1,y1,1.3); interest=box(x0,y0,.9,x1,y1,.9)
        allowed={'fixtures','parcels_static_merged','clutter_procedural'}; route=walk['W3']; a,b,c,d=route['rect_m']
        for extra in (2.5,3,4,5): candidates.append((Vector((x1+extra,(b+d)/2,1.6)),{'walkway':route['id'],'camera_floor_z_m':0}))
    elif zid=='Z13':
        poly=zone['polygon_m']; x0=min(p[0] for p in poly); x1=max(p[0] for p in poly); y1=max(p[1] for p in poly)
        points=box(x0,y1,0,x1,y1,3.0); interest=box(x0,y1,1,x1,y1,2.5)
        allowed={'fixtures','office_glass'}; route=walk['W2']; a,b,c,d=route['rect_m']
        for x in ((a+c)/2,a+.15):
            for extra in (4.5,5.5): candidates.append((Vector((x,y1+extra,1.6)),{'walkway':route['id'],'camera_floor_z_m':0}))
    else: raise ValueError(zid)
    scored=[]
    for location,details in candidates:
        target,extent=fit(location,points,lens)
        # Full subject bounds must fit; use the walking surface's true elevation for eye height.
        if extent>.98: continue
        if any(cast(location,Vector(axis),.2)[0] for axis in ((1,0,0),(-1,0,0),(0,1,0),(0,-1,0))): continue
        visible=0
        for p in interest:
            delta=p-location
            hit,pos,normal,face,obj,matrix=cast(location,delta.normalized(),max(.01,delta.length-.03))
            if not hit or obj.name in allowed or obj.name.startswith(('carrier_','cage_')) or (zid in {'Z06','Z07'} and obj.name.startswith('bag_')): visible+=1
        fraction=visible/max(1,len(interest))
        rotation=(target-location).to_track_quat('-Z','Y')
        tanh=18/lens; tanv=tanh*9/16; blocked=0; samples=0
        near=min((p-location).length for p in points)*.85
        for ix in range(15):
            for iy in range(8):
                ray=rotation@Vector((((ix+.5)/15*2-1)*tanh,((iy+.5)/8*2-1)*tanv,-1)).normalized()
                hit,pos,normal,face,obj,matrix=cast(location,ray,min(3.0,near))
                samples+=1
                if hit and obj.name not in allowed and not obj.name.startswith(('floor_','ground','yard_','carrier_','cage_')) and not (zid in {'Z06','Z07'} and obj.name.startswith('bag_')): blocked+=1
        foreground=blocked/samples
        scored.append((foreground,-fraction,abs(extent-.75),extent,location,target,details))
    if not scored: raise RuntimeError(f'No full-subject walking-route view for {zid}')
    foreground,score,fill,extent,location,target,details=min(scored,key=lambda c:c[:3])
    # The approach distance refers to the zone access/workface, while framing aims at the complete subject.
    approach=next((s['position_m'][:2] for s in spec['scan_points'] if s['zone']==zid),list(target[:2]))
    if zid=='Z01': approach=[max(p[0] for p in zone['polygon_m']),location.y]
    if zid=='Z10': approach=[max(p[0] for p in zone['polygon_m']),location.y]
    if zid=='Z12': approach=next(d['centre'] for d in spec['building']['doors'] if d['id']==details['dock'])
    if zid=='Z06': approach=[spec['machines']['chutes'][3]['x'],spec['machines']['chutes'][3]['mouth_y']]
    if zid=='Z03' and not details.get('walkway_is_elevated'): approach=[location.x,min(p[1] for p in zone['polygon_m'])]
    if zid=='Z04': approach=[19.5,9.5]
    if zid=='Z05': approach=[loops['east_cx']-loops['radius'],loops['cy']]
    if zid=='Z13': approach=[location.x,max(p[1] for p in zone['polygon_m'])]
    distance=math.hypot(location.x-approach[0],location.y-approach[1])
    details.update({'basis':'whole-subject framing on a specified walking surface','eye_height_m':1.6,'lens_mm':lens,
        'doorway_floor_blender':[approach[0],approach[1],0],'distance_from_entrance_m':distance,
        'subject_extent_ndc':extent,'foreground_obstruction_fraction':foreground,'subject_visibility_fraction':-score,'whole_subject_in_frame':extent<=.98})
    return location,target,details,{'view':'eye','location':list(location),'target':list(target),'lens_mm':lens,
        'subject_extent_ndc':extent,'foreground_obstruction_fraction':foreground,'subject_visibility_fraction':-score,'walkway':details['walkway']}
