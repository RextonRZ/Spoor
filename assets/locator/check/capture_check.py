"""Serve the standalone GLB check, capture requested maps and validate their actual rendered cameras.
python -B assets/locator/check/capture_check.py --zones all
"""
import argparse,ctypes,functools,json,os,threading
from http.server import SimpleHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote,urlparse
from PIL import Image,ImageDraw,ImageFont
from playwright.sync_api import sync_playwright
BASE=Path(__file__).resolve().parent; LOCATOR=BASE.parent; ROOT=LOCATOR.parents[1]

class Handler(SimpleHTTPRequestHandler):
    def do_GET(self):
        path=(ROOT/unquote(urlparse(self.path).path).lstrip('/')).resolve()
        allowed=path.is_relative_to(LOCATOR) or path==ROOT/'frontend/public/hub.glb' or path.is_relative_to(ROOT/'frontend/public/draco')
        if not allowed: self.send_error(403); return
        super().do_GET()
    def log_message(self,*args): pass


def comparison(zid,result):
    with Image.open(LOCATOR/f'out/{zid}_map.png') as im: left=im.convert('RGB')
    with Image.open(BASE/f'three_{zid}.png') as im: right=im.convert('RGB')
    image=Image.new('RGB',(3200,1000),'#10141f'); d=ImageDraw.Draw(image)
    font=ImageFont.truetype('C:/Windows/Fonts/seguisb.ttf',24)
    small=ImageFont.truetype('C:/Windows/Fonts/segoeui.ttf',17)
    d.text((28,19),f'{zid} / BLENDER LOCATOR',font=font,fill='white')
    d.text((1628,19),'THREE.JS / EXISTING HUB.GLB',font=font,fill='white')
    image.paste(left,(0,62)); image.paste(right,(1600,62)); d.line((1600,62,1600,962),fill='#72778c',width=2)
    text=f'Same saved camera. Polygon error: {result["max_polygon_pixel_error"]:.4f}px. Visible fixture error: {result["max_anchor_pixel_error"]:.4f}px. Existing GLB dressing may differ.'
    d.text((28,972),text,font=small,fill='#c3c9da')
    image.save(BASE/f'compare_{zid}.png',optimize=True)


def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--serve',action='store_true'); parser.add_argument('--port',type=int,default=8766)
    parser.add_argument('--zones',default='Z11'); args=parser.parse_args()
    server=ThreadingHTTPServer(('127.0.0.1',args.port),functools.partial(Handler,directory=str(ROOT)))
    root_url=f'http://127.0.0.1:{server.server_port}/assets/locator/check/index.html'
    print(root_url,flush=True)
    if args.serve: server.serve_forever(); return
    threading.Thread(target=server.serve_forever,daemon=True).start()
    try: ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(),0x4000)
    except (AttributeError,OSError): pass
    data=json.loads((LOCATOR/'out/locators.json').read_text())
    zones=sorted(data) if args.zones=='all' else args.zones.split(',')
    runtime=BASE/'runtime'; runtime.mkdir(exist_ok=True); os.environ['TMP']=os.environ['TEMP']=str(runtime)
    results={}
    try:
        with sync_playwright() as p:
            context=p.chromium.launch_persistent_context(user_data_dir=str(runtime/'chrome'),
                executable_path='C:/Program Files/Google/Chrome/Application/chrome.exe',headless=True,
                viewport={'width':1600,'height':900},device_scale_factor=1,
                args=['--use-angle=swiftshader','--enable-unsafe-swiftshader','--disable-background-networking','--renderer-process-limit=2'])
            try:
                page=context.pages[0] if context.pages else context.new_page()
                errors=[]; logs=[]
                page.on('pageerror',lambda e:errors.append(str(e)))
                page.on('console',lambda m:logs.append({'type':m.type,'text':m.text}))
                for zid in zones:
                    errors.clear(); logs.clear()
                    page.goto(root_url+'?zone='+zid,wait_until='domcontentloaded',timeout=60000)
                    page.wait_for_function('window.__locatorReady || window.__locatorError',timeout=90000)
                    result=page.evaluate('window.__locatorCheck || {error:window.__locatorError}')
                    result['page_errors']=list(errors); result['browser_console']=list(logs)
                    (BASE/f'camera_check_{zid}.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf8')
                    if zid=='Z11': (BASE/'camera_check.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf8')
                    if not result.get('passed') or errors: raise RuntimeError(json.dumps(result,indent=2))
                    page.screenshot(path=str(BASE/f'three_{zid}.png'),animations='disabled')
                    comparison(zid,result); results[zid]=result
                    print(json.dumps({'zone':zid,'passed':True,'polygon_error_px':result['max_polygon_pixel_error']}),flush=True)
            finally: context.close()
    finally: server.shutdown()
    aggregate_path=BASE/'camera_checks.json'
    aggregate=json.loads(aggregate_path.read_text(encoding='utf8')) if aggregate_path.exists() else {}
    aggregate.update(results)
    aggregate_path.write_text(json.dumps(aggregate,indent=2)+'\n',encoding='utf8')
    print(f'CAMERA_CHECKS_PASSED {len(results)}',flush=True)

if __name__=='__main__': main()
