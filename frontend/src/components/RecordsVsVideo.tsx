"use client";
/**
 * Records vs video (QUEUE H5): two lanes on one time axis, "What the scan records say" and "What the cameras saw", that
 * split at a red pin where a typed conflict starts (backend I6). An empty video lane is drawn as "no confirmed track
 * yet", never as agreement.
 */
import { useResource } from "@/lib/api";
import { cam, clock } from "@/lib/journey";
import { toMs } from "@/lib/time";
import { zoneId } from "@/lib/hub";
import { ZONE_NAMES } from "@/components/plan/HubPlan";

interface Conflicts {
  objects: {
    records: { t: string; words: string; zone_id: string | null; evidence_id: string; claim?: string }[];
    video: { start: string; end: string; camera_id: string }[];
    conflicts: { kind: string; divergence_t: string; statement: string;
      claim: { t?: string; zone_id?: string | null; words?: string } | null;
      observation: { t: string; camera_id: string | null; zone_id: string | null } | null }[];
    note: string | null;
  }[];
}

export default function RecordsVsVideo({ caseId, range }: { caseId: string; range?: { start: number; end: number } }) {
  const r = useResource<Conflicts>(`/v1/cases/${caseId}/conflicts`);
  const o = r.data?.objects[0];
  if (!o) return null;
  const ts = [...o.records.map((x) => toMs(x.t)), ...o.video.flatMap((v) => [toMs(v.start), toMs(v.end)]),
    ...o.conflicts.map((c) => toMs(c.divergence_t))];
  const lo = range?.start ?? Math.min(...ts) - 3000;
  const hi = range?.end ?? Math.max(...ts) + 3000;
  const x = (t: string) => `${Math.min(100, Math.max(0, ((toMs(t) - lo) / (hi - lo)) * 100))}%`;
  return (
    <section className="rv" aria-labelledby="rv-h" data-testid="records-vs-video">
      <div className="rv-head">
        <h2 className="sp-h3" id="rv-h">What the records say vs what the cameras saw</h2>
        <span className={`sp-chip ${o.conflicts.length ? "sp-chip-alert" : ""}`}>
          {o.conflicts.length ? `${o.conflicts.length} disagreement${o.conflicts.length > 1 ? "s" : ""}` : "no disagreement found"}
        </span>
      </div>
      <div className="rv-lanes">
        <div className="rv-lane">
          <span className="rv-name">Scan records</span>
          <div className="rv-track">
            {o.records.map((rec) => (
              <span key={rec.evidence_id + rec.t} className="rv-dot" data-claim={rec.claim} style={{ left: x(rec.t) }}
                title={`${clock(rec.t, true)} · ${rec.words}${rec.claim ? ` (claims: ${rec.claim})` : ""}`} />
            ))}
          </div>
        </div>
        <div className="rv-lane">
          <span className="rv-name">Cameras</span>
          <div className="rv-track">
            {o.video.length === 0 && <span className="rv-empty">no confirmed track yet</span>}
            {o.video.map((v) => (
              <span key={v.start + v.camera_id} className="rv-bar" style={{ left: x(v.start), width: `calc(${x(v.end)} - ${x(v.start)} + 3px)` }}
                title={`${cam(v.camera_id)} ${clock(v.start, true)}–${clock(v.end, true)}`} />
            ))}
          </div>
        </div>
        {o.conflicts.map((c) => (
          <span key={c.divergence_t + c.kind} className="rv-pin" style={{ left: `calc(var(--rv-name) + (100% - var(--rv-name)) * ${parseFloat(x(c.divergence_t)) / 100})` }}
            title={sentence(c)} aria-hidden />
        ))}
      </div>
      {o.conflicts.map((c) => (
        <p key={c.statement} className="rv-statement"><span className="rv-pin-dot" aria-hidden />{clock(c.divergence_t, true)} · {sentence(c)}</p>
      ))}
      {o.note && <p className="sp-caption">{o.note.charAt(0).toUpperCase() + o.note.slice(1)}.</p>}
    </section>
  );
}

const zoneName = (z: string | null | undefined) => (z ? ZONE_NAMES[zoneId.toHub(z)] ?? z : "view");

/** The conflict in plain words from its typed fields (MYT times, human zone names); timing conflicts keep their note. */
function sentence(c: Conflicts["objects"][number]["conflicts"][number]): string {
  if (!c.observation || !c.claim?.t) return c.statement;
  const said = c.kind === "departure" ? "left the hub" : `was in ${zoneName(c.claim.zone_id)}`;
  // "saw it at": a camera may see only a doorway (CAM_19 sees ~5 % of the store), so never "confirmed it in"
  const z = zoneName(c.observation.zone_id);
  const place = z === "Exception store" ? "the exception store (inside the cage + bag store)" : z;
  return `The records say it ${said} (${c.claim.words}, ${clock(c.claim.t, true)}); ${cam(c.observation.camera_id)} saw it at `
    + `${place} at ${clock(c.observation.t, true)}.`;
}
