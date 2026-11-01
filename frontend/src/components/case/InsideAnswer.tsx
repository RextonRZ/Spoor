"use client";
/**
 * The verified "most likely inside an area no camera sees" answer, laid out like a VMS investigation result: the doorway
 * camera's full CCTV frame (its own on-screen clock and name kept) beside the floor plan (the area, where it was last
 * seen, an arrow in), then the moments in time order. Each moment is a button: the frame steps to that time on the same
 * camera, so the facts read as a storyboard. On the last sighting the parcel's path as SAM tracked it is drawn, ending in
 * its box, with a digital-zoom inset of the carton (drawn here from the stored box, not burned into the frame).
 * The agents' own ideas sit behind a toggle, each with the one check that decided it: their wording is never a finding.
 * Everything comes from GET /state "answer" (the verifier's facts), the evidence record and frame-at.
 */
import { useEffect, useState } from "react";
import { api, signedUrl } from "@/lib/api";
import { HYPOTHESIS_WORDS, type InsideFacts, type InvestigationView } from "@/lib/answer";
import HubPlan from "@/components/plan/HubPlan";

const CHECK_WORDS: Record<string, string> = { stayed_in_area: "stayed inside", exit: "left through a door", transition: "moved between areas",
  transfer: "handed over", parcel_match: "same parcel", order: "order of sightings" };

interface Moment { key: string; iso: string; t: string; text: string; tone?: "unknown" }
const LOUPE = 0.12; // the zoom inset shows this share of the frame's width around the parcel

function useSightingUrl(caseId: string, observationId: string): string | null {
  const [s, setS] = useState<{ k: string; u: string } | null>(null);
  useEffect(() => {
    let live = true;
    api<{ frame_url: string }>(`/v1/cases/${caseId}/evidence/${observationId}`)
      .then((r) => live && setS({ k: observationId, u: signedUrl(r.frame_url) })).catch(() => {});
    return () => { live = false; };
  }, [caseId, observationId]);
  return s?.k === observationId ? s.u : null;
}

/** a frame with the parcel's tracked path and box drawn over it, filling its container */
function Marked({ url, wh, box, trail, alt }: { url: string; wh: number[]; box: number[]; trail: number[][]; alt: string }) {
  return (
    <>
      {/* eslint-disable-next-line @next/next/no-img-element -- a signed evidence frame from the API, shown as it is */}
      <img src={url} alt={alt} />
      <svg viewBox={`0 0 ${wh[0]} ${wh[1]}`} aria-hidden>
        {trail.length > 1 && <polyline points={trail.map((q) => q.join(",")).join(" ")} fill="none" stroke="#4ade80" strokeWidth={2}
          strokeDasharray="5 4" strokeLinecap="round" strokeLinejoin="round" vectorEffect="non-scaling-stroke" opacity={0.9} />}
        <rect x={box[0] - 5} y={box[1] - 5} width={box[2] - box[0] + 10} height={box[3] - box[1] + 10} rx={3} fill="none"
          stroke="#4ade80" strokeWidth={2.5} vectorEffect="non-scaling-stroke" />
      </svg>
    </>
  );
}

/** one plain frame per moment, fetched up front so stepping through them is instant */
function useFrames(mediaId: string, moments: Moment[]): Record<string, string> {
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

export function InsideAnswer({ caseId, inside, view }: { caseId: string; inside: InsideFacts; view: InvestigationView }) {
  const moments: Moment[] = [
    { key: "door", iso: inside.iso.door_at, t: inside.door_at, text: "Last seen at its door" },
    { key: "in", iso: inside.iso.carried_in_at, t: inside.carried_in_at, text: "Carried in" },
    ...inside.came_out_empty.map((t, i) => ({ key: `out${i}`, iso: inside.iso[`came_out_${i}`], t, text: "Someone came out without it" })),
    { key: "end", iso: inside.iso.until, t: inside.until, text: "Recording ends, not seen coming out", tone: "unknown" as const },
  ];
  const [sel, setSel] = useState("door");
  const seenUrl = useSightingUrl(caseId, inside.observation_id);
  const frames = useFrames(inside.media_id, moments);
  const [wh, box] = [inside.frame_wh_px, inside.box_px];
  const cur = moments.find((m) => m.key === sel) ?? moments[0];
  const urlOf = (m: Moment) => (m.key === "door" ? seenUrl ?? undefined : undefined) ?? frames[m.key];
  // the inset: the frame scaled so LOUPE of its width fills the inset, centred on the parcel (the inset is 4:3)
  const k = 1 / LOUPE, cx = (box[0] + box[2]) / 2 / wh[0], cy = (box[1] + box[3]) / 2 / wh[1], hk = (k * wh[1]) / wh[0] / 0.75;
  const loupe = { width: `${k * 100}%`, height: `${hk * 100}%`, left: `${(0.5 - cx * k) * 100}%`, top: `${(0.5 - cy * hk) * 100}%` };
  const to: [number, number] = [inside.area_xy[0], inside.area_xy[1]];

  return (
    <>
      <div className="ia-fig">
        <figure className="ia-shot" style={{ aspectRatio: `${wh[0]} / ${wh[1]}` }}>
          {moments.map((m) => {
            const u = urlOf(m);
            if (!u) return null;
            const alt = `${inside.camera} at ${m.t}: ${m.text.toLowerCase()}`;
            return (
              <div key={m.key} className="ia-layer" data-on={m.key === cur.key || undefined}>
                {m.key === "door" ? <Marked url={u} wh={wh} box={box} trail={inside.trail_px} alt={alt} />
                  // eslint-disable-next-line @next/next/no-img-element -- a signed CCTV frame from the API, shown as it is
                  : <img src={u} alt={alt} />}
              </div>
            );
          })}
          {!urlOf(cur) && <span className="an-skel ia-skel" aria-busy="true" />}
          {cur.key === "door" && seenUrl && (
            <div className="ia-loupe" aria-hidden>
              <div style={loupe}><Marked url={seenUrl} wh={wh} box={box} trail={[]} alt="" /></div>
              <span>Zoom</span>
            </div>
          )}
          <figcaption>{cur.key === "door" ? <>Parcel tracked by <b>SAM 3.1</b></> : cur.text}</figcaption>
        </figure>
        <figure className="ia-plan">
          <HubPlan label={`${inside.place}: last seen at its door, carried in`} story={{ area: inside.area_polygon, from: inside.door_xy, to }}
            litCameras={[inside.camera.replace(" ", "_")]} legend={false} fit="contain" minHeight={0} />
          <figcaption>{inside.place}</figcaption>
        </figure>
      </div>
      <ol className="ia-moments" aria-label="What the doorway camera shows">
        {moments.map((m) => (
          <li key={m.key}>
            <button type="button" aria-pressed={m.key === cur.key} data-tone={m.tone} onClick={() => setSel(m.key)}>
              <time>{m.t}</time><span>{m.text}</span>
            </button>
          </li>
        ))}
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
    </>
  );
}
