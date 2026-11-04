"""Validate the complete locator set, coordinate conversion, natural floor match and input hashes."""
import argparse,ast,hashlib,json,math
from pathlib import Path
from PIL import Image
BASE=Path(__file__).resolve().parent; ROOT=BASE.parents[1]


def center(polys,z):
    parts=[]
    for poly in polys:
        area=cx=cy=0
        for p,q in zip(poly,poly[1:]+poly[:1]):
            cross=p[0]*q[1]-q[0]*p[1]; area+=cross; cx+=(p[0]+q[0])*cross; cy+=(p[1]+q[1])*cross
        parts.append((cx/(3*area),cy/(3*area),abs(area)/2))
    total=sum(p[2] for p in parts)
    return [sum(p[i]*p[2] for p in parts)/total for i in (0,1)]+[z]


def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--partial',action='store_true'); args=parser.parse_args()
    spec=json.loads((ROOT/'assets/hub/hub_spec.json').read_text(encoding='utf8'))
    data=json.loads((BASE/'out/locators.json').read_text())
    expected={z['id'] for z in spec['zones']}
    if not args.partial: assert set(data)==expected,'Missing zones'
    results=[]
    for zid,entry in sorted(data.items()):
        zone=next(z for z in spec['zones'] if z['id']==zid)
        if args.partial and not all(v in entry for v in ('eye','map')): continue
        floor_z=-1.2 if zone['kind']=='yard' else 0
        polys=list(zone['polygon_m'].values()) if isinstance(zone['polygon_m'],dict) else [zone['polygon_m']]
        assert entry['open_in_3d']=='map'
        eye=entry['eye']; map_view=entry['map']
        assert 26<=eye['camera']['lens']<=28
        assert abs(eye['camera']['location'][2]-eye['entrance'].get('camera_floor_z_m',0)-1.6)<1e-5
        assert 4-1e-4<=eye['entrance']['distance_from_entrance_m']<=8+1e-4
        if eye['entrance'].get('walkway_is_elevated'):
            route=next(c for c in spec['circulation']['crossovers'] if c['id']==eye['entrance']['walkway'])
            rect=eye['entrance']['walkway_rect_m']
            if eye['entrance'].get('crossing_deck'):
                expected_floor=route['deck_m']
            else:
                n=math.ceil(route['deck_m']/.19)
                expected_floor=route['deck_m']*(eye['entrance']['stair_step_index']+1)/n
            assert abs(expected_floor-eye['entrance']['camera_floor_z_m'])<1e-5
        elif eye['entrance'].get('walking_surface_kind')=='zebra':
            rect=next(z['rect_m'] for z in spec['circulation']['zebra_crossings'] if z['id']==eye['entrance']['walkway'])
        elif eye['entrance'].get('walkway_is_inferred'):
            assert zone['kind']=='yard'
            rect=eye['entrance']['walkway_rect_m']
            assert abs(eye['entrance']['camera_floor_z_m']-floor_z)<1e-5
        else:
            rect=next(w for w in spec['circulation']['walkways'] if w['id']==eye['entrance']['walkway'])['rect_m']
        x,y,_=eye['camera']['location']; x0,y0,x1,y1=rect
        assert x0<=x<=x1 and y0<=y<=y1
        assert not eye['floor_highlight']['enabled'] and map_view['floor_highlight']['enabled']
        desired=center(polys,floor_z)
        assert max(abs(a-b) for a,b in zip(map_view['camera']['target'],desired))<1e-4
        for p,original in zip(map_view['zone_polygon_parts_three'],polys):
            for actual,(x,y) in zip(p,original):
                assert max(abs(a-b) for a,b in zip(actual,[x,floor_z+.035,-y]))<1e-4
        for view in (eye,map_view):
            image=(BASE/'out'/view['image']).resolve(); assert image.is_relative_to(BASE/'out')
            with Image.open(image) as im: assert im.size==(1600,900); im.verify()
            for key,source in [('position','location'),('target','target')]:
                p=view['camera'][source]
                assert max(abs(a-b) for a,b in zip([p[0],p[2],-p[1]],view['three_camera'][key]))<1e-6
            vfov=math.degrees(2*math.atan(18/view['camera']['lens']*900/1600))
            assert abs(vfov-view['three_camera']['fov_deg'])<1e-7
            assert view['render_profile']['people_hidden'] and view['render_profile']['moving_parcels_hidden']
            assert '\u2014' not in view['label']
        matches=map_view['floor_colour_match']['surfaces']
        colour_error=max([max(abs(a-b) for a,b in zip(m['reference_rgb'],m['matched_rgb']))
            for m in matches.values() if 'matched_rgb' in m] or [0])
        assert colour_error<=1
        results.append({'zone_id':zid,'images':[eye['image'],map_view['image']],
            'eye_distance_m':eye['entrance']['distance_from_entrance_m'],'walkway':eye['entrance']['walkway'],
            'floor_colour_error_rgb':colour_error,'map_floor_visible_fraction':map_view['proof']['camera_candidates'][0]['floor_visible_fraction']})
    assert data['Z11']['map']['blind_corner']['coverage']=='none'
    assert data['Z11']['map']['cams_covering']==['CAM_19']
    report=json.loads((BASE/'out/run_report.json').read_text())
    assert report['input_files_unchanged'] and report['blends_saved']==0
    assert all(t['seconds']<=121 for t in report['render_timings'] if t['exit_code']==0)
    for rel,before in report['inputs'].items(): assert hashlib.sha256((ROOT/rel).read_bytes()).hexdigest()==before['sha256']
    for p in [BASE/'make_locators.py',BASE/'postprocess.py',BASE/'batch_runner.py',BASE/'camera_planning.py',BASE/'check/capture_check.py']:
        ast.parse(p.read_text(encoding='utf-8-sig'))
    check=json.loads((BASE/'check/camera_check.json').read_text())
    assert check['passed'] and not check['page_errors']
    camera_checks=json.loads((BASE/'check/camera_checks.json').read_text())
    assert set(camera_checks)==expected and all(c['passed'] and not c['page_errors'] for c in camera_checks.values())
    result={'passed':True,'zone_count':len(results),'image_count':len(results)*2,'zones':results,
        'source_files_unchanged':True,'resolution':[1600,900],'floor_colour_rule':'Natural floor matched per eye/map pair before indigo tint',
        'exception_camera_projection_error_px':check['max_polygon_pixel_error'],
        'existing_glb_limitation':report.get('glb_geometry_status','Existing GLB predates some dressing, including the Z11 store header.'),
        'map_camera_checks':{'passed':True,'zone_count':len(camera_checks),'max_polygon_error_px':max(c['max_polygon_pixel_error'] for c in camera_checks.values())}}
    path=BASE/'out'/('validation_partial.json' if args.partial else 'validation.json')
    path.write_text(json.dumps(result,indent=2)+'\n',encoding='utf8')
    print(json.dumps({k:v for k,v in result.items() if k!='zones'},indent=2))

if __name__=='__main__': main()
