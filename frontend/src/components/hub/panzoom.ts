"use client";
/** Pan and zoom for a picture in its frame (HubMap's WhereIs, the Turntable): wheel at the pointer, drag (while
 *  zoomed), double click, + / - / reset; written to the DOM (no re-render per frame); --k = 1 / scale keeps pins and dots
 *  their size. */
import { useCallback, useEffect, useRef, useState } from "react";

const reducedMotion = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;

/** Pan and zoom for a picture in its frame: wheel at the pointer, drag, double click, + / - / reset. Written to the DOM
 *  (no re-render per frame); --k = 1 / scale keeps pins and dots their size. */
export function usePanZoom() {
  // the frame as state, not a ref: the card renders nothing until places.json is in, and the wheel listener must
  // attach when the frame appears
  const [frame, setFrame] = useState<HTMLDivElement | null>(null);
  const inner = useRef<HTMLDivElement>(null);
  const v = useRef({ s: 1, x: 0, y: 0 });
  const drag = useRef<{ x: number; y: number; vx: number; vy: number; moved: boolean } | null>(null);
  const [zoomed, setZoomed] = useState(false);
  const set = useCallback((s: number, x: number, y: number, animate = false) => {
    const f = frame, el = inner.current; if (!f || !el) return;
    s = Math.min(5, Math.max(1, s));
    const w = f.clientWidth, h = f.clientHeight;
    x = Math.min(0, Math.max(w - w * s, x)); y = Math.min(0, Math.max(h - h * s, y));
    v.current = { s, x, y };
    el.toggleAttribute("data-animate", animate && !reducedMotion());
    el.style.transform = `translate(${x}px, ${y}px) scale(${s})`;
    el.style.setProperty("--k", String(1 / s));
    setZoomed(s > 1.001);
  }, [frame]);
  const zoomAt = useCallback((f: number, cx: number, cy: number, animate: boolean) => {
    const c = v.current, s = Math.min(5, Math.max(1, c.s * f));
    set(s, cx - (cx - c.x) * (s / c.s), cy - (cy - c.y) * (s / c.s), animate);
  }, [set]);
  useEffect(() => {
    const f = frame; if (!f) return;
    const wheel = (e: WheelEvent) => {
      e.preventDefault();
      const r = f.getBoundingClientRect(); zoomAt(Math.exp(-e.deltaY * 0.0015), e.clientX - r.left, e.clientY - r.top, false);
    };
    f.addEventListener("wheel", wheel, { passive: false });
    return () => f.removeEventListener("wheel", wheel);
  }, [frame, zoomAt]);
  const reset = (animate = false) => set(1, 0, 0, animate);
  const handlers = {
    onPointerDown: (e: React.PointerEvent<HTMLDivElement>) => {
      if (e.button !== 0 || v.current.s <= 1.001 || (e.target as HTMLElement).closest("button")) return;
      drag.current = { x: e.clientX, y: e.clientY, vx: v.current.x, vy: v.current.y, moved: false };
      e.currentTarget.setPointerCapture(e.pointerId);
    },
    onPointerMove: (e: React.PointerEvent<HTMLDivElement>) => {
      const d = drag.current; if (!d) return;
      const dx = e.clientX - d.x, dy = e.clientY - d.y;
      if (!d.moved && Math.hypot(dx, dy) > 3) { d.moved = true; e.currentTarget.dataset.dragging = ""; }
      if (d.moved) set(v.current.s, d.vx + dx, d.vy + dy);
    },
    onPointerUp: (e: React.PointerEvent<HTMLDivElement>) => { drag.current = null; delete e.currentTarget.dataset.dragging; },
    onDoubleClick: (e: React.MouseEvent<HTMLDivElement>) => {
      if ((e.target as HTMLElement).closest("button")) return;
      const r = e.currentTarget.getBoundingClientRect();
      if (v.current.s >= 4) reset(true); else zoomAt(2, e.clientX - r.left, e.clientY - r.top, true);
    },
  };
  const step = (f: number) => { if (frame) zoomAt(f, frame.clientWidth / 2, frame.clientHeight / 2, true); };
  return [setFrame, inner, zoomed, reset, step, handlers] as const;
}
