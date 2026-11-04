"""Create aligned before/after review assets from the saved pre-repair captures."""
import html,json,hashlib
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
BASE=Path(__file__).resolve().parent; OUT=BASE/'out'; OLD=BASE/'out_before_zone_repairs'
NOTES={
'Z01':'Small transfer gaps were filled at the booms, collector bend and D02 stub. These are subtle in a whole-zone image.',
'Z02':'Overlapping cartons were moved apart. Uneven damaged-carton tops were deliberately kept in the source model.',
'Z03':'The long flat belt gained side guides and support legs. Small gaps at the angled belts and gravity tables were closed.',
'Z04':'No direct repair in this zone. Nearby induction equipment changed in the background.',
'Z05':'Belt bends and merge noses were repaired. Most repaired joins lie outside the saved eye camera angle.',
'Z06':'Support cartons were added inside the sacks. The visible pile tops did not move, so these views look nearly identical.',
'Z07':'Support cartons were added inside the bin. The visible pile top did not move.',
'Z08':'No direct repair in this zone. Surrounding equipment may show small changes.',
'Z09':'No direct repair in this zone. Repaired induction equipment is visible in the background.',
'Z10':'Some cage-load layers were lowered onto the items below. These are small local changes inside the cages.',
'Z11':'No direct geometry repair in this zone. The saved framing is unchanged.',
'Z12':'Some dock cage-load layers were lowered onto the items below. Look inside the cages.',
'Z13':'No direct geometry repair in this zone. The saved framing is unchanged.',
'Z14':'Cage loads were settled elsewhere in the yard. This saved outdoor eye view is effectively unchanged; compare the map.'}


def main():
    data=json.loads((OUT/'locators.json').read_text()); old=json.loads((OLD/'locators.json').read_text())
    entries={}
    for z,entry in sorted(data.items()):
        entries[z]={'name':entry['label'],'note':NOTES[z],'views':{}}
        for view in ('eye','map'):
            assert entry[view]['camera']==old[z][view]['camera'],(z,view,'Cannot overlay different cameras')
            name=entry[view]['image']; oldname=old[z][view]['image']
            digest=hashlib.sha256((OUT/name).read_bytes()).hexdigest()[:12]
            entries[z]['views'][view]={'before':'../out_before_zone_repairs/'+oldname,'after':name+'?v='+digest}
    payload=json.dumps(entries,ensure_ascii=True).replace('</','<'+chr(92)+'/')
    page='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Spoor repairs: before and after</title>
<style>
*{box-sizing:border-box}body{margin:0;padding:22px;background:#10151e;color:#e8edf7;font:16px system-ui,sans-serif}main{max-width:1640px;margin:auto}h1{font-size:25px;margin:0 0 10px}.tools{display:flex;gap:12px;align-items:center;flex-wrap:wrap;margin:14px 0}button,select{font:inherit;background:#202938;color:#fff;border:1px solid #52617a;border-radius:8px;padding:8px 12px}button{cursor:pointer}button.active{background:#5558ee}a{color:#b8bbff}.note{color:#c7cfdf;min-height:44px;max-width:1050px;line-height:1.5}.stage{overflow:auto;background:#070b12;border:1px solid #354158;border-radius:10px}.frame{position:relative;width:100%;aspect-ratio:16/9;touch-action:pan-y;user-select:none;cursor:ew-resize}.stage.full .frame{width:1600px;height:900px}.frame img{position:absolute;inset:0;width:100%;height:100%;pointer-events:none}.after{clip-path:inset(0 0 0 var(--split,50%))}.divider{position:absolute;left:var(--split,50%);top:0;height:100%;width:3px;background:#ffdf7c;pointer-events:none}.badge{position:absolute;top:12px;background:#10151eea;padding:7px 13px;border-radius:7px;font-size:14px;pointer-events:none}.before-badge{left:12px}.after-badge{right:12px}.slider{width:100%;accent-color:#8d90ff;margin:16px 0}.small{font-size:14px;color:#aeb8ca;line-height:1.5}
</style><main><h1>Hub repairs: before / after</h1><p>Drag the divider, or switch between the complete images. Both captures use the same saved camera.</p>
<div class="tools"><label>Zone <select id="zone"></select></label><button data-view="eye" class="active">Eye view</button><button data-view="map">Map view</button><button id="before-button">Show before</button><button id="after-button">Show after</button><button id="zoom">100% size</button></div>
<p id="note" class="note"></p><div id="stage" class="stage"><div id="frame" class="frame"><img id="before" alt="Before the source repairs" draggable="false"><img id="after" class="after" alt="After the source repairs" draggable="false"><div class="divider"></div><span class="badge before-badge">BEFORE</span><span class="badge after-badge">AFTER</span></div></div>
<input id="split" class="slider" type="range" min="0" max="100" value="50" aria-label="Before and after divider">
<div class="tools"><a id="open-before" target="_blank">Open full before image</a><a id="open-after" target="_blank">Open full after image</a><a href="review.html">All current image pairs</a></div><p class="small">These are the Blender captures. The live app and the separate 3D check still load the older hub.glb, which has not yet been re-exported with the repairs.</p></main>
<script>const DATA=__DATA__;const select=document.querySelector('#zone'),frame=document.querySelector('#frame'),slider=document.querySelector('#split');let view='eye';
for(const [id,d] of Object.entries(DATA)){const option=document.createElement('option');option.value=id;option.textContent=id+' / '+d.name;select.append(option)}
function setSplit(value){slider.value=value;frame.style.setProperty('--split',value+'%')}
function update(){const d=DATA[select.value],v=d.views[view];document.querySelector('#before').src=v.before;document.querySelector('#after').src=v.after;document.querySelector('#open-before').href=v.before;document.querySelector('#open-after').href=v.after;document.querySelector('#note').textContent=d.note;document.querySelectorAll('[data-view]').forEach(b=>b.classList.toggle('active',b.dataset.view===view));setSplit(50);const params=new URLSearchParams({zone:select.value,view});history.replaceState(null,'','?'+params)}
select.addEventListener('change',update);document.querySelectorAll('[data-view]').forEach(b=>b.onclick=()=>{view=b.dataset.view;update()});slider.oninput=()=>setSplit(slider.value);document.querySelector('#before-button').onclick=()=>setSplit(100);document.querySelector('#after-button').onclick=()=>setSplit(0);document.querySelector('#zoom').onclick=()=>{const full=document.querySelector('#stage').classList.toggle('full');document.querySelector('#zoom').textContent=full?'Fit to screen':'100% size'};let dragging=false;function move(e){const r=frame.getBoundingClientRect();setSplit(Math.max(0,Math.min(100,(e.clientX-r.left)/r.width*100)))}frame.onpointerdown=e=>{dragging=true;frame.setPointerCapture(e.pointerId);move(e)};frame.onpointermove=e=>{if(dragging)move(e)};frame.onpointerup=()=>dragging=false;frame.onpointercancel=()=>dragging=false;
const params=new URLSearchParams(location.search);select.value=DATA[params.get('zone')]?params.get('zone'):'Z03';view=params.get('view')==='map'?'map':'eye';update();
</script></html>'''.replace('__DATA__',payload)
    (OUT/'compare_repairs.html').write_text(page,encoding='utf8')
    font=ImageFont.truetype('C:/Windows/Fonts/seguisb.ttf',23)
    small=ImageFont.truetype('C:/Windows/Fonts/segoeui.ttf',18)
    width=740; pad=20; sheet=Image.new('RGB',(1540,1060),'#10151e'); draw=ImageDraw.Draw(sheet)
    draw.text((pad,16),'Z03: belt guides and support legs',font=font,fill='white')
    draw.text((pad,54),'BEFORE',font=small,fill='#b8c1d2'); draw.text((800,54),'AFTER',font=small,fill='#b8c1d2')
    for folder,x in ((OLD,pad),(OUT,800)):
        with Image.open(folder/'Z03_eye.png') as im:
            crop=im.convert('RGB').crop((90,230,1530,860)); crop=crop.resize((width,324),Image.Resampling.LANCZOS); sheet.paste(crop,(x,87))
    draw.text((pad,425),'Before: bare belt slab. After: continuous guide rail and legs below it.',font=small,fill='#d4dced')
    draw.text((pad,486),'Z02: overlapping cartons separated',font=font,fill='white')
    draw.text((pad,524),'BEFORE',font=small,fill='#b8c1d2'); draw.text((800,524),'AFTER',font=small,fill='#b8c1d2')
    for folder,x in ((OLD,pad),(OUT,800)):
        with Image.open(folder/'Z02_eye.png') as im:
            crop=im.convert('RGB').crop((490,180,950,385)); crop=crop.resize((width,330),Image.Resampling.LANCZOS); sheet.paste(crop,(x,558))
    draw.text((pad,905),'The small cartons moved apart. The large carton still has an uneven top.',font=small,fill='#d4dced')
    draw.text((pad,950),'Many other views look the same because the fixes are small, hidden inside sacks,',font=small,fill='#aeb8ca')
    draw.text((pad,978),'or outside the saved camera angle. The app 3D model still uses the older export.',font=small,fill='#aeb8ca')
    sheet.save(OUT/'repair_differences_Z02_Z03.png',optimize=True)
    print('BEFORE_AFTER_READY '+str(OUT/'compare_repairs.html'))

if __name__=='__main__': main()
