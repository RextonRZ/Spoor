"""Locator finishing, run by system Python with Pillow, never by Blender Python."""
import argparse
import json
import math
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageEnhance, ImageFilter, ImageChops

BASE=Path(__file__).resolve().parent
SCALE=2


def font(size,bold=False):
    names=['C:/Windows/Fonts/Inter-SemiBold.ttf' if bold else 'C:/Windows/Fonts/Inter-Regular.ttf',
           'C:/Windows/Fonts/seguisb.ttf' if bold else 'C:/Windows/Fonts/segoeui.ttf',
           'C:/Windows/Fonts/arialbd.ttf' if bold else 'C:/Windows/Fonts/arial.ttf']
    for name in names:
        if Path(name).exists(): return ImageFont.truetype(name,round(size*SCALE))
    return ImageFont.load_default(size=round(size*SCALE))


def surface_masks(raw,stem,size):
    path=raw/f'{stem}_surface.pgm'
    if not path.exists(): return {}
    labels=Image.open(path)
    masks={}
    for name,value in [('indoor',255),('yard',128)]:
        mask=labels.point(lambda n:255 if n==value else 0)
        if sum(mask.histogram()[1:])<16: continue
        masks[name]=mask.resize(size,Image.Resampling.BILINEAR)
    return masks


def median_rgb(image,mask):
    values=[]
    for channel in image.split():
        hist=channel.histogram(mask=mask); total=sum(hist); target=total/2; acc=0
        for value,count in enumerate(hist):
            acc+=count
            if acc>=target:
                values.append(value); break
    return values


def write_floor_tones(raw,stem,image,masks):
    data={name:median_rgb(image,mask) for name,mask in masks.items()}
    (raw/f'{stem}_floor_tones.json').write_text(json.dumps(data,indent=2)+'\n',encoding='utf8')
    return data


def match_floor(image,original,raw,stem,zid,masks):
    reference=raw/f'{zid}_eye_floor_tones.json'
    target=json.loads(reference.read_text()) if reference.exists() else {}
    fallback=raw/'Z11_eye_floor_tones.json'
    fallback=json.loads(fallback.read_text()) if fallback.exists() else {}
    matches={}
    for name,mask in masks.items():
        desired=target.get(name,fallback.get(name))
        current=median_rgb(original,mask)
        if desired:
            gains=[desired[i]/max(1,current[i]) for i in range(3)]
            corrected=Image.merge('RGB',tuple(channel.point([min(255,round(v*g)) for v in range(256)])
                for channel,g in zip(original.split(),gains)))
            matches[name]={'reference_rgb':desired,'raw_map_rgb':current,'gain_rgb':gains,
                'matched_rgb':median_rgb(corrected,mask)}
        else:
            corrected=original
            matches[name]={'reference':'original physical material; this surface is absent in the eye photo'}
        image=Image.composite(corrected,image,mask)
    return image,matches


def finish(out,zid,view):
    out=Path(out).resolve()
    if not out.is_relative_to(BASE): raise ValueError('Outputs must stay in assets/locator')
    raw=out/'_raw'
    stem=f'{zid}_{view}'
    entry=json.loads((raw/f'{stem}.json').read_text())
    camera=entry['three_camera']; distance=math.dist(camera['position'],camera['target'])
    entry['three_controls']={'minDistance':min(6,distance*.5),'maxDistance':max(95,distance*1.05)}
    image=Image.open(raw/f'{stem}.png').convert('RGB')
    w,h=image.size
    original=image.copy()
    masks=surface_masks(raw,stem,(w,h))
    tones=write_floor_tones(raw,stem,image,masks)
    if view=='eye':
        entry['floor_colour_reference']={'mode':'natural','median_rgb':tones}
        (raw/f'{stem}.json').write_text(json.dumps(entry,indent=2)+'\n',encoding='utf8')
        # Phone-style primary image: original materials and colours, one small label only.
        overlay=Image.new('RGBA',(w*SCALE,h*SCALE)); d=ImageDraw.Draw(overlay)
        title=entry['label'].replace('\u2014','-').replace('\u2013','-')
        tw=d.textlength(title,font=font(18,True))/SCALE
        d.rounded_rectangle((28*SCALE,28*SCALE,(tw+60)*SCALE,72*SCALE),radius=11*SCALE,fill=(16,20,31,221))
        d.text((44*SCALE,36*SCALE),title,font=font(18,True),fill='#FFFFFF')
        image=Image.alpha_composite(image.convert('RGBA'),overlay.resize((w,h),Image.Resampling.LANCZOS)).convert('RGB')
        image.save(out/f'{stem}.png',optimize=True)
        print(f'FINISHED {out/stem}.png',flush=True)
        return

    poly_mask=Image.new('L',(w,h)); pd=ImageDraw.Draw(poly_mask)
    projected=entry['proof']['polygon_pixels_blender']
    for poly in projected: pd.polygon([tuple(p) for p in poly],fill=255)
    neutral=ImageEnhance.Brightness(ImageEnhance.Color(image).enhance(.56)).enhance(.80)
    image=Image.composite(ImageEnhance.Brightness(image).enhance(.96),neutral,poly_mask)
    image,matches=match_floor(image,original,raw,stem,zid,masks)
    entry['floor_colour_match']={'mode':'match natural eye-photo floor before indigo tint','surfaces':matches}
    (raw/f'{stem}.json').write_text(json.dumps(entry,indent=2)+'\n',encoding='utf8')
    floor=Image.open(raw/f'{stem}_floor.pgm').resize((w,h),Image.Resampling.BILINEAR)
    opacity=floor.point(lambda v:round(v*.35))
    image=Image.composite(Image.new('RGB',(w,h),'#5558EE'),image,opacity).convert('RGBA')
    if entry.get('blind_corner'):
        blind=Image.new('L',(w,h)); bd=ImageDraw.Draw(blind)
        bd.polygon([tuple(p) for p in entry['blind_corner']['screen_polygon']],fill=255)
        visible_blind=ImageChops.multiply(blind,floor)
        hatch=Image.new('L',(w,h)); hd=ImageDraw.Draw(hatch)
        for x in range(-h,w+h,14): hd.line((x,h,x+h,0),fill=105,width=2)
        hatch=ImageChops.multiply(hatch,visible_blind)
        image=Image.composite(Image.new('RGBA',(w,h),'#D5D5FF'),image,hatch)

    # Supersampled, fixed 2.5px edge, occluded by the same fixtures as the floor fill.
    edge=Image.new('L',(w*SCALE,h*SCALE)); ed=ImageDraw.Draw(edge)
    for poly in projected:
        pts=[(round(x*SCALE),round(y*SCALE)) for x,y in poly]
        ed.line(pts+[pts[0]],fill=255,width=5,joint='curve')
    edge=edge.resize((w,h),Image.Resampling.LANCZOS)
    edge=ImageChops.multiply(edge,floor.filter(ImageFilter.MaxFilter(7)))
    glow=edge.filter(ImageFilter.GaussianBlur(3)).point(lambda p:round(p*.6))
    image=Image.composite(Image.new('RGBA',(w,h),'#777AFF'),image,glow)
    image=Image.composite(Image.new('RGBA',(w,h),'#ADAEFF'),image,edge)
    overlay=Image.new('RGBA',(w*SCALE,h*SCALE))
    d=ImageDraw.Draw(overlay)
    def box(bounds,fill=(16,20,31,234),radius=14,outline=(255,255,255,25)):
        d.rounded_rectangle(tuple(round(n*SCALE) for n in bounds),radius=radius*SCALE,fill=fill,outline=outline,width=SCALE)
    def text(x,y,value,size,color='#FFFFFF',bold=False):
        if '\u2014' in value: raise ValueError('Em dashes are prohibited')
        d.text((round(x*SCALE),round(y*SCALE)),value,font=font(size,bold),fill=color)
    title=entry['label']
    if len(title)>64: title=title[:61]+'...'
    title_w=d.textlength(title,font=font(30,True))/SCALE
    subtitle=f'{zid}  /  '+entry['name'].split(' (')[0]
    if zid!='Z11': subtitle=zid+'  /  HUB LOCATOR'
    subtitle=subtitle.replace('\u2014','-').replace('\u2013','-')
    sub_w=d.textlength(subtitle,font=font(15))/SCALE
    label_w=max(title_w,sub_w)+84
    box((28,28,28+label_w,125),radius=17)
    d.rounded_rectangle((48*SCALE,53*SCALE,58*SCALE,93*SCALE),radius=5*SCALE,fill='#777AFF')
    text(75,42,title,30,bold=True)
    text(76,88,subtitle,15,'#BAC1D1')
    if zid=='Z11':
        box((28,137,515,175),fill=(16,20,31,214),radius=10)
        text(44,145,'CAM 19: entrance only  /  Blind corner: no coverage',14,'#D9DDE8')
    # Camera positions are spec positions projected by the saved perspective camera.
    for cam in entry['coverage_details']:
        x,y=cam['screen_xy']
        if not (35<x<w-120 and 205<y<h-110): continue
        box((x-16,y-16,x+16,y+16),fill=(26,30,46,240),radius=8)
        d.rounded_rectangle(((x-9)*SCALE,(y-5)*SCALE,(x+3)*SCALE,(y+5)*SCALE),radius=2*SCALE,outline='#E2E4FF',width=2*SCALE)
        d.polygon([((x+3)*SCALE,(y-3)*SCALE),((x+10)*SCALE,(y-7)*SCALE),((x+10)*SCALE,(y+7)*SCALE),((x+3)*SCALE,(y+3)*SCALE)],fill='#E2E4FF')
        label=cam['id'].replace('CAM_','CAM ')
        tw=d.textlength(label,font=font(13,True))/SCALE
        box((x+23,y-13,x+tw+44,y+14),radius=7)
        text(x+33,y-9,label,13,bold=True)
    # True north is +Y in the spec, projected into the current camera's screen plane.
    nx,ny=entry['compass']['screen_vector']; length=math.hypot(nx,ny)
    nx,ny=nx/length,ny/length
    cx,cy=78,h-77
    box((28,h-128,128,h-28),fill=(16,20,31,226),radius=18)
    d.ellipse(((cx-31)*SCALE,(cy-31)*SCALE,(cx+31)*SCALE,(cy+31)*SCALE),outline=(172,180,199,65),width=SCALE)
    tip=(cx+nx*23,cy+ny*23); tail=(cx-nx*19,cy-ny*19)
    d.line((tail[0]*SCALE,tail[1]*SCALE,tip[0]*SCALE,tip[1]*SCALE),fill='#DDE0FA',width=2*SCALE)
    perp=(-ny,nx)
    d.polygon([(tip[0]*SCALE,tip[1]*SCALE),((tip[0]-nx*13+perp[0]*5)*SCALE,(tip[1]-ny*13+perp[1]*5)*SCALE),((tip[0]-nx*13-perp[0]*5)*SCALE,(tip[1]-ny*13-perp[1]*5)*SCALE)],fill='#A9ABFF')
    tx,ty=cx+nx*36-5,cy+ny*36-11
    text(tx,ty,'N',14,bold=True)
    tag='Demo hub (3D model)'
    tag_w=d.textlength(tag,font=font(14))/SCALE+32
    box((w-tag_w-28,h-66,w-28,h-28),fill=(16,20,31,226),radius=10)
    text(w-tag_w-12,h-59,tag,14,'#DFE2EC')
    image=Image.alpha_composite(image,overlay.resize((w,h),Image.Resampling.LANCZOS)).convert('RGB')
    path=out/f'{stem}.png'
    image.save(path,optimize=True)
    print(f'FINISHED {path}',flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('--out',required=True); p.add_argument('--zone',required=True); p.add_argument('--view',choices=['eye','map'],required=True)
    a=p.parse_args(); finish(a.out,a.zone,a.view)
