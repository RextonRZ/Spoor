"""Hub map prototype for the app's Places (Rexton 1 Nov): the hub from straight above with every scanner as a numbered
checkpoint (its step in a parcel's journey), pan / zoom, groups that open as you zoom in; pick one and the side panel
shows it as a tilted 3D map, from straight above and at eye height (with the workers), its pin on each. Spoor's own
tokens (frontend/src/app/globals.css) and checkpoint words (frontend/src/lib/checkpoints.ts). For the frontend agent
to copy; data inlined so it opens from file://.   py -X utf8 assets/hub/place_page.py  -> assets/places/index.html
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
OUT = ROOT / "assets" / "places"
meta = json.loads((OUT / "out" / "places.json").read_text(encoding="utf-8"))
spec = json.loads((ROOT / "assets" / "hub" / "hub_spec.json").read_text(encoding="utf-8"))
ZONE_NAMES = {"Z01": "Inbound dock", "Z02": "Bag opening", "Z03": "Induction", "Z04": "Scan tunnel",
              "Z05": "Cross-belt sorter", "Z06": "Chutes + bagging", "Z07": "Reject", "Z08": "Exception bench",
              "Z09": "Oversize", "Z10": "Cage staging", "Z11": "Exception store", "Z12": "Outbound dock",
              "Z13": "Office", "Z14": "Truck yard"}  # frontend/src/lib/zones.ts
FIXED = {"SP-IN-N": "Unloading, north door", "SP-IN-S": "Unloading, south door", "SP-CAGE-W": "Cage staging, west",
         "SP-CAGE-E": "Cage staging, east", "SP-STORE-IN": "Exception store door", "SP-BAGOPEN": "Bag opening",
         "SP-REWORK": "Exception bench", "SP-OVERSIZE": "Oversize area"}
# a parcel's journey, in order (checkpoints.ts words where it has them)
STAGES = [(1, "Unloaded", "Handheld scan at the door", "Unloading"),
          (2, "Bag opening", "Scanned as each bag is opened", "Bag opening"),
          (3, "Sorter induct", "Placed on the sorter by hand", "Induct"),
          (4, "Scan tunnel", "Photo, weight and size", "Tunnel"),
          (5, "Into chute", "Sorter confirms the drop", "Chutes"),
          (6, "Into bag or cage", "Handheld scan", "Bag scans"),
          (7, "Exceptions", "Rework bench, oversize area and exception store", "Exceptions"),
          (8, "Loaded on truck", "Cage tag read at the dock gate", "Dock scanners")]


def stage(i):
    for pre, n in (("SP-IN-", 1), ("SP-BAGOPEN", 2), ("SP-INDUCT", 3), ("SP-TUNNEL", 4), ("SP-DIV-", 5),
                   ("SP-BAG-", 6), ("SP-CAGE-", 6), ("SP-LOAD-", 8), ("SP-RFID-", 8)):
        if i.startswith(pre):
            return n
    return 7


def place_name(i):  # frontend/src/app/hub/page.tsx placeName
    d, c = re.search(r"D\d{2}$", i), re.search(r"C\d{2}$", i)
    if i.startswith("SP-DIV-REJECT"):
        return "Reject chute"
    if i.startswith("SP-DIV-") and c:
        return f"Chute {c.group()}"
    if i.startswith("SP-BAG-") and c:
        return f"Bag scan, chute {c.group()}"
    if i.startswith("SP-TUNNEL"):
        return f"Scan tunnel, line {'B' if i.endswith('-B') else 'A'}"
    if i.startswith("SP-INDUCT"):
        return f"Sorter induct, line {'B' if i.endswith('-B') else 'A'}"
    if i.startswith("SP-RFID-") and d:
        return f"Dock {d.group()} gate"
    if i.startswith("SP-LOAD-") and d:
        return f"Dock {d.group()} loading"
    return FIXED.get(i, i)


order = sorted(spec["scan_points"], key=lambda s: (stage(s["id"]), s["id"]))
places = [{"id": s["id"], "name": place_name(s["id"]), "zone": s["zone"], "stage": stage(s["id"])} for s in order]
for z in meta["zones"].values():
    if "map" in z:
        z["map"]["image"] = "../locator/out/" + Path(z["map"]["image"]).name
data = {"hub": meta["hub_top"], "zones": meta["zones"], "places": places, "zoneNames": ZONE_NAMES,
        "stages": [{"n": n, "label": l, "how": h, "group": g} for n, l, h, g in STAGES]}

PAGE = r"""<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Hub map</title>
<style>
:root{--bg:#0e1012;--surface:#15181b;--surface-2:#1b1f23;--material-bg:rgba(21,24,27,.88);--hairline:rgba(226,232,238,.11);
--hairline-strong:rgba(226,232,238,.2);--ink-strong:#f3f5f7;--ink:#d6dbe0;--ink-muted:#9aa4ad;--accent:#a99bff;--accent-ink:#15121f;
--accent-tint:rgba(169,155,255,.13);--radius:.75rem;--radius-sm:.5rem;--ease:cubic-bezier(.22,1,.36,1);--ease-move:cubic-bezier(.77,0,.175,1);
--shadow:0 1px 3px rgba(0,0,0,.2),0 10px 30px rgba(0,0,0,.28);
--font:ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif;
--mono:ui-monospace,"SFMono-Regular","Cascadia Mono","Segoe UI Mono",Consolas,monospace;
--z-map:1;--z-chrome:2;--z-label:3;--z-tip:4}
*{box-sizing:border-box}html,body{height:100%}
body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.5 var(--font);-webkit-font-smoothing:antialiased;
display:grid;grid-template-rows:56px minmax(0,1fr);grid-template-columns:minmax(0,1fr);overflow:hidden}
button{font:inherit;color:inherit;cursor:pointer}
:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.num,.mono{font-family:var(--mono);font-variant-numeric:tabular-nums}
.micro{font-size:11px;letter-spacing:.08em;text-transform:uppercase;color:var(--ink-muted);font-weight:600}
header{display:flex;align-items:center;justify-content:space-between;gap:16px;padding:0 24px;border-bottom:1px solid var(--hairline)}
.brand{display:flex;align-items:baseline;gap:10px;font-size:15px}.brand b{color:var(--ink-strong);font-weight:650;letter-spacing:-.01em}
.brand span{color:var(--ink-muted)}
.hmeta{color:var(--ink-muted);font-size:13px;white-space:nowrap}.hmeta .num{color:var(--ink-strong)}
main{display:grid;grid-template-columns:minmax(0,1fr) 400px;gap:16px;padding:16px 24px 20px;min-height:0}
.mapcol{display:grid;grid-template-rows:auto minmax(0,1fr);gap:10px;min-height:0}
.toolbar{display:flex;align-items:center;gap:10px;min-height:36px}
.search{position:relative;flex:0 1 320px}
.search input{width:100%;height:36px;padding:0 12px 0 34px;background:rgba(27,31,35,.6);border:1px solid var(--hairline);
border-radius:var(--radius-sm);color:var(--ink-strong);font:inherit;transition:border-color .15s var(--ease)}
.search input::placeholder{color:var(--ink-muted)}.search input:focus{outline:none;border-color:var(--accent)}
.search svg{position:absolute;left:11px;top:11px;width:14px;height:14px;color:var(--ink-muted)}
.filter{display:none;align-items:center;gap:8px;height:28px;padding:0 6px 0 10px;border-radius:999px;background:var(--accent-tint);
color:var(--ink-strong);font-size:12px}.filter.on{display:inline-flex}
.filter button{background:none;border:0;width:20px;height:20px;border-radius:50%;color:var(--ink-muted);display:grid;place-items:center}
.filter button:hover{color:var(--ink-strong);background:rgba(255,255,255,.06)}
.tool-note{margin-left:auto;color:var(--ink-muted);font-size:12px}
.map{position:relative;overflow:hidden;border:1px solid var(--hairline);border-radius:var(--radius);background:#0b0d0f;
touch-action:none;cursor:grab;min-height:0;isolation:isolate}
.map::before{content:"";position:absolute;inset:0;background:#bcb8af;filter:brightness(.84) contrast(1.06) saturate(.9)}
/* the ground outside the picture, same colour and filter as the picture's own edge: no letterbox bands */
.map.dragging{cursor:grabbing}
.content{position:absolute;left:0;top:0;width:1600px;height:900px;transform-origin:0 0;z-index:var(--z-map)}
.content img{width:1600px;height:900px;display:block;user-select:none;-webkit-user-drag:none;pointer-events:none;
filter:brightness(.84) contrast(1.06) saturate(.9)}
.content svg{position:absolute;inset:0;width:1600px;height:900px;overflow:visible}
.zone{fill:rgba(0,0,0,0);stroke:rgba(226,232,238,.13);stroke-width:1;vector-effect:non-scaling-stroke;pointer-events:all;
transition:fill .15s var(--ease),stroke .15s var(--ease)}
.zone.hover{fill:rgba(169,155,255,.07);stroke:rgba(169,155,255,.45)}
.zone.sel{fill:rgba(169,155,255,.10);stroke:rgba(169,155,255,.7);stroke-width:1.5}
.layer{position:absolute;inset:0;pointer-events:none;z-index:var(--z-label)}
.mk{position:absolute;left:0;top:0;pointer-events:auto;display:inline-flex;align-items:center;gap:6px;border:1px solid var(--hairline-strong);
background:rgba(21,24,27,.92);color:var(--ink-strong);box-shadow:0 1px 2px rgba(0,0,0,.4);
transition:background-color .15s var(--ease),border-color .15s var(--ease),opacity .15s var(--ease),box-shadow .15s var(--ease)}
.mk:active{scale:.96}
.mk.dot{width:22px;height:22px;border-radius:50%;justify-content:center;font:600 11px var(--mono)}
.mk.grp{height:24px;padding:0 9px 0 2px;border-radius:999px;font-size:12px;font-weight:600;white-space:nowrap}
.mk.grp i{font:600 11px var(--mono);font-style:normal;width:18px;height:18px;border-radius:50%;display:grid;place-items:center;background:var(--surface-2)}
.mk.grp .c{color:var(--ink-muted);font-family:var(--mono);font-weight:500}
@media(hover:hover) and (pointer:fine){.mk:hover{border-color:var(--ink-muted);background:rgba(27,31,35,.98)}}
.mk.sel{background:var(--accent);border-color:var(--accent);color:var(--accent-ink);box-shadow:0 0 0 4px rgba(169,155,255,.25),0 1px 2px rgba(0,0,0,.4)}
.mk.sel i{background:rgba(21,18,31,.18)}.mk.sel .c{color:var(--accent-ink)}
.mk.dim{opacity:.25}.mk[hidden]{display:none}
.zlabel{position:absolute;left:0;top:0;padding:3px 8px;border-radius:6px;background:var(--material-bg);backdrop-filter:blur(8px);
border:1px solid var(--hairline);font-size:11px;color:var(--ink-strong);white-space:nowrap;opacity:0;transition:opacity .12s var(--ease);
pointer-events:none}.zlabel.on{opacity:1}
.chrome{position:absolute;z-index:var(--z-chrome);background:var(--material-bg);backdrop-filter:blur(8px);border:1px solid var(--hairline);
border-radius:var(--radius-sm)}
.zoom{right:12px;bottom:12px;display:grid}.zoom button{width:32px;height:32px;background:none;border:0;display:grid;place-items:center;color:var(--ink)}
.zoom button+button{border-top:1px solid var(--hairline)}.zoom button:hover{color:var(--ink-strong);background:rgba(255,255,255,.05)}
.zoom button:active svg{scale:.92}.zoom svg{width:14px;height:14px}
.scale{left:12px;bottom:12px;padding:6px 10px;font-size:11px;color:var(--ink)}
.scale .bar{height:6px;border:1.5px solid var(--ink);border-top:0;margin-top:3px}
.north{right:12px;top:12px;width:32px;height:32px;display:grid;place-items:center;font:600 10px var(--mono);color:var(--ink)}
.north svg{width:12px;height:12px;margin-bottom:-2px}
.tip{position:fixed;left:0;top:0;z-index:var(--z-tip);pointer-events:none;padding:6px 10px;border-radius:8px;background:var(--surface-2);
border:1px solid var(--hairline-strong);box-shadow:var(--shadow);font-size:12px;color:var(--ink-strong);white-space:nowrap;
opacity:0;transform:translateY(2px);transform-origin:50% 100%;transition:opacity .125s var(--ease),transform .125s var(--ease)}
.tip.on{opacity:1;transform:none}.tip.instant{transition:none}.tip .mono{color:var(--ink-muted);margin-left:8px;font-size:11px}
aside{background:var(--surface);border:1px solid var(--hairline);border-radius:var(--radius);display:flex;flex-direction:column;min-height:0;overflow:hidden}
.pscroll{overflow:auto;padding:20px;min-height:0;scrollbar-width:thin;scrollbar-color:rgba(154,164,173,.28) transparent}
.back{display:inline-flex;align-items:center;gap:6px;background:none;border:0;padding:4px 6px 4px 2px;margin:-4px 0 12px -2px;color:var(--ink-muted);
font-size:12px;border-radius:6px}.back:hover{color:var(--ink-strong)}.back:active{scale:.97}.back svg{width:12px;height:12px}
h1{font-size:20px;line-height:1.2;margin:6px 0 4px;color:var(--ink-strong);font-weight:650;letter-spacing:-.01em;text-wrap:balance}
.lede{color:var(--ink-muted);margin:0 0 16px;font-size:13px;max-width:34em}
.seg{position:relative;display:grid;grid-template-columns:repeat(3,1fr);background:var(--bg);border:1px solid var(--hairline);
border-radius:var(--radius-sm);padding:3px;margin-bottom:10px}
.seg .thumb{position:absolute;top:3px;bottom:3px;left:3px;width:calc((100% - 6px)/3);border-radius:6px;background:var(--surface-2);
border:1px solid var(--hairline-strong);transition:transform .2s var(--ease)}
.seg.instant .thumb{transition:none}
.seg button{position:relative;background:none;border:0;height:28px;font-size:12px;font-weight:600;color:var(--ink-muted);border-radius:6px;
transition:color .15s var(--ease)}.seg button[aria-selected=true]{color:var(--ink-strong)}
.shot{position:relative;aspect-ratio:16/9;border-radius:var(--radius-sm);overflow:hidden;background:#000;border:1px solid var(--hairline)}
.shot img{position:absolute;inset:0;width:100%;height:100%;object-fit:fill;transition:opacity .18s var(--ease)}
.shot svg{position:absolute;inset:0;width:100%;height:100%}
.shot .zo{fill:rgba(169,155,255,.06);stroke:rgba(169,155,255,.65);stroke-width:1.5;vector-effect:non-scaling-stroke}
.pin{position:absolute;width:14px;height:14px;margin:-7px 0 0 -7px;border-radius:50%;background:var(--accent);
box-shadow:0 0 0 3px var(--bg),0 0 0 5px rgba(169,155,255,.35)}
.pinlabel{position:absolute;transform:translate(12px,-50%);padding:2px 7px;border-radius:6px;background:var(--material-bg);
backdrop-filter:blur(8px);border:1px solid var(--hairline);font-size:11px;font-weight:600;color:var(--ink-strong);white-space:nowrap}
.pinlabel.left{transform:translate(calc(-100% - 12px),-50%)}
.mate{position:absolute;width:20px;height:20px;margin:-10px 0 0 -10px;border:0;background:none;padding:0;border-radius:50%;display:grid;place-items:center}
.mate::after{content:"";width:8px;height:8px;border-radius:50%;background:var(--ink-strong);box-shadow:0 0 0 2px rgba(14,16,18,.85)}
.mate:hover::after{background:#fff;scale:1.25}
.cap{color:var(--ink-muted);font-size:12px;margin:8px 2px 0;min-height:18px}
.sect{margin:22px 0 8px;display:flex;justify-content:space-between;align-items:baseline}
.rows{display:grid;gap:2px}
.row{display:grid;grid-template-columns:26px minmax(0,1fr) auto;align-items:center;gap:10px;min-height:40px;padding:0 10px;
border:0;background:none;border-radius:8px;text-align:left;transition:background-color .15s var(--ease)}
.row:hover{background:color-mix(in srgb,var(--accent) 6%,var(--surface-2))}
.row[aria-current=true],.row[aria-pressed=true]{background:var(--accent-tint)}.row:active{scale:.985}
.badge{width:22px;height:22px;border-radius:50%;display:grid;place-items:center;border:1px solid var(--hairline-strong);
font:600 11px var(--mono);color:var(--ink-strong)}
.row[aria-current=true] .badge,.row[aria-pressed=true] .badge{background:var(--accent);border-color:var(--accent);color:var(--accent-ink)}
.row .t{color:var(--ink-strong);font-weight:550;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.row .s{display:block;color:var(--ink-muted);font-size:12px;font-weight:400;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.row .k{color:var(--ink-muted);font-size:11px}
.hint{color:var(--ink-muted);font-size:12px;margin:16px 2px 0;line-height:1.6}.hint kbd{font:11px var(--mono);padding:1px 5px;border:1px solid var(--hairline-strong);border-radius:4px;color:var(--ink)}
@media(max-width:1000px){html,body{height:auto}body{overflow:auto;grid-template-rows:56px auto}
main{grid-template-columns:minmax(0,1fr);min-height:auto}.mapcol{grid-template-rows:auto auto;min-height:auto}.map{height:62vh}aside{max-height:none}.tool-note{display:none}}
@media(max-width:640px){header{padding:0 16px}.hmeta{display:none}main{padding:12px 16px 16px}.search{flex:1 1 auto}}
@media(prefers-reduced-motion:reduce){*{transition-duration:0s!important}.shot img{transition:opacity .12s linear!important}}
</style>
<header><div class="brand"><b>Spoor</b><span>/</span><span>Hub map</span></div>
<div class="hmeta"><span class="num" id="nPlaces"></span> scanners · <span class="num">14</span> zones · CONTOH Express hub (fictional)</div></header>
<main>
<section class="mapcol" aria-label="Hub map">
 <div class="toolbar">
  <label class="search"><svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6" aria-hidden="true"><circle cx="7" cy="7" r="5"/><path d="m11 11 3.5 3.5"/></svg>
  <input id="q" type="search" placeholder="Find a scanner: C12, D07, tunnel" aria-label="Find a scanner" autocomplete="off" spellcheck="false"></label>
  <span class="filter" id="filter"><span id="filterText"></span><button id="clearFilter" aria-label="Show every checkpoint"><svg viewBox="0 0 12 12" width="10" height="10" stroke="currentColor" stroke-width="1.6"><path d="m3 3 6 6M9 3l-6 6"/></svg></button></span>
  <span class="tool-note">Scroll to zoom · drag to move</span>
 </div>
 <div class="map" id="map">
  <div class="content" id="content"><img id="hubimg" alt="The whole hub from straight above, roof removed, north up" draggable="false"><svg id="zones" viewBox="0 0 1600 900"></svg></div>
  <div class="layer" id="layer"><div class="zlabel" id="zlabel"></div></div>
  <div class="chrome north" aria-hidden="true"><svg viewBox="0 0 12 12"><path d="M6 1 10 11 6 8.6 2 11Z" fill="currentColor"/></svg>N</div>
  <div class="chrome scale" aria-hidden="true"><span id="scaleText"></span><div class="bar" id="scaleBar"></div></div>
  <div class="chrome zoom"><button id="zin" aria-label="Zoom in"><svg viewBox="0 0 14 14" stroke="currentColor" stroke-width="1.6"><path d="M7 2v10M2 7h10"/></svg></button>
   <button id="zout" aria-label="Zoom out"><svg viewBox="0 0 14 14" stroke="currentColor" stroke-width="1.6"><path d="M2 7h10"/></svg></button>
   <button id="zfit" aria-label="Show the whole hub"><svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M2 5V2h3M9 2h3v3M12 9v3H9M5 12H2V9"/></svg></button></div>
 </div>
</section>
<aside aria-live="polite"><div class="pscroll" id="panel"></div></aside>
</main>
<div class="tip" id="tip" role="tooltip"></div>
<script>
const D=__DATA__;
const $=s=>document.querySelector(s),NS="http://www.w3.org/2000/svg",W=1600,H=900;
const P=Object.fromEntries(D.places.map(p=>[p.id,p])),ST=Object.fromEntries(D.stages.map(s=>[s.n,s]));
const reduce=matchMedia("(prefers-reduced-motion: reduce)").matches;
const st={sel:null,stage:null,q:"",view:"map",s:1,tx:0,ty:0,s0:1};
const map=$("#map"),content=$("#content"),layer=$("#layer"),tip=$("#tip");
$("#nPlaces").textContent=D.places.length;$("#hubimg").src="out/"+D.hub.image;

/* cubic-bezier(.77,0,.175,1) for on-screen movement */
function bez(x1,y1,x2,y2){const cx=3*x1,bx=3*(x2-x1)-cx,ax=1-cx-bx,cy=3*y1,by=3*(y2-y1)-cy,ay=1-cy-by;
 const X=t=>((ax*t+bx)*t+cx)*t,Y=t=>((ay*t+by)*t+cy)*t,dX=t=>(3*ax*t+2*bx)*t+cx;
 return x=>{let t=x;for(let i=0;i<6;i++){const d=dX(t);if(Math.abs(d)<1e-6)break;t-=(X(t)-x)/d}return Y(Math.min(1,Math.max(0,t)))}}
const easeMove=bez(.77,0,.175,1);

/* ---------- groups: a row of the same checkpoint in one zone opens as you zoom in ---------- */
const groups=[];{const by={};for(const p of D.places){const k=p.stage+"|"+p.zone;(by[k]=by[k]||[]).push(p)}
 for(const k in by)if(by[k].length>=3){const m=by[k],pts=m.map(p=>D.hub.scan_points[p.id]);
  groups.push({key:k,stage:m[0].stage,zone:m[0].zone,members:m.map(p=>p.id),x:pts.reduce((a,p)=>a+p.x,0)/pts.length,y:pts.reduce((a,p)=>a+p.y,0)/pts.length,
   box:[Math.min(...pts.map(p=>p.x)),Math.min(...pts.map(p=>p.y)),Math.max(...pts.map(p=>p.x)),Math.max(...pts.map(p=>p.y))]})}}
const groupOf={};groups.forEach(g=>g.members.forEach(id=>groupOf[id]=g));

/* ---------- zones ---------- */
const zoneEls={},zoneC={};
for(const [zid,polys] of Object.entries(D.hub.zones)){let sx=0,sy=0,n=0;
 for(const poly of polys){const e=document.createElementNS(NS,"polygon");e.setAttribute("points",poly.map(p=>p.join(",")).join(" "));
  e.setAttribute("class","zone");e.dataset.zone=zid;$("#zones").appendChild(e);(zoneEls[zid]=zoneEls[zid]||[]).push(e);
  for(const p of poly){sx+=p[0];sy+=p[1];n++}}
 zoneC[zid]=[sx/n,sy/n]}
let hoverZone=null;
function setHoverZone(z){if(z===hoverZone)return;if(hoverZone)zoneEls[hoverZone].forEach(e=>e.classList.remove("hover"));hoverZone=z;
 const L=$("#zlabel");if(z){zoneEls[z].forEach(e=>e.classList.add("hover"));L.textContent=z+" · "+D.zoneNames[z];L.classList.add("on");placeZoneLabel()}else L.classList.remove("on")}
function placeZoneLabel(){if(!hoverZone)return;const [x,y]=zoneC[hoverZone],L=$("#zlabel");
 L.style.transform=`translate(${x*st.s+st.tx}px,${y*st.s+st.ty}px) translate(-50%,-50%)`}
$("#zones").addEventListener("pointerover",e=>{const z=e.target.dataset&&e.target.dataset.zone;if(z&&!dragging)setHoverZone(z)});
$("#zones").addEventListener("pointerout",e=>{if(!e.relatedTarget||!e.relatedTarget.dataset||!e.relatedTarget.dataset.zone)setHoverZone(null)});

/* ---------- markers ---------- */
const mk={},gk={};
function marker(cls,html,label){const b=document.createElement("button");b.className="mk "+cls;b.innerHTML=html;b.setAttribute("aria-label",label);layer.appendChild(b);return b}
for(const p of D.places){const b=marker("dot",p.stage,`${p.name}, checkpoint ${p.stage}`);mk[p.id]=b;
 b.onclick=e=>select(p.id,{fly:false,kb:e.detail===0});tipOn(b,()=>`${p.name}<span class="mono">${p.id}</span>`)}
for(const g of groups){const s=ST[g.stage];const b=marker("grp",`<i>${g.stage}</i>${s.group}<span class="c">${g.members.length}</span>`,`${s.group}: ${g.members.length} scanners, zoom in`);
 gk[g.key]=b;b.onclick=()=>flyToBox(g.box,70);tipOn(b,()=>`${g.members.length} scanners · click to zoom in`)}

/* tooltips: a short delay for the first, then instant while moving between markers */
let tipT=0,tipHidAt=0;
function tipOn(el,html){el.addEventListener("pointerenter",()=>{if(dragging)return;clearTimeout(tipT);const show=()=>{const r=el.getBoundingClientRect();
  tip.innerHTML=html();tip.style.left=Math.round(r.left+r.width/2-tip.offsetWidth/2)+"px";tip.style.top=Math.round(r.top-tip.offsetHeight-8)+"px";tip.classList.add("on")};
 if(performance.now()-tipHidAt<400){tip.classList.add("instant");show();requestAnimationFrame(()=>tip.classList.remove("instant"))}else tipT=setTimeout(show,320)});
 el.addEventListener("pointerleave",hideTip)}
function hideTip(){clearTimeout(tipT);if(tip.classList.contains("on"))tipHidAt=performance.now();tip.classList.remove("on")}

/* ---------- view transform ---------- */
function fitState(box,pad){const fw=map.clientWidth,fh=map.clientHeight;
 if(!box){const s=Math.min(fw/W,fh/H);return{s,tx:(fw-W*s)/2,ty:(fh-H*s)/2}}
 const bw=Math.max(box[2]-box[0],40)+pad*2,bh=Math.max(box[3]-box[1],40)+pad*2,s=Math.min(st.s0*4,Math.max(st.s0,Math.min(fw/bw,fh/bh)));
 const cx=(box[0]+box[2])/2,cy=(box[1]+box[3])/2;return clamp({s,tx:fw/2-cx*s,ty:fh/2-cy*s})}
function clamp(v){const fw=map.clientWidth,fh=map.clientHeight,cw=W*v.s,ch=H*v.s;
 v.tx=cw<=fw?(fw-cw)/2:Math.min(0,Math.max(fw-cw,v.tx));v.ty=ch<=fh?(fh-ch)/2:Math.min(0,Math.max(fh-ch,v.ty));return v}
function apply(){content.style.transform=`translate(${st.tx}px,${st.ty}px) scale(${st.s})`;place();placeZoneLabel();scalebar()}
function place(){const grouped=st.s<st.s0*1.7;
 for(const p of D.places){const q=D.hub.scan_points[p.id],b=mk[p.id],g=groupOf[p.id];
  b.hidden=!!(grouped&&g);b.style.transform=`translate(${q.x*st.s+st.tx}px,${q.y*st.s+st.ty}px) translate(-50%,-50%)`}
 for(const g of groups){const b=gk[g.key];b.hidden=!grouped;b.style.transform=`translate(${g.x*st.s+st.tx}px,${g.y*st.s+st.ty}px) translate(-50%,-50%)`}}
function scalebar(){const mpp=D.hub.m_per_px/st.s;let m=[2,5,10,20,50].find(v=>v/mpp>=70)||50;
 $("#scaleBar").style.width=Math.round(m/mpp)+"px";$("#scaleText").textContent=m+" m"}
let anim=0;
function flyTo(v){cancelAnimationFrame(anim);v=clamp(v);if(reduce){Object.assign(st,v);apply();return}
 const a={s:st.s,tx:st.tx,ty:st.ty},t0=performance.now(),dur=320;
 const step=t=>{const k=easeMove(Math.min(1,(t-t0)/dur));st.s=a.s+(v.s-a.s)*k;st.tx=a.tx+(v.tx-a.tx)*k;st.ty=a.ty+(v.ty-a.ty)*k;apply();
  if(k<1)anim=requestAnimationFrame(step)};anim=requestAnimationFrame(step)}
const flyToBox=(box,pad)=>flyTo(fitState(box,pad));
function zoomAt(f,cx,cy,animate){const s=Math.min(st.s0*4,Math.max(st.s0,st.s*f)),v={s,tx:cx-(cx-st.tx)*(s/st.s),ty:cy-(cy-st.ty)*(s/st.s)};
 if(animate)flyTo(v);else{Object.assign(st,clamp(v));apply()}}
map.addEventListener("wheel",e=>{e.preventDefault();cancelAnimationFrame(anim);const r=map.getBoundingClientRect();
 zoomAt(Math.exp(-e.deltaY*.0015),e.clientX-r.left,e.clientY-r.top,false)},{passive:false});
let dragging=false,down=null;
map.addEventListener("pointerdown",e=>{if(e.button!==0||e.target.closest(".mk,.chrome"))return;cancelAnimationFrame(anim);
 down={x:e.clientX,y:e.clientY,tx:st.tx,ty:st.ty,zone:e.target.dataset&&e.target.dataset.zone};map.setPointerCapture(e.pointerId)});
map.addEventListener("pointermove",e=>{if(!down)return;const dx=e.clientX-down.x,dy=e.clientY-down.y;
 if(!dragging&&Math.hypot(dx,dy)>3){dragging=true;map.classList.add("dragging");hideTip();setHoverZone(null)}
 if(dragging){st.tx=down.tx+dx;st.ty=down.ty+dy;clamp(st);apply()}});
map.addEventListener("pointerup",e=>{if(down&&!dragging&&down.zone){const ps=D.hub.zones[down.zone].flat();
  flyToBox([Math.min(...ps.map(p=>p[0])),Math.min(...ps.map(p=>p[1])),Math.max(...ps.map(p=>p[0])),Math.max(...ps.map(p=>p[1]))],40)}
 down=null;dragging=false;map.classList.remove("dragging")});
map.addEventListener("dblclick",e=>{if(e.target.closest(".mk,.chrome"))return;const r=map.getBoundingClientRect();zoomAt(2,e.clientX-r.left,e.clientY-r.top,true)});
$("#zin").onclick=()=>zoomAt(1.6,map.clientWidth/2,map.clientHeight/2,true);
$("#zout").onclick=()=>zoomAt(1/1.6,map.clientWidth/2,map.clientHeight/2,true);
$("#zfit").onclick=()=>flyTo(fitState());
new ResizeObserver(()=>{const was=st.s0;const f=fitState();st.s0=f.s;if(Math.abs(st.s-was)<1e-6||!st.s){Object.assign(st,f)}else clamp(st);apply()}).observe(map);

/* ---------- filters: a checkpoint step, or a search ---------- */
const match=p=>(!st.stage||p.stage===st.stage)&&(!st.q||(p.name+" "+p.id+" "+D.zoneNames[p.zone]).toLowerCase().includes(st.q));
function paint(){for(const p of D.places){const b=mk[p.id];b.classList.toggle("dim",!match(p));b.classList.toggle("sel",p.id===st.sel)}
 for(const g of groups){const b=gk[g.key];b.classList.toggle("dim",!g.members.some(id=>match(P[id])));b.classList.toggle("sel",g.members.includes(st.sel))}
 for(const [z,els] of Object.entries(zoneEls))els.forEach(e=>e.classList.toggle("sel",!!st.sel&&P[st.sel].zone===z));
 const f=$("#filter");f.classList.toggle("on",!!st.stage);if(st.stage)$("#filterText").textContent=`Showing ${st.stage} · ${ST[st.stage].label}`}
$("#clearFilter").onclick=()=>{st.stage=null;paint();if(!st.sel)renderIntro()};
$("#q").addEventListener("input",e=>{st.q=e.target.value.trim().toLowerCase();paint()});
$("#q").addEventListener("keydown",e=>{if(e.key==="Enter"){const p=D.places.find(match);if(p)select(p.id,{fly:true})}
 if(e.key==="Escape"){e.target.value="";st.q="";paint();e.target.blur()}});

/* ---------- side panel ---------- */
const panel=$("#panel");
const esc=s=>String(s).replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
function renderIntro(){const counts={};D.places.forEach(p=>counts[p.stage]=(counts[p.stage]||0)+1);
 panel.innerHTML=`<p class="micro">How a parcel moves</p><h1>Eight checkpoints, ${D.places.length} scanners</h1>
 <p class="lede">Every scan a parcel gets happens at one of these places. Pick a step to see where it is on the map, or pick a scanner.</p>
 <div class="rows">${D.stages.map(s=>`<button class="row" data-stage="${s.n}" aria-pressed="${st.stage===s.n}"><span class="badge">${s.n}</span>
  <span class="t">${esc(s.label)}<span class="s">${esc(s.how)}</span></span><span class="k num">${counts[s.n]||0}</span></button>`).join("")}</div>
 <p class="hint"><kbd>/</kbd> find a scanner &nbsp; <kbd>←</kbd><kbd>→</kbd> step through them &nbsp; <kbd>Esc</kbd> back</p>`;
 panel.querySelectorAll("[data-stage]").forEach(b=>b.onclick=()=>{const n=+b.dataset.stage;st.stage=st.stage===n?null:n;paint();renderIntro();
  if(st.stage){const ids=D.places.filter(p=>p.stage===n).map(p=>D.hub.scan_points[p.id]);
   flyToBox([Math.min(...ids.map(p=>p.x)),Math.min(...ids.map(p=>p.y)),Math.max(...ids.map(p=>p.x)),Math.max(...ids.map(p=>p.y))],90)}})}
const VIEWS=[["map","3D map"],["top","From above"],["eye","Eye level"]];
function renderPlace(kb){const p=P[st.sel],z=D.zones[p.zone],s=ST[p.stage],mates=D.places.filter(q=>q.zone===p.zone);
 if(!z[st.view])st.view="top";const vi=VIEWS.findIndex(v=>v[0]===st.view);
 panel.innerHTML=`<button class="back" id="back"><svg viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M7.5 2.5 4 6l3.5 3.5"/></svg>All checkpoints</button>
 <p class="micro">Checkpoint ${s.n} · ${esc(s.label)}</p><h1>${esc(p.name)}</h1>
 <p class="lede">${p.zone} ${esc(D.zoneNames[p.zone])} · ${esc(s.how)} · <span class="mono" style="white-space:nowrap">${p.id}</span></p>
 <div class="seg${kb?" instant":""}" role="tablist" aria-label="Picture">${`<span class="thumb" style="transform:translateX(${vi*100}%)"></span>`}${VIEWS.map(([k,l])=>
  `<button role="tab" data-v="${k}" aria-selected="${k===st.view}" ${z[k]?"":"disabled"}>${l}</button>`).join("")}</div>
 <div class="shot" id="shot"><img alt=""><img alt="" style="opacity:0"><svg viewBox="0 0 1600 900" preserveAspectRatio="none"></svg></div>
 <p class="cap" id="cap"></p>
 <div class="sect"><span class="micro">In this zone</span><span class="k num micro">${mates.length}</span></div>
 <div class="rows">${mates.map(q=>`<button class="row" data-id="${q.id}" aria-current="${q.id===p.id}"><span class="badge">${q.stage}</span>
  <span class="t">${esc(q.name)}</span><span class="k mono">${q.id.replace("SP-","")}</span></button>`).join("")}</div>`;
 $("#back").onclick=()=>deselect();
 panel.querySelectorAll(".seg [role=tab]").forEach((b,i)=>{b.onclick=e=>setView(b.dataset.v,e.detail===0);
  b.onkeydown=e=>{if(e.key!=="ArrowRight"&&e.key!=="ArrowLeft")return;e.preventDefault();e.stopPropagation();
   const tabs=[...panel.querySelectorAll(".seg [role=tab]:not([disabled])")],j=tabs.indexOf(b),n=tabs[(j+(e.key==="ArrowRight"?1:-1)+tabs.length)%tabs.length];n.focus();setView(n.dataset.v,true)}});
 panel.querySelectorAll("[data-id]").forEach(b=>b.onclick=e=>select(b.dataset.id,{fly:false,kb:e.detail===0}));
 drawShot(true)}
function setView(v,kb){st.view=v;const seg=panel.querySelector(".seg");seg.classList.toggle("instant",!!kb);
 const vi=VIEWS.findIndex(x=>x[0]===v);seg.querySelector(".thumb").style.transform=`translateX(${vi*100}%)`;
 seg.querySelectorAll("[role=tab]").forEach(b=>b.setAttribute("aria-selected",b.dataset.v===v));drawShot(!!kb)}
let shotSeq=0;
function drawShot(instant){const p=P[st.sel],z=D.zones[p.zone],v=z[st.view],shot=$("#shot"),[a,b]=shot.querySelectorAll("img"),svg=shot.querySelector("svg");
 const src=v.image.startsWith("..")?v.image:"out/"+v.image,seq=++shotSeq,front=+a.style.opacity===0?b:a,back=front===a?b:a;
 const alt={map:"Tilted 3D map of ",top:"From straight above: ",eye:"At eye height in "}[st.view]+D.zoneNames[p.zone];
 const put=()=>{if(seq!==shotSeq)return;back.alt=alt;if(instant||reduce){back.style.transition=front.style.transition="none"}else back.style.transition=front.style.transition="";
  back.style.opacity=1;front.style.opacity=0;overlay(v,svg,shot)};
 back.src=src;back.decode?back.decode().then(put,put):(back.onload=put)}
function overlay(v,svg,shot){const p=P[st.sel];svg.innerHTML="";shot.querySelectorAll(".pin,.pinlabel,.mate").forEach(e=>e.remove());
 if(st.view!=="map")for(const poly of (v.zones[p.zone]||[])){const e=document.createElementNS(NS,"polygon");e.setAttribute("class","zo");
  e.setAttribute("points",poly.map(q=>q.join(",")).join(" "));svg.appendChild(e)}
 for(const [id,q] of Object.entries(v.scan_points)){if(id===p.id||q.seen===false||!P[id]||P[id].zone!==p.zone)continue;
  const m=document.createElement("button");m.className="mate";m.style.left=q.x/16+"%";m.style.top=q.y/9+"%";m.setAttribute("aria-label",P[id].name);
  m.onclick=e=>select(id,{fly:false,kb:e.detail===0});tipOn(m,()=>`${P[id].name}<span class="mono">${id}</span>`);shot.appendChild(m)}
 const h=v.scan_points[p.id],cap=$("#cap");
 if(h&&h.seen!==false){const d=document.createElement("span");d.className="pin";d.style.left=h.x/16+"%";d.style.top=h.y/9+"%";shot.appendChild(d);
  const l=document.createElement("span");l.className="pinlabel"+(h.x>1150?" left":"");l.textContent=p.name;l.style.left=h.x/16+"%";l.style.top=h.y/9+"%";shot.appendChild(l)}
 const ppl=st.view==="eye"&&(v.people||[]).length;
 cap.textContent=!h?"This scanner is outside this picture. Try From above.":h.seen===false?"Hidden behind equipment from this spot. Try From above.":
  {map:"Tilted view of the zone, shaded blue.",top:"From straight above, roof removed, north up.",eye:ppl?"At eye height, with the people working here.":"At eye height."}[st.view]}
function select(id,o={}){st.sel=id;paint();renderPlace(o.kb);history.replaceState(null,"","#"+id);
 const q=D.hub.scan_points[id],fw=map.clientWidth,fh=map.clientHeight,x=q.x*st.s+st.tx,y=q.y*st.s+st.ty;
 const g=groupOf[id],grouped=st.s<st.s0*1.7;
 if(o.fly||(g&&grouped)){const s=Math.max(st.s,st.s0*2.2),v=clamp({s,tx:fw/2-q.x*s,ty:fh/2-q.y*s});if(o.kb||reduce){Object.assign(st,v);apply()}else flyTo(v)}
 else if(x<40||y<40||x>fw-40||y>fh-40){st.tx+=fw/2-x;st.ty+=fh/2-y;clamp(st);apply()}}
function deselect(){st.sel=null;paint();renderIntro();history.replaceState(null,"",location.pathname)}
document.addEventListener("keydown",e=>{if(e.target.matches("input"))return;
 if(e.key==="/"){e.preventDefault();$("#q").focus();return}
 if(e.key==="Escape"){deselect();return}
 if(e.key!=="ArrowRight"&&e.key!=="ArrowLeft")return;if(e.target.closest(".seg"))return;e.preventDefault();
 const list=D.places.filter(match),i=list.findIndex(p=>p.id===st.sel),n=list[(i+(e.key==="ArrowRight"?1:-1)+list.length)%list.length];if(n)select(n.id,{kb:true})});
/* start: the whole hub, the eight steps; a #SP-... link opens that scanner */
Object.assign(st,fitState());st.s0=st.s;apply();paint();
const h=decodeURIComponent(location.hash.slice(1));if(P[h])select(h,{kb:true});else renderIntro();
</script>"""
(OUT / "index.html").write_text(PAGE.replace("__DATA__", json.dumps(data)), encoding="utf-8")
print("PAGE", OUT / "index.html", len(places), "places", len(meta["zones"]), "zones")
