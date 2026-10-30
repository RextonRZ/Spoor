"use client";
/**
 * Lead investigator (QUEUE J2): Muse Wonder 1.0 proposes which footage to analyse next, from the journey and the missing
 * moment. A paid call: the button states the model and the estimated cost first. Steps that cite unknown evidence or a
 * non-candidate camera were dropped by the backend's check and are counted here. A plan, never an answer.
 */
import { useState } from "react";
import { api, invalidate, useResource } from "@/lib/api";
import { cam } from "@/lib/journey";
import { useWorkspace } from "./context";

interface Lead {
  available: boolean;
  estimate: { model: string; usd: number };
  plan: null | { model: string; summary: string; at: string; usd_estimate: number; unknowns: string[]; rejected: unknown[];
    steps: { camera_id: string; window_start: string; window_end: string; what_to_check: string; why: string }[] };
}

export default function LeadPlan() {
  const { caseId } = useWorkspace();
  const path = `/v1/cases/${caseId}/lead-plan`;
  const lead = useResource<Lead>(path);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  if (!lead.data) return null;
  const { available, estimate, plan } = lead.data;
  return (
    <section className="sp-tint" style={{ padding: 14 }} aria-labelledby="lead-h" data-testid="lead-plan">
      <p className="sp-micro" id="lead-h">Lead investigator · {estimate.model}</p>
      <button className="sp-btn sp-btn-sm" style={{ marginTop: 8 }} disabled={!available || busy} onClick={async () => {
        setBusy(true); setErr(null);
        try { await api(path, { method: "POST" }); invalidate(path); } catch (e) { setErr(e instanceof Error ? e.message : String(e)); } finally { setBusy(false); }
      }}>{busy ? "Planning" : `Plan the next footage to analyse · about US$${estimate.usd.toFixed(2)}`}</button>
      {!available && <p className="sp-caption">Unavailable: no API key. With the key, Muse Wonder plans from the journey and the missing moment.</p>}
      {err && <p role="alert" className="sp-caption">{err}</p>}
      {plan && (
        <div className="sp-stack" style={{ gap: 6, marginTop: 10 }}>
          <p style={{ margin: 0, fontSize: 13 }}>{plan.summary}</p>
          <ol style={{ margin: 0, paddingLeft: 18, fontSize: 12.5 }}>
            {plan.steps.map((s, i) => <li key={i}><b>{cam(s.camera_id)}</b> · {s.what_to_check}<span className="sp-caption"> · {s.why}</span></li>)}
          </ol>
          <p className="sp-caption">{plan.model} · US${plan.usd_estimate.toFixed(3)} · {plan.rejected.length} step{plan.rejected.length === 1 ? "" : "s"} dropped by the evidence check · a plan, not evidence</p>
        </div>
      )}
    </section>
  );
}
