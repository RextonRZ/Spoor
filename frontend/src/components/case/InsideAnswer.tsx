"use client";
/**
 * The verified "most likely inside an area no camera sees" answer, laid out like a VMS investigation result: the
 * camera still the verifier relied on (SAM outline, camera, time) beside the floor plan with the place, then the facts
 * in time order. The agents' own ideas sit behind a toggle, each with the one check that decided it: their wording is
 * never shown as a finding. Everything comes from GET /state "answer" (the verifier's facts) and the evidence frame.
 */
import { useEffect, useState } from "react";
import { api, signedUrl } from "@/lib/api";
import { HYPOTHESIS_WORDS, type InsideFacts, type InvestigationView } from "@/lib/answer";
import HubPlan from "@/components/plan/HubPlan";

const CHECK_WORDS: Record<string, string> = { stayed_in_area: "stayed inside", exit: "left through a door", transition: "moved between areas",
  transfer: "handed over", parcel_match: "same parcel", order: "order of sightings" };

interface Shot { k: string; u: string; at: [number, number] }

/** the outlined evidence frame, and where the parcel sits in it (0..1), so the still can be zoomed toward it */
function useShot(caseId: string, observationId: string): Shot | null {
  const [shot, setShot] = useState<Shot | null>(null);
  useEffect(() => {
    let live = true;
    api<{ annotated_frame_url: string; observation: { bbox_xyxy_px: number[] | null; frame_wh_px: number[] | null } }>(
      `/v1/cases/${caseId}/evidence/${observationId}`).then((r) => {
      const [b, wh] = [r.observation.bbox_xyxy_px, r.observation.frame_wh_px];
      const at: [number, number] = b && wh ? [(b[0] + b[2]) / 2 / wh[0], (b[1] + b[3]) / 2 / wh[1]] : [0.5, 0.5];
      if (live) setShot({ k: observationId, u: signedUrl(r.annotated_frame_url), at });
    }).catch(() => {});
    return () => { live = false; };
  }, [caseId, observationId]);
  return shot?.k === observationId ? shot : null;
}

export function InsideAnswer({ caseId, inside, view }: { caseId: string; inside: InsideFacts; view: InvestigationView }) {
  const shot = useShot(caseId, inside.observation_id);
  const facts: { t: string; text: string; sub?: string; tone?: string }[] = [
    { t: inside.door_at, text: "Last seen at its door", sub: inside.camera },
    { t: inside.carried_in_at, text: "Carried in" },
    ...inside.came_out_empty.map((t) => ({ t, text: "Someone came out without it" })),
    { t: inside.until, text: "Recording ends, not seen coming out", tone: "unknown" },
  ];
  return (
    <>
      <div className="ia-fig">
        <figure className="ia-shot">
          {/* eslint-disable-next-line @next/next/no-img-element -- a signed evidence frame from the API, shown as is */}
          {shot ? <img src={shot.u} alt={`${inside.camera} at ${inside.door_at}: the parcel at the door of the ${inside.place}, outlined`}
            style={{ transformOrigin: `${(shot.at[0] * 100).toFixed(1)}% ${(shot.at[1] * 100).toFixed(1)}%` }} />
            : <span className="an-skel ia-skel" aria-busy="true" />}
          <figcaption><b>{inside.camera}</b> {inside.door_at}<span>SAM 3.1 outline</span></figcaption>
        </figure>
        <figure className="ia-plan">
          <HubPlan label={`${inside.place} on the floor plan`} focus={{ xy: inside.area_xy, radius_m: 9, tone: "warn" }} legend={false} fit="contain" minHeight={0} />
          <figcaption>{inside.place}</figcaption>
        </figure>
      </div>
      <ol className="an-tl ia-facts">
        {facts.map((f) => (
          <li key={`${f.t}${f.text}`} data-tone={f.tone}><time>{f.t}</time><span>{f.text}{f.sub && <em>{f.sub}</em>}</span></li>
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
