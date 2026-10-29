"use client";
/**
 * Investigation agent panel (PRD §19.2 #7). Shows the backend job's real events as they arrive over SSE, then the
 * orchestrator's stored answer verbatim. No simulated typing, no invented tool activity (PRD §19.5).
 */
import { useEffect, useRef, useState } from "react";
import { api, API_BASE } from "@/lib/api";
import { fmtTime } from "@/lib/time";
import type { CaseDiff, JobEvent, JobStatus } from "@/lib/types";
import { Unavailable } from "@/components/ui";
import { useWorkspace } from "./context";

interface Run {
  jobId: string;
  events: JobEvent[];
  status: JobStatus["status"] | "connecting";
  result: JobStatus["result"];
  error: string | null;
  fromRevision: string | null;
  diff: CaseDiff | null;
  prevAnswer: string | null;
}

export default function AgentPanel() {
  const { caseId, state, caps, reloadAll } = useWorkspace();
  const [runs, setRuns] = useState<Run[]>([]);
  const [startErr, setStartErr] = useState<string | null>(null);
  const esRef = useRef<EventSource | null>(null);
  const hasLM = !!caps.data?.agents;
  const running = runs[0] && (runs[0].status === "running" || runs[0].status === "queued" || runs[0].status === "connecting");

  useEffect(() => () => esRef.current?.close(), []);

  async function start() {
    setStartErr(null);
    const fromRevision = state.data?.revision?.case_revision_id ?? null;
    const prevAnswer = runs[0]?.result?.answer ?? null;
    let jobId: string;
    try {
      jobId = (await api<{ job_id: string }>(`/v1/cases/${caseId}/investigate`, { method: "POST" })).job_id;
    } catch (e) {
      setStartErr(e instanceof Error ? e.message : String(e));
      return;
    }
    const run: Run = { jobId, events: [], status: "connecting", result: null, error: null, fromRevision, diff: null, prevAnswer };
    setRuns((r) => [run, ...r]);
    const patch = (p: Partial<Run>) => setRuns((rs) => rs.map((x) => (x.jobId === jobId ? { ...x, ...p } : x)));
    const es = new EventSource(`${API_BASE}/v1/jobs/${jobId}/events`);
    esRef.current = es;
    es.onmessage = (m) => {
      const ev = JSON.parse(m.data) as JobEvent;
      setRuns((rs) => rs.map((x) => (x.jobId === jobId ? { ...x, status: "running", events: [...x.events, ev] } : x)));
    };
    es.addEventListener("end", async () => {
      es.close();
      try {
        const job = await api<JobStatus>(`/v1/jobs/${jobId}`);
        let diff: CaseDiff | null = null;
        if (job.result?.revision_id) {
          const q = new URLSearchParams({ to_revision: job.result.revision_id });
          if (fromRevision) q.set("from_revision", fromRevision);
          diff = await api<CaseDiff>(`/v1/cases/${caseId}/diff?${q}`).catch(() => null);
        }
        patch({ status: job.status, result: job.result, error: job.error, diff });
        await reloadAll();
      } catch (e) {
        patch({ status: "failed", error: e instanceof Error ? e.message : String(e) });
      }
    });
    es.onerror = () => {
      if (es.readyState === EventSource.CLOSED) return;
      es.close();
      patch({ status: "failed", error: "Lost the live connection to the job. Its result is still stored; reload to see it." });
    };
  }

  return (
    <div className="sp-stack">
      {!hasLM && (
        <Unavailable title="Language-model agents: analysis unavailable (no API key)">
          The investigation still runs: the deterministic orchestrator answers from stored evidence only and abstains
          where evidence is missing. Free questions need the language model.
        </Unavailable>
      )}
      <label className="sp-field">
        <span className="sp-label">Ask about this case</span>
        <textarea className="sp-textarea" disabled={!hasLM} placeholder={hasLM ? "e.g. Was the parcel seen leaving the chute?" : "Needs the language model (no API key)"} />
      </label>
      <div className="sp-row sp-wrap">
        <button className="sp-btn sp-btn-primary" onClick={start} disabled={!!running} data-testid="run-investigation">
          {running ? "Investigation running" : "Run the investigation of the case question"}
        </button>
      </div>
      {startErr && <div role="alert" className="sp-state sp-state-error">{startErr}</div>}
      {runs.length === 0 && <p className="sp-caption">No investigation run in this session yet. Runs use only stored evidence and cost nothing without model keys.</p>}
      {runs.map((r, i) => (
        <article key={r.jobId} className="sp-card sp-card-tight sp-stack" style={{ gap: 10 }} aria-label={`Investigation run ${runs.length - i}`}>
          <div className="sp-row" style={{ justifyContent: "space-between" }}>
            <span className="sp-micro">Run {runs.length - i} · {r.jobId.slice(-8)}</span>
            <span className={r.status === "done" ? "sp-chip sp-chip-safe" : r.status === "failed" ? "sp-chip sp-chip-alert" : "sp-chip"}>{r.status}</span>
          </div>
          <ol className="sp-list" aria-live="polite" aria-label="Job events" style={{ fontSize: 12.5 }}>
            {r.events.map((e, k) => (
              <li key={k} className="sp-row" style={{ alignItems: "baseline" }}>
                <span className="sp-num sp-muted" style={{ fontSize: 11 }}>{fmtTime(e.at)}</span>
                <span>{e.message}{"agents" in e ? ` · language model: ${e.agents ? "on" : "off"}` : ""}</span>
              </li>
            ))}
            {r.status === "connecting" && <li className="sp-muted">Connecting to the job stream</li>}
          </ol>
          {r.error && <div role="alert" className="sp-state sp-state-error">{r.error}</div>}
          {r.result && (
            <div className="sp-stack sp-gap-s">
              <div className="sp-row"><span className="sp-micro">Answer</span>
                <span className={r.result.status === "answered" ? "sp-chip sp-chip-safe" : "sp-chip sp-chip-warn"}>{r.result.status}</span></div>
              <pre className="sp-answer">{r.result.answer}</pre>
              <p className="sp-caption">Composed by the orchestrator from verified findings and recorded hypothesis states only.</p>
              {r.result.hypotheses.length > 0 && (
                <ul className="sp-list" style={{ fontSize: 12.5 }}>
                  {r.result.hypotheses.map((h) => <li key={h.id}><span className="sp-chip sp-chip-warn">{h.status}</span> {h.claim}</li>)}
                </ul>
              )}
              {r.diff && <DiffView diff={r.diff} prevAnswer={r.prevAnswer} answer={r.result.answer} />}
            </div>
          )}
        </article>
      ))}
    </div>
  );
}

function DiffView({ diff, prevAnswer, answer }: { diff: CaseDiff; prevAnswer: string | null; answer: string }) {
  const items = [
    ...diff.new_findings.map((f) => `New finding: ${f.statement}`),
    ...diff.invalidated_findings.map((f) => `Finding invalidated: ${f}`),
    ...diff.new_hypotheses.map((h) => `New hypothesis: ${h.claim}`),
    ...diff.status_changes.map((s) => `${s.claim}: ${s.from} to ${s.to}`),
    ...diff.new_evidence_requests.map((r) => `Evidence requested: ${r.reason}`),
    ...diff.last_seen_changed.map((l) => `Last seen changed: ${l.after}`),
  ];
  const answerChanged = prevAnswer !== null && prevAnswer !== answer;
  return (
    <section className="sp-tint" style={{ padding: 12 }} aria-label="What changed">
      <p className="sp-micro">What changed in this revision</p>
      {items.length === 0 && !answerChanged ? (
        <p className="sp-muted" style={{ margin: "4px 0 0", fontSize: 12.5 }}>No new evidence since the previous revision.</p>
      ) : (
        <ul className="sp-list" style={{ fontSize: 12.5, marginTop: 4 }}>
          {items.map((t) => <li key={t}>{t}</li>)}
          {answerChanged && <li>The answer changed from the previous run.</li>}
        </ul>
      )}
    </section>
  );
}
