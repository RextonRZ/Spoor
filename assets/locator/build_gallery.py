"""Generate contact sheets and a small local review gallery from the saved manifest."""
import html,json,math
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
BASE=Path(__file__).resolve().parent
OUT=BASE/'out'


def build():
    data=json.loads((OUT/'locators.json').read_text())
    complete={z:d for z,d in sorted(data.items()) if all(v in d for v in ('eye','map'))}
    font=ImageFont.truetype('C:/Windows/Fonts/seguisb.ttf',18)
    small=ImageFont.truetype('C:/Windows/Fonts/segoeui.ttf',13)
    for view in ('eye','map'):
        width,thumb_h,gap=520,293,16
        rows=math.ceil(len(complete)/3)
        sheet=Image.new('RGB',(3*(width+gap)+gap,rows*(thumb_h+64)+68),'#111722')
        draw=ImageDraw.Draw(sheet)
        draw.text((gap,16),'SPOOR / '+('EYE-HEIGHT VIEWS' if view=='eye' else 'ZONE MAPS'),font=font,fill='white')
        for i,(z,d) in enumerate(complete.items()):
            x=gap+(i%3)*(width+gap); y=60+(i//3)*(thumb_h+64)
            with Image.open(OUT/d[view]['image']) as im: thumb=im.convert('RGB').resize((width,thumb_h),Image.Resampling.LANCZOS)
            sheet.paste(thumb,(x,y))
            label=z+' / '+d['label'].split(' (')[0]
            if len(label)>60: label=label[:57]+'...'
            draw.text((x,y+thumb_h+9),label,font=small,fill='#DDE3F1')
        sheet.save(OUT/f'overview_{view}.png',optimize=True)
    cards=[]
    for z,d in complete.items():
        cards.append(f'<section id="{z}"><h2>{html.escape(z+" / "+d["label"])}</h2><div class="pair">'+
            ''.join(f'<figure><a href="{d[v]["image"]}"><img loading="lazy" src="{d[v]["image"]}" alt="{html.escape(d["label"])} {v}"></a><figcaption>{"Eye-height photo" if v=="eye" else "Locator map"}</figcaption></figure>' for v in ('eye','map'))+
            f'</div><a class="check" href="../check/index.html?zone={z}">Open map camera in 3D</a></section>')
    page='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Spoor zone locators</title><style>
body{margin:0;background:#10151e;color:#e6eaf3;font:16px system-ui,sans-serif;padding:28px;max-width:1800px;margin:auto}h1{font-size:28px}h2{font-size:20px}.pair{display:grid;grid-template-columns:1fr 1fr;gap:18px}figure{margin:0}img{width:100%;display:block;border-radius:12px}figcaption{color:#aeb8c9;margin:8px 0}section{padding:22px 0 35px;border-top:1px solid #303848}a{color:#adb3ff}.check{font-size:14px}@media(max-width:800px){.pair{grid-template-columns:1fr}body{padding:16px}}</style><h1>Spoor zone locators</h1>'''+f'<p>{len(complete)} zones / {len(complete)*2} images. Click an image to open the full 1600 x 900 PNG.</p>'+'<p><a href="compare_repairs.html?zone=Z03">Compare before and after repairs</a></p>'+''.join(cards)+'</html>'
    (OUT/'review.html').write_text(page,encoding='utf8')
    print(f'GALLERY {len(complete)} zones: {OUT/"review.html"}')

if __name__=='__main__': build()
