"use client";
/**
 * Track this parcel (owner 1 Nov; Meta's SAM 3.1 docs: to follow ONE object, prompt it with a box on a chosen frame and
 * let SAM propagate both ways). On a paused ORIGINAL frame the investigator drags a box around the carton; the box,
 * in the frame's own pixels, goes to POST /v1/media/{id}/segment as an instance prompt on that frame. The backend links
 * the single resulting track to the case object (operator-selected = verified on this camera), so the journey,
 * follow-cam and evidence pick it up. A box can be drawn again on a later frame or another camera (SAM's re-prompt for
 * re-entry; ids do not survive leaving view). Shown only when SAM is configured; never guesses a box.
 */
import { useRef, useState, type ReactNode } from "react";
import { api, invalidate } from "@/lib/api";
import { useWorkspace } from "./context";

type Phase = { k: "idle" } | { k: "draw" } | { k: "run"; frames: string } | { k: "done"; text: string; ok: boolean };
interface Span { first_frame_index: number; last_frame_index: number }
/** linked_track: the stretch through the boxed frame, up to where SAM lost the parcel (later stretches stay unlinked) */
interface Job { status: string; result?: { status: string; message?: string; tracks?: Span[]; linked_track?: Span | null }; error?: string }

export function TrackParcel({ mediaId, frame, children }: { mediaId: string; frame: number; children: ReactNode }) {
  const { caseId, caps } = useWorkspace();
  const [phase, setPhase] = useState<Phase>({ k: "idle" });
  const [box, setBox] = useState<[number, number, number, number] | null>(null);  // in % of the shown frame
  const wrap = useRef<HTMLDivElement>(null);
  const start = useRef<[number, number] | null>(null);
  if (!caps.data?.sam) return <>{children}</>;

  const pct = (e: React.PointerEvent): [number, number] => {
    const r = wrap.current!.getBoundingClientRect();
    return [Math.min(100, Math.max(0, ((e.clientX - r.left) / r.width) * 100)), Math.min(100, Math.max(0, ((e.clientY - r.top) / r.height) * 100))];
  };
  async function send(b: [number, number, number, number]) {
    const img = wrap.current?.querySelector("img");
    if (!img?.naturalWidth) return;
    const W = img.naturalWidth, H = img.naturalHeight;
    const ltrb = [Math.round((b[0] / 100) * W), Math.round((b[1] / 100) * H), Math.round((b[2] / 100) * W), Math.round((b[3] / 100) * H)];
    setPhase({ k: "run", frames: "" });
    try {
      const j = await api<{ job_id: string }>(`/v1/media/${mediaId}/segment`, { method: "POST",
        json: { case_id: caseId, instance: { frame_index: frame, box_ltrb_px: ltrb } } });
      for (let i = 0; i < 240; i++) {
        await new Promise((r) => setTimeout(r, 2000));
        const s = await api<Job>(`/v1/jobs/${j.job_id}`);
        if (s.status === "running" || s.status === "queued") continue;
        const t = s.result?.linked_track;
        const lost = t && (s.result?.tracks ?? []).some((x) => x.first_frame_index > t.last_frame_index);
        setPhase(s.status === "done" && t
          ? { k: "done", ok: true, text: `Followed in frames ${t.first_frame_index}–${t.last_frame_index}${lost ? ", until it left view" : ""}. Linked to this case.` }
          : { k: "done", ok: false, text: s.error ?? s.result?.message ?? "SAM did not find it from this box. Try a tighter box, or another frame." });
        invalidate(`/v1/cases/${caseId}`);
        invalidate(`/v1/media/${mediaId}`);
        return;
      }
      setPhase({ k: "done", ok: false, text: "Still running after 8 minutes. The result will appear in the case when it finishes." });
    } catch (e) {
      setPhase({ k: "done", ok: false, text: e instanceof Error ? e.message : String(e) });
    } finally {
      setBox(null);
    }
  }
  const drawing = phase.k === "draw";
  return (
    <div className="tp">
      <div ref={wrap} className="tp-wrap" data-draw={drawing || undefined}
        onPointerDown={(e) => { if (!drawing) return; start.current = pct(e); setBox([...start.current, ...start.current]); e.currentTarget.setPointerCapture(e.pointerId); }}
        onPointerMove={(e) => { if (!drawing || !start.current) return; const [x, y] = pct(e), [x0, y0] = start.current;
          setBox([Math.min(x0, x), Math.min(y0, y), Math.max(x0, x), Math.max(y0, y)]); }}
        onPointerUp={() => { if (!drawing || !start.current || !box) return; start.current = null;
          if (box[2] - box[0] < 1 || box[3] - box[1] < 1) { setBox(null); return; } void send(box); }}
        onKeyDown={(e) => { if (e.key === "Escape" && drawing) { setPhase({ k: "idle" }); setBox(null); } }}>
        {children}
        {box && <span className="tp-box" style={{ left: `${box[0]}%`, top: `${box[1]}%`, width: `${box[2] - box[0]}%`, height: `${box[3] - box[1]}%` }} aria-hidden="true" />}
        {drawing && !box && <span className="tp-hint">Drag a box around the parcel</span>}
      </div>
      <div className="tp-bar">
        {phase.k === "idle" || phase.k === "done" ? (
          <button type="button" className="sp-btn sp-btn-sm tp-go" onClick={() => setPhase({ k: "draw" })} data-testid="track-parcel">
            <svg viewBox="0 0 14 14" aria-hidden="true"><rect x="2" y="3" width="10" height="8" rx="1" /><path d="M5 1.5v3M9 1.5v3M5 9.5v3M9 9.5v3" /></svg>
            {phase.k === "done" && phase.ok ? "Track again" : "Track this parcel"}
          </button>
        ) : phase.k === "draw" ? (
          <button type="button" className="sp-btn sp-btn-sm sp-btn-ghost" onClick={() => { setPhase({ k: "idle" }); setBox(null); }}>Cancel</button>
        ) : null}
        <span className="tp-chip" data-state={phase.k} role="status">
          {phase.k === "draw" ? "SAM 3.1 · draw a box on this frame"
            : phase.k === "run" ? "SAM 3.1 · following it through the clip…"
              : phase.k === "done" ? phase.text : "SAM 3.1 follows the parcel you box, both ways from this frame"}
        </span>
      </div>
    </div>
  );
}
