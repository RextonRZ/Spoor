"use client";
/**
 * Case summary (QUEUE H14): page 1 of every report, for claims, customer service and managers. One sentence, a status,
 * the key frames, the route with its gaps, how sure, and what to do next. Everything is computed by the backend from
 * stored evidence (/journey, /missing-moment, /plan); the formal document stays as the Evidence appendix.
 */
import Link from "next/link";
import { use } from "react";
import { signedUrl, useResource } from "@/lib/api";
import {
  answerParts, answerSentence, cam, caseStatus, clock, confidenceWords, nextAction, openFor, openedOn, RESULT_WORDS,
  type ExpectedNext, type FrameRef, type Journey, type JourneyObject, type MissingMoment,
} from "@/lib/journey";
import type { CaseState } from "@/lib/types";
import { ErrorState, Loading } from "@/components/ui";
import HubPlan from "@/components/plan/HubPlan";
import "./summary.css";

const STATUS = {
  found: { label: "Found", cls: "sp-chip-safe" },
  located: { label: "Located", cls: "sp-chip-accent" },
  unknown: { label: "Unknown", cls: "" },
} as const;

export default function SummaryPage({ params }: { params: Promise<{ caseId: string }> }) {
  const { caseId } = use(params);
  const state = useResource<CaseState>(`/v1/cases/${caseId}/state`);
  const journey = useResource<Journey>(`/v1/cases/${caseId}/journey`);
  const missing = useResource<MissingMoment>(`/v1/cases/${caseId}/missing-moment`);

  if (state.error || journey.error) {
    return <div className="sp-page"><ErrorState error={(state.error ?? journey.error)!} what="the case summary"
      onRetry={() => { state.reload(); journey.reload(); }} /></div>;
  }
  // The answer and the next action depend on the missing moment too: never show an interim sentence that changes.
  if (!state.data || !journey.data || (!missing.data && !missing.error)) {
    return <div className="sp-page"><Loading label="Loading the case summary" lines={5} /></div>;
  }

  const c = state.data.case;
  const j = journey.data.objects[0];
  const mm = missing.data?.objects[0];
  const status = STATUS[caseStatus(j)];
  const action = nextAction(mm);
  const waybill = j?.identity_keys.find((k) => k.startsWith("carrier_waybill:"))?.split(":")[1];
  return (
    <article className="sp-page sum" aria-labelledby="sum-answer">
      <header className="sum-head">
        <div className="sp-row sp-wrap sum-meta">
          <span className="sp-eyebrow">Case summary</span>
          <span className={`sp-chip ${status.cls}`} data-testid="case-status">{status.label}</span>
          <span className="sp-chip sp-chip-sim">synthetic footage · simulated scans</span>
        </div>
        <h1 className="sp-h1 sum-answer" id="sum-answer" data-testid="case-answer" aria-describedby="sum-sub">{answerParts(j, mm).head}</h1>
        <p className="sum-sub" id="sum-sub">{answerParts(j, mm).sub}</p>
        <p className="sp-sr">{answerSentence(j, mm)}</p>
        <dl className="sum-facts">
          <div><dt className="sp-micro">Waybill</dt><dd className="sp-num">{waybill ?? "none"}</dd></div>
          <div><dt className="sp-micro">Opened</dt><dd>{openedOn(c.created_at)}</dd></div>
          <div><dt className="sp-micro">Open for</dt><dd className="sp-num">{openFor(c.created_at)}</dd></div>
          <div><dt className="sp-micro">Case</dt><dd className="sp-num">{c.case_id.slice(-8)}</dd></div>
        </dl>
        {c.complaint && <blockquote className="sum-complaint">“{c.complaint}”</blockquote>}
      </header>

      <section aria-label="Key frames" className="sum-frames">
        <KeyFrames j={j} mm={missing.data} loading={missing.loading} />
      </section>

      <div className="sum-grid">
        <section className="sp-panel sum-map" aria-labelledby="sum-route">
          <div className="sp-panel-head">
            <h2 className="sp-h3" id="sum-route">Route through the hub</h2>
          </div>
          <div className="sp-panel-body">
            {j ? <HubPlan label={`Route of ${j.label} through the hub`} journey={j} missing={mm} minHeight={320}
              litCameras={(mm?.expected_next ?? []).filter((r) => r.result !== "no_footage").map((r) => cam(r.camera_id))} /> : <Loading lines={3} />}
          </div>
        </section>

        <div className="sum-side">
          <section className="sp-tint sum-next" aria-labelledby="sum-next-h">
            <p className="sp-micro" id="sum-next-h">Next action</p>
            {action ? <>
              <p className="sum-next-text" data-testid="next-action">{action.text}</p>
              <p className="sp-caption">{action.detail}</p>
            </> : <p className="sum-next-text">No action can be derived from the evidence yet.</p>}
            <div className="sp-row sp-wrap sum-actions">
              <Link className="sp-btn sp-btn-primary" href={`/cases/${caseId}`}>Open the investigation</Link>
              <button className="sp-btn" onClick={() => window.print()}>Print or save as PDF</button>
            </div>
          </section>

          <section className="sp-card" aria-labelledby="sum-conf">
            <h2 className="sp-h3" id="sum-conf">How sure</h2>
            <ul className="sum-conf">
              {confidenceWords(j).map((w) => <li key={w}>{w}</li>)}
            </ul>
            {journey.data.needs.map((n) => <p key={n} className="sp-caption">{n}</p>)}
          </section>

          <section className="sp-card sum-appendix" aria-labelledby="sum-app">
            <h2 className="sp-h3" id="sum-app">Evidence appendix</h2>
            <p className="sp-caption">The full trace: scan history, CCTV reviewed with hashes, continuity, records a claim needs.</p>
            <Link className="sp-btn sp-btn-sm" href={`/cases/${caseId}/report`}>Open the report</Link>
          </section>
        </div>
      </div>
      <p className="sp-caption sum-foot">Investigative decision support, not a forensic certification. Inferred stretches
        come from the site plan&apos;s belt route and are not observations. Times in {clock(c.created_at).split(" ").pop()}.</p>
    </article>
  );
}

function KeyFrames({ j, mm, loading }: { j?: JourneyObject; mm?: MissingMoment; loading: boolean }) {
  const o = mm?.objects[0];
  const lastFrames = o?.last_confirmed?.frames ?? [];
  const rowOf = (camera: string) => o?.expected_next.find((r) => r.camera_id === camera);
  const first = lastFrames[0];
  const nextRow = o?.expected_next.find((r) => r.frame && r.camera_id !== first?.camera_id);
  if (loading && !mm) return <Loading label="Loading key frames" lines={2} />;
  return (
    <>
      <Tile n="1" title="Last confirmed" frame={first} row={first ? rowOf(first.camera_id) : undefined}
        caption={first ? `${cam(first.camera_id)} · ${j?.last_confirmed ? clock(j.last_confirmed.t, true) : ""}`
          : "No frame at the last confirmed moment."}
        note={first?.role === "context_at_scan_time" ? "Frame at the scan time. The parcel is not yet identified in it." : undefined} />
      <Tile n="2" title="The missing moment" frame={nextRow?.frame ?? undefined} row={nextRow}
        caption={nextRow ? `${cam(nextRow.camera_id)} · expected ${clock(nextRow.window.start, true).replace(" MYT", "")}–${clock(nextRow.window.end, true)} · ${RESULT_WORDS[nextRow.result]}`
          : "No camera with footage was due next."}
        note={nextRow ? "Dashed box: where it should appear (approximate, from the mounting plan)." : undefined} />
      <Tile n="3" title="Where it is" empty="Not located yet. The possible area narrows only when analysed footage shows where it was not." />
      <Tile n="4" title="Found" empty="Not found yet. A floor search records the outcome here." />
    </>
  );
}

function Tile({ n, title, frame, row, caption, note, empty }: {
  n: string; title: string; frame?: FrameRef; row?: ExpectedNext; caption?: string; note?: string; empty?: string;
}) {
  const r = row?.expected_region_px;
  const b = row?.region_basis_wh_px;
  return (
    <figure className="sum-tile">
      <figcaption className="sum-tile-head"><span className="sum-tile-n sp-num">{n}</span>{title}</figcaption>
      {frame ? (
        <div className="sum-shot">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={signedUrl(frame.frame_url)} alt={`${title}: original frame ${frame.frame_index} of ${cam(frame.camera_id)}`} />
          {r && b && <span className="sum-expect" aria-hidden style={{ left: `${(r[0] / b[0]) * 100}%`,
            top: `${(r[1] / b[1]) * 100}%`, width: `${((r[2] - r[0]) / b[0]) * 100}%`, height: `${((r[3] - r[1]) / b[1]) * 100}%` }} />}
          <span className="sum-shot-tag">original · frame {frame.frame_index}</span>
        </div>
      ) : <div className="sum-shot sum-shot-empty"><p>{empty ?? caption}</p></div>}
      {frame && <p className="sum-tile-cap">{caption}</p>}
      {note && <p className="sp-caption">{note}</p>}
    </figure>
  );
}
