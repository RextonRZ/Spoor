"use client";
/**
 * A scanner's Blender turntable (owner 1 Nov: Blender quality you can turn): two rings of frames around it (place_turn.py,
 * public/places/turn/<id>/), "Side" 5.5 m up and "High" 16 m up. Drag sideways to turn (one frame per 18 px), drag up /
 * down or use the switch for the other ring, arrow keys too; scroll or + / - to zoom, and while zoomed a drag moves the
 * picture (reset to turn again). Every frame of a ring stays mounted once loaded, so turning is a swap of what is shown,
 * never a fetch; a ring still loading says how far it is. The scanner is pinned on each frame and the zone's other
 * scanners are dots to pick.
 */
import { useEffect, useRef, useState } from "react";
import { placeName, type TurnData } from "@/lib/places";
import { usePanZoom } from "./panzoom";

const RINGS: [string, string][] = [["mid", "Side"], ["high", "High"]];
const STEP_PX = 18;

export function Turntable({ point, n, big = false, onPick, onExpand }: {
  point: string; n: number; big?: boolean; onPick?: (id: string, el: HTMLElement) => void; onExpand?: () => void;
}) {
  const [data, setData] = useState<TurnData | null>(null);
  const [ring, setRing] = useState("mid");
  const [k, setK] = useState(0);
  const [loaded, setLoaded] = useState<Record<string, true>>({});
  const [turned, setTurned] = useState(false);
  const [pzFrame, pzInner, zoomed, pzReset, pzStep, pzHandlers] = usePanZoom();
  const drag = useRef<{ x: number; y: number; k: number; ringDone: boolean } | null>(null);
  useEffect(() => {
    let live = true;
    fetch(`/places/turn/${point}/turn.json`).then((r) => r.json()).then((d: TurnData) => { if (live) setData(d); }).catch(() => {});
    return () => { live = false; };
  }, [point]);
  const url = (r: string, i: number) => `/places/turn/${point}/${r}_${String(i).padStart(2, "0")}.webp`;
  const ringLoaded = (r: string) => Array.from({ length: n }, (_, i) => url(r, i)).filter((u) => loaded[u]).length;
  const nLoaded = ringLoaded(ring);
  const ready = nLoaded === n;
  // the other ring starts loading once this one is in
  const mounted = RINGS.map(([r]) => r).filter((r) => r === ring || ready);
  const f = data?.rings[ring]?.[k];
  const name = placeName(point);
  const turn = (d: number) => { setK((x) => (x + d + n * 8) % n); setTurned(true); };
  const other = (r: string) => { setRing(r); pzReset(); };
  return (
    <div className="hm-turn" data-big={big || undefined}>
      <div className="hm-shot hm-turnshot" ref={pzFrame} tabIndex={0} role="img"
        aria-label={`${name}, turntable view, frame ${k + 1} of ${n}. Arrow keys turn and change height.`}
        data-zoomed={zoomed || undefined} data-loading={!ready || undefined} aria-busy={!ready}
        onKeyDown={(e) => {
          if (e.key === "ArrowRight") { e.preventDefault(); turn(1); }
          if (e.key === "ArrowLeft") { e.preventDefault(); turn(-1); }
          if (e.key === "ArrowUp") { e.preventDefault(); other("high"); }
          if (e.key === "ArrowDown") { e.preventDefault(); other("mid"); }
        }}
        onPointerDown={(e) => {
          pzHandlers.onPointerDown(e);
          if (zoomed || e.button !== 0 || (e.target as HTMLElement).closest("button")) return;
          drag.current = { x: e.clientX, y: e.clientY, k, ringDone: false };
          e.currentTarget.setPointerCapture(e.pointerId);
        }}
        onPointerMove={(e) => {
          pzHandlers.onPointerMove(e);
          const d = drag.current; if (!d) return;
          const dx = e.clientX - d.x, dy = e.clientY - d.y;
          const nk = (((d.k - Math.round(dx / STEP_PX)) % n) + n) % n;
          if (nk !== k) { setK(nk); setTurned(true); }
          if (!d.ringDone && Math.abs(dy) > 60 && Math.abs(dy) > Math.abs(dx)) { d.ringDone = true; other(dy < 0 ? "high" : "mid"); }
        }}
        onPointerUp={(e) => { pzHandlers.onPointerUp(e); drag.current = null; }}
        onDoubleClick={pzHandlers.onDoubleClick}>
        <div className="hm-zoomable" ref={pzInner}>
          {mounted.flatMap((r) => Array.from({ length: n }, (_, i) => {
            const u = url(r, i);
            return (
              // eslint-disable-next-line @next/next/no-img-element
              <img key={u} src={u} alt="" draggable={false} data-front={(r === ring && i === k && loaded[u]) || undefined}
                fetchPriority={r === ring && i === k ? "high" : "auto"} decoding="async"
                onLoad={() => setLoaded((l) => (l[u] ? l : { ...l, [u]: true }))} />
            );
          }))}
          {ready && f && Object.entries(f.mates).map(([id, q]) => (
            <button key={id} type="button" className="hm-mate" style={{ left: `${q.x / 16}%`, top: `${q.y / 9}%` }} aria-label={placeName(id)}
              title={placeName(id)} onClick={(e) => onPick?.(id, e.currentTarget)} />
          ))}
          {ready && f && <>
            <span className="hm-pin" style={{ left: `${f.x / 16}%`, top: `${f.y / 9}%` }} aria-hidden="true" />
            <span className="hm-pinlabel" data-left={f.x > 1150 || undefined} style={{ left: `${f.x / 16}%`, top: `${f.y / 9}%` }}>{name}</span>
          </>}
        </div>
        {!ready && <div className="hm-shot-wait" role="status">Loading 3D view {nLoaded}/{n}</div>}
        {ready && !turned && !zoomed && <div className="hm-turnhint" aria-hidden="true">Drag to turn</div>}
        {onExpand && <div className="hm-3dbar">
          <button type="button" onClick={onExpand}>
            <svg viewBox="0 0 14 14" aria-hidden="true"><path d="M2 5V2h3M9 2h3v3M12 9v3H9M5 12H2V9" /></svg>Full screen
          </button>
        </div>}
        <div className="hm-ringtog" role="group" aria-label="Height">
          {RINGS.map(([r, label]) => (
            <button key={r} type="button" aria-pressed={ring === r} onClick={() => other(r)}>{label}</button>
          ))}
        </div>
        <div className="hm-chrome hm-pz">
          <button type="button" aria-label="Zoom in" onClick={() => pzStep(1.6)}><svg viewBox="0 0 14 14"><path d="M7 2v10M2 7h10" /></svg></button>
          <button type="button" aria-label="Zoom out" disabled={!zoomed} onClick={() => pzStep(1 / 1.6)}><svg viewBox="0 0 14 14"><path d="M2 7h10" /></svg></button>
          {zoomed && <button type="button" aria-label="Back to turning" onClick={() => pzReset(true)}>
            <svg viewBox="0 0 14 14"><path d="M2 5V2h3M9 2h3v3M12 9v3H9M5 12H2V9" /></svg></button>}
        </div>
      </div>
    </div>
  );
}
