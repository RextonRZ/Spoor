"""Derive eye-level approaches solely from hub_spec walkways, scan points, doors and polygons."""
import math


def choose_eye(spec, zone, cast, inside, polygons, fixed_entrance=None, fixed_evidence=None):
    from mathutils import Vector
    zid=zone['id']; entries=[]
    if zone['kind']=='yard': return choose_yard_eye(spec,zone,cast,inside,polygons)
    if zid in {'Z01','Z02','Z03','Z04','Z05','Z06','Z07','Z08','Z10','Z12'}:
        from subject_views import choose
        return choose(spec,zone,cast)
    if zid=='Z11':
        entries=[(fixed_entrance[:2],fixed_evidence['basis'],0,fixed_evidence)]
    elif zone['kind']=='office':
        poly=polygons(zone)[0]
        west=min(p[0] for p in poly)
        route=next(w for w in spec['circulation']['walkways'] if w['id']=='W1')
        y=(route['rect_m'][1]+route['rect_m'][3])/2
        entries=[([west,y],'office west door onto W1 from spec',0,{})]
    else:
        for scan in spec['scan_points']:
            if scan['zone']==zid:
                entries.append((scan['position_m'][:2],'approach to a declared work/scan point',0,{'scan_point':scan['id']}))
        for poly in polygons(zone):
            for a,b in zip(poly,poly[1:]+poly[:1]):
                for k in range(1,12):
                    t=k/12
                    entries.append(([a[0]*(1-t)+b[0]*t,a[1]*(1-t)+b[1]*t],
                        'zone boundary beside a declared walkway',5.0,{}))
    points=[]
    for w in spec['circulation']['walkways']:
        x0,y0,x1,y1=w['rect_m']
        nx=max(2,math.ceil((x1-x0)/.3)); ny=max(2,math.ceil((y1-y0)/.3))
        for ix in range(nx):
            for iy in range(ny):
                points.append((x0+(ix+.5)*(x1-x0)/nx,y0+(iy+.5)*(y1-y0)/ny,w['id']))
    candidates=[]
    for entry,basis,penalty,evidence in entries:
        for x,y,walkway in points:
            distance=math.hypot(x-entry[0],y-entry[1])
            if not 4<=distance<=8: continue
            if zid=='Z11' and y>=entry[1]: continue
            frontal=abs(x-entry[0])*.35 if zid=='Z11' else 0
            score=penalty+abs(distance-4.5)+frontal
            candidates.append((score,x,y,walkway,distance,entry,basis,evidence))
    candidates.sort(key=lambda p:p[0])
    # Look beyond several blocked candidates without spending minutes searching an empty approach.
    for score,x,y,walkway,distance,entry,basis,evidence in candidates[:3000]:
        location=Vector((x,y,1.6)) # all declared walkways are on the indoor z=0 floor
        target=Vector((entry[0],entry[1],1.5))
        direction=target-location
        hit,pos,normal,face,obj,matrix=cast(location,direction.normalized(),direction.length-.04)
        if hit:
            hit_distance=(pos-location).length
            is_subject=any(inside(pos.x,pos.y,p) for p in polygons(zone))
            at_entrance=(pos-target).length<1.1
            if hit_distance<1.0 or not (is_subject or at_entrance): continue
            if zone['kind']=='yard' and not at_entrance: continue
        # A camera cannot stand in a cabinet, pallet or wall, even if a walkway overlaps a zone.
        if any(cast(location,Vector(axis),.25)[0] for axis in [(1,0,0),(-1,0,0),(0,1,0),(0,-1,0)]): continue
        details=dict(evidence)
        details.update({'basis':basis,'walkway':walkway,'distance_from_entrance_m':distance,
            'doorway_floor_blender':[entry[0],entry[1],0.0],'eye_height_m':1.6,'camera_floor_z_m':0.0,'lens_mm':27.0})
        return location,target,details,{'view':'eye','walkway':walkway,'location':list(location),
            'distance_from_entrance_m':distance,'basis':basis}
    raise RuntimeError(f'No clear 4-8m approach on the spec walkways for {zid}')


def choose_yard_eye(spec,zone,cast,inside,polygons):
    """Stand on the clear outer apron, derived from the yard polygon and static lorry bounds."""
    import bpy
    from mathutils import Vector
    west=zone['polygon_m']['west']
    x0,x1=min(p[0] for p in west),max(p[0] for p in west)
    y0,y1=min(p[1] for p in west),max(p[1] for p in west)
    lorries=bpy.context.scene.objects.get('lorries')
    if not lorries: raise RuntimeError('Missing static lorry geometry for exterior yard view')
    points=[lorries.matrix_world@v.co for v in lorries.data.vertices]
    points=[p for p in points if x0<=p.x<x1 and y0<=p.y<=y1]
    truck_front=min(p.x for p in points)
    row_center_y=(min(p.y for p in points)+max(p.y for p in points))/2
    ground=-max(d['dock_height'] for d in spec['building']['doors'] if d['kind']=='dock' and d['wall']=='W')
    strip=[x0,y0,truck_front,y1]
    for fraction in (.5,.35,.65):
        x=x0+(truck_front-x0)*fraction
        for entry_distance in (4.5,5.5,6.5):
            y=y0+entry_distance
            location=Vector((x,y,ground+1.6))
            if any(cast(location,Vector(axis),.4)[0] for axis in [(1,0,0),(-1,0,0),(0,1,0),(0,-1,0)]): continue
            hit,pos,*_=cast(location,Vector((0,0,-1)),2)
            if not hit or abs(pos.z-ground)>.04: continue
            target=Vector(((truck_front+x1)/2,row_center_y,ground+1.5))
            details={'basis':'exterior apron strip between spec west-yard edge and static lorry fronts',
                'walkway':'west yard apron','walkway_is_inferred':True,'walkway_rect_m':strip,
                'entrance_basis':'open south boundary of the west yard polygon',
                'doorway_floor_blender':[x,y0,ground],'distance_from_entrance_m':entry_distance,
                'eye_height_m':1.6,'camera_floor_z_m':ground,'lens_mm':27.0,
                'subject':'west yard lorry bays','lorry_front_x_m':truck_front}
            return location,target,details,{'view':'eye','location':list(location),'target':list(target),
                'eye_height_m':1.6,'distance_from_entrance_m':entry_distance,'basis':details['basis']}
    raise RuntimeError('No clear ground-level position in the exterior west-yard apron')
