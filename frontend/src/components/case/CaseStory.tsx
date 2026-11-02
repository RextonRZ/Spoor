"use client";
/**
 * The case, as the landing page tells it, from this case's live evidence only: the doorway camera's real clip on the
 * left with SAM 3.1's own box following the carton (every box it drew on that track, at its video time), the hub plan
 * on the right with the parcel's path and where it is at the chosen moment, and the moments in order below on the
 * landing page's time rail (the same lp-mo classes). Picking a moment cuts the clip to it and moves the plan's marker.
 *
 * Moments, all from the verifier's facts and the case's records, each on the best camera that has it (a close-up
 * checkpoint camera first): taken out of its cage without a scan (the live alert's outline), last seen at the store
 * door (the wide camera, SAM's track), carried in past the scan-in post and someone came out without it (the door's
 * close-up), and either the truck record that says it left (the dock's close-up, while it is still inside) or the end
 * of the recording. The hero opens on "carried in".
 * The agents' own ideas sit behind a toggle, each with the one check that decided it: their wording is never a finding.
 *
 * Motion: the clip plays a short window around the moment (ease is the footage's own); the frame and marker change on
 * a click with a 140 ms crossfade only. Reduced motion: no autoplay, the clip rests on the moment's frame.
 */
import { useEffect, useMemo, useRef, useState } from "react";
import { api, previewUrl, signedUrl, useResource } from "@/lib/api";
import { camId } from "@/lib/hub";
import { pointsIn, useBestView, useContours } from "@/lib/focus";
import type { MediaRow, Site } from "@/lib/types";
import { HYPOTHESIS_WORDS, type InsideFacts, type InvestigationView } from "@/lib/answer";
import type { JourneyObject, XY } from "@/lib/journey";
import { prefersReducedMotion } from "@/lib/motion";
import { hms } from "@/lib/words";
import HubPlan from "@/components/plan/HubPlan";
import "@/components/landing/landing.css";
import "./casestory.css";

const CHECK_WORDS: Record<string, string> = { stayed_in_area: "stayed inside", exit: "left through a door", transition: "moved between areas",
  transfer: "handed over", parcel_match: "same parcel", order: "order of sightings" };

interface Moment { key: string; iso: string; text: string; xy: XY; tone?: "bad"; from?: string; /** the measured time, when the frame shown is a moment off it */ at?: string;
  /** the clip that shows it and its camera; box: an outline at this moment (frame pixels) */
  media: string; cam: string; box?: number[] | null }
interface Alert { at_utc: string; camera_id: string; media_id: string; frame_index: number; track_id: string; box_px: number[] | null; candidates: { waybill: string }[] }

const camWords = (c: string) => c.replace(/^cam_/, "").replaceAll("_", " ");

/** one still per moment, each from its own clip, fetched up front (the rail's thumbnails and the clip's poster) */
function useStills(moments: Moment[]): Record<string, string> {
  const [urls, setUrls] = useState<Record<string, string>>({});
  const key = moments.map((m) => `${m.media}@${m.iso}`).join();
  useEffect(() => {
    let live = true;
    moments.forEach((m) => {
      api<{ frame_url: string }>(`/v1/media/${m.media}/frame-at?time=${encodeURIComponent(m.iso)}`)
        .then((r) => live && setUrls((u) => ({ ...u, [m.key]: previewUrl(r.frame_url, 1280) }))).catch(() => {});
    });
    return () => { live = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- the moments are fixed by their clips and times
  }, [key]);
  return urls;
}

function usePlayback(mediaId: string): { url: string; start: number } | null {
  const [got, setGot] = useState<{ k: string; url: string; start: number } | null>(null);
  useEffect(() => {
    let live = true;
    api<{ url: string; start_utc: string | null }>(`/v1/media/${mediaId}/playback`)
      .then((r) => live && setGot({ k: mediaId, url: signedUrl(r.url), start: r.start_utc ? Date.parse(r.start_utc) : NaN })).catch(() => {});
    return () => { live = false; };
  }, [mediaId]);
  return got?.k === mediaId ? got : null;
}

/** the clip of a camera that has this moment (a close-up checkpoint camera if one does) */
function useClipFor(siteId: string | undefined) {
  const media = useResource<MediaRow[]>(siteId ? `/v1/sites/${siteId}/media` : null);
  return (hub: string, iso: string) => (media.data ?? []).find((m) => m.media.camera_id && camId.toHub(m.media.camera_id) === hub
    && !m.purged && m.coverage.some((c) => Date.parse(c.start_utc) <= Date.parse(iso) && Date.parse(iso) <= Date.parse(c.end_utc)))?.media.media_id;
}

export function CaseStory({ caseId, inside, view, journey, truck, strip = true }: {
  caseId: string; inside: InsideFacts; view: InvestigationView; journey?: JourneyObject; strip?: boolean;
  /** the records' "loaded on truck" (the cage's gate read), if any */
  truck?: { t: string; door: string | null } | null;
}) {
  void caseId;
  const doorMs = Date.parse(inside.iso.door_at);
  const isoAt = (pts: number) => new Date(doorMs + (pts - inside.door_pts_ms)).toISOString();
  const sites = useResource<Site[]>("/v1/sites");
  const siteId = sites.data?.[0]?.site_id;
  const clipFor = useClipFor(siteId);
  const alerts = useResource<Alert[]>(siteId ? `/v1/sites/${siteId}/alerts` : null);
  const waybill = view.objects[0]?.label?.split(" ").at(-1) ?? "";
  const pick = (alerts.data ?? []).find((a) => a.candidates.length === 1 && a.candidates[0].waybill === waybill);
  // show the pick where the carton is wholly in the picture (the alert's frame is where it leaves the view)
  const pickView = useBestView(pick?.media_id, pick?.track_id, pick?.frame_index);
  const pickIso = pick ? new Date(Date.parse(pick.at_utc) + (pickView?.dms ?? 0)).toISOString() : "";
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
  const wide = inside.camera.replace(" ", "_");
  const best = (iso: string, hubs: string[]) => {  // the first of these cameras with a clip of the moment
    for (const h of hubs) { const m = clipFor(h, iso); if (m) return { media: m, cam: h }; }
    return { media: inside.media_id, cam: wide };
  };
  const moments: Moment[] = useMemo(() => [
    ...(pick ? [{ key: "pick", iso: pickIso, at: pick.at_utc, text: "Taken out of its cage, no scan", xy: floorAt(firstIso), media: pick.media_id,
      cam: camId.toHub(pick.camera_id), box: pickView?.box ?? pick.box_px, tone: "bad" as const }]
      : inside.track_px.length > 1 ? [{ key: "first", iso: firstIso, text: `Seen on ${inside.camera}, carried toward the store`, xy: floorAt(firstIso),
        from: firstIso, media: inside.media_id, cam: wide }] : []),
    { key: "door", iso: inside.iso.door_at, text: "Last seen at the store door", xy: door, from: firstIso, media: inside.media_id, cam: wide },
    { key: "in", iso: inside.iso.carried_in_at, at: clockIso(inside.carried_in_at), text: "Carried in, past the scan-in post", xy: area,
      ...best(inside.iso.carried_in_at, ["CHK_STORE", wide]) },
    ...inside.came_out_empty.map((t, i) => ({ key: `out${i}`, iso: inside.iso[`came_out_${i}`], at: clockIso(t), text: "Someone came out without it",
      xy: area, ...best(inside.iso[`came_out_${i}`], ["CHK_STORE", wide]) })),
    truckInside
      ? { key: "truck", iso: truck!.t, text: `Record says loaded on truck ${truck!.door ?? ""}. Still inside`.replace("  ", " "), xy: area,
        tone: "bad" as const, ...best(truck!.t, ["CHK_DOCK", wide]) }
      : { key: "end", iso: inside.iso.until, text: "Recording ends, not seen coming out", xy: area, media: inside.media_id, cam: wide },
    // eslint-disable-next-line react-hooks/exhaustive-deps -- fixed by the facts and the clips on site
  ], [inside, truck, pick, pickIso, pickView, clipFor]);
  const [sel, setSel] = useState("in");
  const cur = moments.find((m) => m.key === sel) ?? moments[0];
  const stills = useStills(moments);
  const play = usePlayback(cur.media);
  const clip = play?.url ?? null;
  // the clip's own time of a moment, from the clip's recorded start (each moment may be a different clip)
  const vt = (iso: string) => (Number.isFinite(play?.start) ? (Date.parse(iso) - play!.start) / 1000 : 0);
  const video = useRef<HTMLVideoElement>(null);
  const boxEl = useRef<SVGRectElement>(null);
  const [wh, track] = [inside.frame_wh_px, inside.track_px];
  // a close-up moment SAM followed in the journey reel (the carried carton at the store door): loop where SAM saw the
  // carton and draw its own outline, instead of a moment with nothing marked
  const reel = useResource<{ chapters: { media_id: string | null; track_id: string | null }[] }>(`/v1/cases/${caseId}/journey-reel`);
  const carry = cur.media !== inside.media_id ? reel.data?.chapters.find((c) => c.media_id === cur.media && c.track_id) : undefined;
  const carryBoxes = useResource<{ boxes: number[][] }>(carry ? `/v1/media/${carry.media_id}/tracks/${carry.track_id}/boxes` : null).data?.boxes ?? [];
  const carryEdges = useContours(carry?.media_id, carry?.track_id);
  const polyEl = useRef<SVGPolygonElement>(null);
  const reduced = typeof window !== "undefined" && prefersReducedMotion();

  // play a short window around the chosen moment (the first sighting plays up to the door), resting on the moment
  useEffect(() => {
    const v = video.current;
    if (!v || !clip) return;
    const cb = carryBoxes.length > 4 ? [carryBoxes[0][1] / 1000, carryBoxes[carryBoxes.length - 1][1] / 1000 + 0.6] : null;
    const at = vt(cur.iso), from = cb ? cb[0] : cur.from ? vt(cur.from) : at - 1.5, to = cb ? cb[1] : cur.key === "first" ? vt(inside.iso.door_at) : at + 2.5;
    const start = () => {
      v.currentTime = reduced ? at : Math.max(0, from);
      if (!reduced) v.play().catch(() => {});
    };
    if (v.readyState >= 1) start(); else v.addEventListener("loadedmetadata", start, { once: true });
    const loop = () => { if (v.currentTime >= to) { v.currentTime = Math.max(0, from); } };
    v.addEventListener("timeupdate", loop);
    return () => { v.removeEventListener("timeupdate", loop); v.removeEventListener("loadedmetadata", start); };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- re-cut when the moment or the clip changes
  }, [cur.key, clip, play?.start, carryBoxes.length]);

  // SAM's box follows the carton: the box it drew at this video time (within one frame), hidden otherwise
  useEffect(() => {
    const v = video.current;
    if (!v) return;
    let id = 0;
    const own = cur.media === inside.media_id;
    const pickAt = cur.box && play ? (Date.parse(cur.iso) - play.start) : NaN;
    const draw = () => {
      const ms = v.currentTime * 1000;
      const cnear = carryBoxes.length ? carryBoxes.reduce((a, b) => (Math.abs(b[1] - ms) < Math.abs(a[1] - ms) ? b : a)) : null;
      const near = own && track.length ? track.reduce((a, b) => (Math.abs(b[0] - ms) < Math.abs(a[0] - ms) ? b : a))
        : cnear ? cnear.slice(1)
        : cur.box && Number.isFinite(pickAt) && Math.abs(ms - pickAt) < 400 ? [ms, ...cur.box] : null;
      const edge = cnear && Math.abs(cnear[1] - ms) <= 70 ? carryEdges.get(cnear[0]) : undefined;
      if (polyEl.current) {
        polyEl.current.style.opacity = edge ? "1" : "0";
        if (edge) polyEl.current.setAttribute("points", pointsIn(edge));
      }
      const r = boxEl.current;
      if (r && edge) r.style.opacity = "0";
      else if (r) {
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
    // eslint-disable-next-line react-hooks/exhaustive-deps -- redrawn per clip and moment
  }, [track, clip, cur.key, carryBoxes, carryEdges]);

  // SAM's box on a moment's thumbnail: the alert's outline at the pick, the wide camera's track at its own moments
  const thumbBox = (m: Moment): number[] | null => {
    if (m.box) return m.box;
    if (m.media !== inside.media_id || !track.length) return null;
    const ms = inside.door_pts_ms + (Date.parse(m.iso) - doorMs);
    const near = track.reduce((a, b) => (Math.abs(b[0] - ms) < Math.abs(a[0] - ms) ? b : a));
    return Math.abs(near[0] - ms) <= 400 ? near.slice(1) : null;
  };
  // focus: scale the frame (and its outline) about SAM's box so the carton fills the thumbnail, never past 3x
  const zoomOn = (b: number[] | null): React.CSSProperties | undefined => {
    if (!b) return undefined;
    const s = Math.min(3, Math.max(1, Math.min(wh[0] / ((b[2] - b[0]) * 4), wh[1] / ((b[3] - b[1]) * 3.2))));
    return { transform: `scale(${s.toFixed(2)})`, transformOrigin: `${((b[0] + b[2]) / 2 / wh[0]) * 100}% ${((b[1] + b[3]) / 2 / wh[1]) * 100}%` };
  };
  const toPlan = cur.key === "in" || cur.key.startsWith("out") || cur.key === "truck" || cur.key === "end";
  return (
    <div className="cs">
      <div className="cs-stage">
        <figure className="cs-video" style={{ aspectRatio: `${wh[0]} / ${wh[1]}` }}>
          {clip ? (
            <video ref={video} src={clip} poster={stills[cur.key]} muted playsInline preload="auto" aria-label={`${camWords(cur.cam)} at ${hms(cur.iso)}: ${cur.text}`} />
          ) : stills[cur.key] ? (
            // eslint-disable-next-line @next/next/no-img-element -- a signed CCTV frame from the API, shown as it is
            <img src={stills[cur.key]} alt={`${camWords(cur.cam)} at ${hms(cur.iso)}: ${cur.text}`} />
          ) : <span className="an-skel cs-skel" aria-busy="true" />}
          <svg viewBox={`0 0 ${wh[0]} ${wh[1]}`} aria-hidden>
            <rect ref={boxEl} rx={4} className="cs-hero-mark" style={{ opacity: 0 }} />
            <polygon ref={polyEl} className="cs-hero-edge" style={{ opacity: 0 }} />
          </svg>
          <figcaption data-tone={cur.tone}>
            <b>{camWords(cur.cam)}</b><span>{cur.text}</span>
          </figcaption>
          {(cur.media === inside.media_id || cur.box || carryBoxes.length > 0) && <span className="cs-sam">Outline: SAM 3.1 tracking</span>}
        </figure>
        <figure className="cs-plan">
          <HubPlan label={`The parcel's path; now: ${cur.text}`} journey={journey} quiet
            story={{ area: inside.area_polygon as XY[], from: door, to: area }}
            marker={{ xy: toPlan ? area : cur.xy, kind: cur.tone ? "unknown" : "observed", label: hms(cur.iso) }}
            litCameras={[cur.cam]} legend={false} fit="contain" minHeight={0} />
          <figcaption>{inside.place}</figcaption>
        </figure>
      </div>

      {strip && <ol className="lp-mo cs-mo" aria-label="The moments, in order">
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
                  <span className="cs-mo-zoom" style={zoomOn(thumbBox(m))}>
                    {/* eslint-disable-next-line @next/next/no-img-element -- a signed CCTV frame from the API */}
                    {stills[m.key] && <img src={stills[m.key]} alt="" loading="lazy" decoding="async" />}
                    {stills[m.key] && thumbBox(m) && (() => { const b = thumbBox(m)!; return (
                      <svg className="cs-mo-mark" viewBox={`0 0 ${wh[0]} ${wh[1]}`} preserveAspectRatio="xMidYMid slice" aria-hidden="true">
                        <rect x={b[0] - 8} y={b[1] - 8} width={b[2] - b[0] + 16} height={b[3] - b[1] + 16} rx="6" />
                      </svg>); })()}
                  </span>
                  <span className="lp-mo-cam">{camWords(m.cam)}</span>
                </span>
              </button>
              <p className="lp-mo-cap">{m.text}</p>
            </li>
          );
        })}
      </ol>}

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
