"use client";
/**
 * The case, as the landing page tells it, from this case's live evidence only: the doorway camera's real clip on the
 * left with SAM 3.1's own box following the carton (every box it drew on that track, at its video time), the hub plan
 * on the right with the parcel's path and where it is at the chosen moment, and the moments in order below on the
 * landing page's time rail (the same lp-mo classes). Picking a moment cuts the clip to it and moves the plan's marker.
 *
 * Moments, all from the verifier's facts and the case's records: first seen carrying it, last seen at the door, carried
 * in, someone came out without it, and either the truck record that says it left (while it is still inside) or the
 * end of the recording. Frames for in and out are shown just before going in and just after coming out (engine facts).
 * The agents' own ideas sit behind a toggle, each with the one check that decided it: their wording is never a finding.
 *
 * Motion: the clip plays a short window around the moment (ease is the footage's own); the frame and marker change on
 * a click with a 140 ms crossfade only. Reduced motion: no autoplay, the clip rests on the moment's frame.
 */
import { useEffect, useMemo, useRef, useState } from "react";
import { api, signedUrl } from "@/lib/api";
import { HYPOTHESIS_WORDS, type InsideFacts, type InvestigationView } from "@/lib/answer";
import type { JourneyObject, XY } from "@/lib/journey";
import { prefersReducedMotion } from "@/lib/motion";
import { hms } from "@/lib/words";
import HubPlan from "@/components/plan/HubPlan";
import "@/components/landing/landing.css";
import "./casestory.css";

const CHECK_WORDS: Record<string, string> = { stayed_in_area: "stayed inside", exit: "left through a door", transition: "moved between areas",
  transfer: "handed over", parcel_match: "same parcel", order: "order of sightings" };

interface Moment { key: string; iso: string; text: string; xy: XY; tone?: "bad"; from?: string; /** the measured time, when the frame shown is a moment off it */ at?: string }

/** one still per moment, fetched up front (the rail's thumbnails and the clip's poster) */
function useStills(mediaId: string, moments: Moment[]): Record<string, string> {
  const [urls, setUrls] = useState<Record<string, string>>({});
  const key = moments.map((m) => m.iso).join();
  useEffect(() => {
    let live = true;
    moments.forEach((m) => {
      api<{ frame_url: string }>(`/v1/media/${mediaId}/frame-at?time=${encodeURIComponent(m.iso)}`)
        .then((r) => live && setUrls((u) => ({ ...u, [m.key]: signedUrl(r.frame_url) }))).catch(() => {});
    });
    return () => { live = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- the moments are fixed by their times
  }, [mediaId, key]);
  return urls;
}

function usePlayback(mediaId: string): string | null {
  const [url, setUrl] = useState<{ k: string; u: string } | null>(null);
  useEffect(() => {
    let live = true;
    api<{ url: string }>(`/v1/media/${mediaId}/playback`).then((r) => live && setUrl({ k: mediaId, u: signedUrl(r.url) })).catch(() => {});
    return () => { live = false; };
  }, [mediaId]);
  return url?.k === mediaId ? url.u : null;
}

export function CaseStory({ caseId, inside, view, journey, truck }: {
  caseId: string; inside: InsideFacts; view: InvestigationView; journey?: JourneyObject;
  /** the records' "loaded on truck" (the cage's gate read), if any */
  truck?: { t: string; door: string | null } | null;
}) {
  void caseId;
  const doorMs = Date.parse(inside.iso.door_at);
  const isoAt = (pts: number) => new Date(doorMs + (pts - inside.door_pts_ms)).toISOString();
  const vt = (iso: string) => (inside.door_pts_ms + (Date.parse(iso) - doorMs)) / 1000; // the clip's own time
  const area = inside.area_xy as XY;
  const door = inside.door_xy as XY;
  // where the tracked carton stood on the floor (the journey's observed points), nearest a time
  const floorAt = (iso: string): XY => {
    const pts = (journey?.segments ?? []).flatMap((s) => (s.kind === "observed" ? s.points : [])).filter((p) => p.xy);
    if (!pts.length) return door;
    const t = Date.parse(iso);
    return pts.reduce((a, b) => (Math.abs(Date.parse(b.t) - t) < Math.abs(Date.parse(a.t) - t) ? b : a)).xy as XY;
  };
  // "14:32:32" (the verifier's measured time) on the door moment's date and offset
  const clockIso = (hmsText: string) => inside.iso.door_at.replace(/T\d{2}:\d{2}:\d{2}(\.\d+)?/, `T${hmsText}.000`);
  const truckInside = truck && Date.parse(truck.t) > Date.parse(inside.iso.carried_in_at) && Date.parse(truck.t) < Date.parse(inside.iso.until);
  const firstIso = inside.track_px.length ? isoAt(inside.track_px[0][0]) : inside.iso.door_at;
  const moments: Moment[] = useMemo(() => [
    ...(inside.track_px.length > 1 ? [{ key: "first", iso: firstIso, text: `Seen on ${inside.camera}, carried toward the store`, xy: floorAt(firstIso), from: firstIso }] : []),
    { key: "door", iso: inside.iso.door_at, text: "Last seen at the store door", xy: door, from: firstIso },
    { key: "in", iso: inside.iso.carried_in_at, at: clockIso(inside.carried_in_at), text: "Carried in", xy: area },
    ...inside.came_out_empty.map((t, i) => ({ key: `out${i}`, iso: inside.iso[`came_out_${i}`], at: clockIso(t), text: "Someone came out without it", xy: area })),
    truckInside
      ? { key: "truck", iso: truck!.t, text: `Record says loaded on truck ${truck!.door ?? ""}. Still inside`.replace("  ", " "), xy: area, tone: "bad" as const }
      : { key: "end", iso: inside.iso.until, text: "Recording ends, not seen coming out", xy: area },
    // eslint-disable-next-line react-hooks/exhaustive-deps -- fixed by the facts
  ], [inside, truck]);
  const [sel, setSel] = useState("door");
  const cur = moments.find((m) => m.key === sel) ?? moments[0];
  const stills = useStills(inside.media_id, moments);
  const clip = usePlayback(inside.media_id);
  const video = useRef<HTMLVideoElement>(null);
  const boxEl = useRef<SVGRectElement>(null);
  const [wh, track] = [inside.frame_wh_px, inside.track_px];
  const reduced = typeof window !== "undefined" && prefersReducedMotion();

  // play a short window around the chosen moment (the first sighting plays up to the door), resting on the moment
  useEffect(() => {
    const v = video.current;
    if (!v || !clip) return;
    const at = vt(cur.iso), from = cur.from ? vt(cur.from) : at - 1.5, to = cur.key === "first" ? vt(inside.iso.door_at) : at + 2.5;
    const start = () => {
      v.currentTime = reduced ? at : Math.max(0, from);
      if (!reduced) v.play().catch(() => {});
    };
    if (v.readyState >= 1) start(); else v.addEventListener("loadedmetadata", start, { once: true });
    const loop = () => { if (v.currentTime >= to) { v.currentTime = Math.max(0, from); } };
    v.addEventListener("timeupdate", loop);
    return () => { v.removeEventListener("timeupdate", loop); v.removeEventListener("loadedmetadata", start); };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- re-cut when the moment or the clip changes
  }, [cur.key, clip]);

  // SAM's box follows the carton: the box it drew at this video time (within one frame), hidden otherwise
  useEffect(() => {
    const v = video.current;
    if (!v) return;
    let id = 0;
    const draw = () => {
      const ms = v.currentTime * 1000;
      const near = track.length ? track.reduce((a, b) => (Math.abs(b[0] - ms) < Math.abs(a[0] - ms) ? b : a)) : null;
      const r = boxEl.current;
      if (r) {
        const on = near && Math.abs(near[0] - ms) <= 70;
        r.style.opacity = on ? "1" : "0";
        if (on) {
          r.setAttribute("x", String(near[1] - 6)); r.setAttribute("y", String(near[2] - 6));
          r.setAttribute("width", String(near[3] - near[1] + 12)); r.setAttribute("height", String(near[4] - near[2] + 12));
        }
      }
      id = requestAnimationFrame(draw);
    };
    id = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(id);
  }, [track, clip]);

  const toPlan = cur.key === "in" || cur.key.startsWith("out") || cur.key === "truck" || cur.key === "end";
  return (
    <div className="cs">
      <div className="cs-stage">
        <figure className="cs-video" style={{ aspectRatio: `${wh[0]} / ${wh[1]}` }}>
          {clip ? (
            <video ref={video} src={clip} poster={stills[cur.key]} muted playsInline preload="auto" aria-label={`${inside.camera} at ${hms(cur.iso)}: ${cur.text}`} />
          ) : stills[cur.key] ? (
            // eslint-disable-next-line @next/next/no-img-element -- a signed CCTV frame from the API, shown as it is
            <img src={stills[cur.key]} alt={`${inside.camera} at ${hms(cur.iso)}: ${cur.text}`} />
          ) : <span className="an-skel cs-skel" aria-busy="true" />}
          <svg viewBox={`0 0 ${wh[0]} ${wh[1]}`} aria-hidden>
            <rect ref={boxEl} rx={4} fill="none" stroke="#4ade80" strokeWidth={2.5} vectorEffect="non-scaling-stroke" style={{ opacity: 0 }} />
          </svg>
          <figcaption data-tone={cur.tone}>
            <b>{inside.camera}</b><span>{cur.text}</span>
          </figcaption>
          <span className="cs-sam">Box: SAM 3.1 tracking</span>
        </figure>
        <figure className="cs-plan">
          <HubPlan label={`The parcel's path; now: ${cur.text}`} journey={journey} quiet
            story={{ area: inside.area_polygon as XY[], from: door, to: area }}
            marker={{ xy: toPlan ? area : cur.xy, kind: cur.tone ? "unknown" : "observed", label: hms(cur.iso) }}
            litCameras={[inside.camera.replace(" ", "_")]} legend={false} fit="contain" minHeight={0} />
          <figcaption>{inside.place}</figcaption>
        </figure>
      </div>

      <ol className="lp-mo cs-mo" aria-label="The moments, in order">
        {moments.map((m, i) => {
          const nx = moments[i + 1];
          const when = (x: Moment) => x.at ?? x.iso;
          const gap = nx ? Math.round((Date.parse(when(nx)) - Date.parse(when(m))) / 1000) : null;
          return (
            <li key={m.key} className="lp-mo-item" style={{ "--i": i } as React.CSSProperties} data-tone={m.tone}>
              <div className="lp-mo-rail" aria-hidden="true">
                <span className="lp-mo-dot" />
                <span className="lp-mo-time">{hms(m.at ?? m.iso)}</span>
                {gap !== null && gap > 0 && <span className="lp-mo-gap">+{gap} s</span>}
              </div>
              <button type="button" className="lp-mo-btn" aria-pressed={m.key === cur.key} onClick={() => setSel(m.key)}
                aria-label={`${hms(m.at ?? m.iso)}: ${m.text}`}>
                <span className={`lp-mo-frame${m.key === cur.key ? " is-on" : ""}`}>
                  {/* eslint-disable-next-line @next/next/no-img-element -- a signed CCTV frame from the API */}
                  {stills[m.key] && <img src={stills[m.key]} alt="" loading="lazy" decoding="async" />}
                  <span className="lp-mo-cam">{inside.camera}</span>
                </span>
              </button>
              <p className="lp-mo-cap"><span className="lp-mo-n">{String(i + 1).padStart(2, "0")}</span>{m.text}</p>
            </li>
          );
        })}
      </ol>

      {view.hypotheses.length > 0 && (
        <details className="an-more ia-ideas">
          <summary>Agents&apos; ideas ({view.hypotheses.length})<span>not evidence</span></summary>
          <ul>
            {view.hypotheses.map((h, i) => {
              const decided = h.tested?.find((t) => t.verdict === h.status) ?? h.tested?.[0];
              return (
                <li key={i}>
                  <span className="an-chip" data-tone={h.status === "supported" ? "ok" : h.status === "contradicted" ? undefined : "plain"}>
                    {HYPOTHESIS_WORDS[h.status] ?? h.status}</span>
                  <q>{h.agent_wording}</q>
                  <small>{decided ? `Tested: ${CHECK_WORDS[decided.kind] ?? decided.kind}` : "Tested: nothing new"}</small>
                </li>
              );
            })}
          </ul>
        </details>
      )}
    </div>
  );
}
