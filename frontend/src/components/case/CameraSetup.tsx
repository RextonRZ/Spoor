"use client";
/**
 * The hub's camera setup on the Blender wide shot (Rexton 3 Nov: "a toggle to view the CCTV and camera setup; click a
 * camera to see what it sees, cinematic, easy to navigate"). Every camera sits where it is mounted; hovering one lights
 * the floor it covers (its frustum met with the floor, computed in Blender: assets/tour/overview_render.py). Clicking one
 * flies into it: the hub zooms toward the camera and its own view opens over it. Esc, or "Back to the hub", flies out.
 * The view is the camera's own recording (or its still, for the close-up cameras); nothing is generated.
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import { HUB } from "@/lib/hub";
import "./hubtour.css";

interface Overview { size: [number, number]; cameras: { id: string; at: [number, number]; floor: [number, number][]; height_m: number }[] }
type Cam = { id: string; osd_label: string; question: string; mount: string; height_m: number };
const CAMS = HUB.cameras as unknown as Cam[];
const CLOSE: Record<string, string> = { UNLOAD: "Unload close-up", TUNNEL: "Tunnel close-up", CHUTE: "Chute close-up", CAGE_W: "Cage close-up",
  STORE: "Store door close-up", DOCK: "Dock close-up" };
const sentence = (s: string) => s.toLowerCase().replace(/^\w/, (x) => x.toUpperCase());
const nameOf = (id: string) => id.startsWith("CHK_") ? CLOSE[id.slice(4)] ?? id : `${id.replace("_", " ")} · ${sentence(CAMS.find((c) => c.id === id)?.osd_label ?? "")}`;
// the plan's internal zone ids ("BLIND_NW") mean nothing on screen
const ask = (q: string) => q.replace(/\s*\([^)]*BLIND_[^)]*\)/g, "").replace(/\bBLIND_\w+\b/g, "a blind spot");
const REDUCED = () => typeof window !== "undefined" && matchMedia("(prefers-reduced-motion: reduce)").matches;

/** used: camera id -> the step numbers it shows on this case's route (empty on the Cameras page) */
export function CameraSetup({ used = {} }: { used?: Record<string, number[]> }) {
  const [ov, setOv] = useState<Overview | null | "none">(null);
  const [hover, setHover] = useState<string | null>(null);
  const [open, setOpen] = useState<string | null>(null);
  const [phase, setPhase] = useState<"idle" | "in" | "view" | "out">("idle");

  useEffect(() => {
    let live = true;
    fetch("/tour/overview.json").then((r) => r.ok ? r.json() : "none").then((j) => { if (live) setOv(j); }).catch(() => live && setOv("none"));
    return () => { live = false; };
  }, []);
  const o = ov && ov !== "none" ? ov : null;
  // the cameras on this route first, then the rest in their numbering
  const list = useMemo(() => (o?.cameras ?? []).filter((c) => CAMS.some((h) => h.id === c.id))
    .sort((a, b) => Number(!used[a.id]) - Number(!used[b.id]) || a.id.localeCompare(b.id)), [o, used]);

  const fly = useCallback((id: string) => {
    if (open && open !== id) { setOpen(id); return; }        // already inside: switch cameras in place
    setOpen(id); setHover(null);
    if (REDUCED()) { setPhase("view"); return; }
    setPhase("in"); window.setTimeout(() => setPhase("view"), 380);
  }, [open]);
  const out = useCallback(() => {
    if (REDUCED()) { setOpen(null); setPhase("idle"); return; }
    setPhase("out"); window.setTimeout(() => { setOpen(null); setPhase("idle"); }, 360);
  }, []);
  useEffect(() => {
    if (!open) return;
    const k = (e: KeyboardEvent) => {
      if (e.key === "Escape") out();
      const i = list.findIndex((c) => c.id === open);
      if (e.key === "ArrowRight") fly(list[(i + 1) % list.length].id);
      if (e.key === "ArrowLeft") fly(list[(i - 1 + list.length) % list.length].id);
    };
    window.addEventListener("keydown", k); return () => window.removeEventListener("keydown", k);
  }, [open, list, out, fly]);

  if (ov === "none") return <p className="ht-none">The camera setup has not been exported yet.</p>;
  const sel = open ?? hover;
  const info = sel ? CAMS.find((c) => c.id === sel) : null;
  const at = open ? o?.cameras.find((c) => c.id === open)?.at : null;
  const idx = open ? list.findIndex((c) => c.id === open) : -1;

  return (
    <>
      <div className="ht-main">
        <div className="hc-stage" data-phase={phase} style={o ? { aspectRatio: `${o.size[0]} / ${o.size[1]}` } : undefined}>
          <div className="hc-world" style={at ? { transformOrigin: `${at[0] * 100}% ${at[1] * 100}%` } : undefined}>
            {/* eslint-disable-next-line @next/next/no-img-element -- the Blender render of the hub model */}
            {o && <img className="hc-img" src="/tour/overview.jpg" alt="The hub model from above, rendered in Blender" />}
            {o && (
              <svg className="hc-floor" viewBox="0 0 1 1" preserveAspectRatio="none" aria-hidden>
                {list.map((c) => (
                  <polygon key={c.id} points={c.floor.map((p) => p.join(",")).join(" ")} data-on={sel === c.id ? "" : undefined} data-used={used[c.id] ? "" : undefined} />
                ))}
              </svg>
            )}
            {list.map((c) => (
              <button key={c.id} type="button" className="hc-cam" data-close={c.id.startsWith("CHK_") ? "" : undefined} data-used={used[c.id] ? "" : undefined}
                data-on={sel === c.id ? "" : undefined} style={{ left: `${c.at[0] * 100}%`, top: `${c.at[1] * 100}%` }} tabIndex={open ? -1 : 0}
                onMouseEnter={() => setHover(c.id)} onMouseLeave={() => setHover((h) => h === c.id ? null : h)} onFocus={() => setHover(c.id)} onBlur={() => setHover(null)}
                onClick={() => fly(c.id)} aria-label={`Look through ${nameOf(c.id)}`}>
                <svg viewBox="0 0 24 24" aria-hidden><path d="M4 8h11a1 1 0 0 1 1 1v6a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V9a1 1 0 0 1 1-1zM16 11l5-3v8l-5-3" /></svg>
              </button>
            ))}
          </div>
          {!o && <span className="ht-wait" />}

          {open && (
            <div className="hc-view" role="dialog" aria-label={`The view from ${nameOf(open)}`}>
              {open.startsWith("CHK_")
                // eslint-disable-next-line @next/next/no-img-element -- the close-up camera's own frame
                ? <img key={open} className="hc-feed" src={`/cameras/${open}.jpg`} alt={`What ${nameOf(open)} sees`} />
                : <video key={open} className="hc-feed" src={`/cameras/${open}.mp4`} poster={`/cameras/${open}.jpg`} autoPlay muted loop playsInline aria-label={`What ${nameOf(open)} sees`} />}
              {/* only the way back sits on the picture: the camera's own time and name (its corners) stay readable */}
              <div className="hc-view-top">
                <button type="button" className="hc-x" onClick={out}><svg viewBox="0 0 24 24" aria-hidden><path d="M15 5l-7 7 7 7" /></svg>Back to the hub</button>
              </div>
              <div className="hc-view-nav">
                <button type="button" className="hc-nav" onClick={() => fly(list[(idx - 1 + list.length) % list.length].id)} aria-label="Previous camera">
                  <svg viewBox="0 0 24 24" aria-hidden><path d="M15 5l-7 7 7 7" /></svg></button>
                <span className="hc-count">{idx + 1} / {list.length}</span>
                <button type="button" className="hc-nav" onClick={() => fly(list[(idx + 1) % list.length].id)} aria-label="Next camera">
                  <svg viewBox="0 0 24 24" aria-hidden><path d="M9 5l7 7-7 7" /></svg></button>
              </div>
            </div>
          )}
        </div>
        <div className="hc-legend" aria-hidden>
          <span><i className="hc-k-wide" />Wide camera</span><span><i className="hc-k-close" />Close-up camera</span>
          {Object.keys(used).length > 0 && <span><i className="hc-k-used" />On this parcel&apos;s route</span>}
          <span className="hc-hint">Hover a camera to see what it covers. Click to look through it.</span>
        </div>
      </div>

      <aside className="ht-card hc-card" aria-live="polite">
        {info ? (
          <>
            <div className="ht-card-top"><span className="ht-n">{info.id.startsWith("CHK_") ? "Close-up camera" : "Wide camera"}</span>
              {used[info.id] && <span className="ht-chip" data-tone="seen">Step {used[info.id].join(", ")}</span>}</div>
            <h3 className="ht-title">{nameOf(info.id)}</h3>
            <p className="ht-sub">{ask(info.question)}</p>
            <p className="ht-meta">{info.mount} · {info.height_m} m up</p>
            {!open && <button type="button" className="ht-btn ht-btn-main hc-look" onClick={() => fly(info.id)}>Look through it</button>}
          </>
        ) : (
          <>
            <span className="ht-n">{list.length} cameras</span>
            <h3 className="ht-title">Every camera, where it is mounted</h3>
            <ul className="hc-list">
              {list.map((c) => (
                <li key={c.id}>
                  <button type="button" className="hc-li" data-used={used[c.id] ? "" : undefined} onMouseEnter={() => setHover(c.id)} onMouseLeave={() => setHover(null)}
                    onClick={() => fly(c.id)}>{c.id.replace("_", " ").replace("CHK ", "")}</button>
                </li>
              ))}
            </ul>
          </>
        )}
      </aside>
    </>
  );
}
