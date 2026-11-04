"""Sync finishing metadata and record control limits compatible with each saved camera."""
import json,math
from pathlib import Path
BASE=Path(__file__).resolve().parent

def finish():
    path=BASE/'out/locators.json'; data=json.loads(path.read_text(encoding='utf8'))
    for zid,zone in data.items():
        for view in ('eye','map'):
            entry=zone[view]; raw=BASE/f'out/_raw/{zid}_{view}.json'
            if raw.exists():
                latest=json.loads(raw.read_text(encoding='utf8'))
                for field in ('floor_colour_reference','floor_colour_match'):
                    if field in latest: entry[field]=latest[field]
            c=entry['three_camera']; distance=math.dist(c['position'],c['target'])
            entry['three_controls']={'minDistance':min(6,distance*.5),'maxDistance':max(95,distance*1.05)}
    ordered={k:data[k] for k in sorted(data)}
    path.write_text(json.dumps(ordered,indent=2,ensure_ascii=True)+'\n',encoding='utf8')
    path=BASE/'out/run_report.json'; report=json.loads(path.read_text(encoding='utf8'))
    latest={}
    for item in report['render_timings']:
        if item['exit_code']==0: latest[(item['zone'],item['view'])]=item
    report['latest_image_timings']=[latest[k] for k in sorted(latest)]
    report['zone_count']=len(data); report['image_count']=len(data)*2
    report['complete_set_image_seconds']=round(sum(t['seconds'] for t in latest.values()),2)
    report['maximum_image_seconds']=max(t['seconds'] for t in latest.values())
    report['floor_colour_rule']='Match natural floor per eye/map pair before indigo highlight'
    path.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
    print(json.dumps({k:report[k] for k in ['zone_count','image_count','complete_set_image_seconds','maximum_image_seconds']}))

if __name__=='__main__': finish()
