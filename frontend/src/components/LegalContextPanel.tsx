"use client";
/**
 * Malaysian context for reports (QUEUE J3): Muse Spark 1.3 with web search answers a few narrow questions about the
 * Postal Services Act 2012 and MCMC complaint rules. Only cited sentences are kept; .gov.my sources are marked official.
 * Background for the report reader, never case evidence. A paid call: the button states the measured cost first.
 */
import { useState } from "react";
import type { LegalContext } from "@/contracts/generated";
import { api, invalidate, useResource } from "@/lib/api";
import { fmtDate, fmtTime } from "@/lib/time";

interface Resp { context: LegalContext | null; available: boolean; estimate: { model: string; usd: number; basis: string } }

export default function LegalContextPanel({ siteId, admin }: { siteId: string | undefined; admin: boolean }) {
  const path = siteId ? `/v1/sites/${siteId}/legal-context` : null;
  const res = useResource<Resp>(path);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  if (!path || !res.data) return null;
  const { context: c, available, estimate } = res.data;
  const dropped = c ? c.answers.reduce((n, a) => n + a.dropped_uncited + (a.dropped_narration ?? 0), 0) : 0;
  return (
    <section className="sp-panel" aria-labelledby="lc-h" data-testid="legal-context">
      <div className="sp-panel-head"><h2 className="sp-micro" id="lc-h" style={{ margin: 0 }}>Malaysian context for reports</h2></div>
      <div className="sp-panel-body sp-stack" style={{ gap: 12 }}>
        <p className="sp-caption" style={{ margin: 0 }}>
          Web search, cited and dated. It appears in every case report as background for the reader. It is not case evidence.
        </p>
        {c ? c.answers.map((a, i) => (
          <div key={i} className="sp-stack" style={{ gap: 4 }}>
            <p style={{ margin: 0, fontSize: 13, fontWeight: 600 }}>{a.question}</p>
            <p style={{ margin: 0, fontSize: 13, lineHeight: 1.55, maxWidth: "72ch" }}>
              {a.sentences.length ? a.sentences.map((s, j) => (
                <span key={j}>{s.text}{s.sources.map((n) => <sup key={n}> [{n}]</sup>)} </span>
              )) : <span className="sp-caption">No cited answer.</span>}
            </p>
          </div>
        )) : <p className="sp-caption" style={{ margin: 0 }}>Not retrieved yet. Reports say so instead.</p>}
        {c && (
          <ol style={{ margin: 0, paddingLeft: 0, listStyle: "none", fontSize: 12.5 }} className="sp-stack">
            {c.sources.map((s) => (
              <li key={s.n}>
                [{s.n}] <a href={s.url} target="_blank" rel="noreferrer">{s.title}</a> · {s.domain}{" "}
                {s.official ? <span className="sp-chip sp-chip-safe">official</span> : <span className="sp-chip">secondary</span>}
              </li>
            ))}
          </ol>
        )}
        {c && (
          <p className="sp-caption" style={{ margin: 0 }}>
            Retrieved {fmtDate(c.retrieved_at)}, {fmtTime(c.retrieved_at, false)} MYT · {c.model} · {c.searches} searches ·
            US${c.usd_estimate.toFixed(2)} · {dropped} sentence{dropped === 1 ? "" : "s"} left out (uncited or the model narrating its search)
          </p>
        )}
        {admin && (
          <div>
            <button className="sp-btn sp-btn-sm" disabled={!available || busy} onClick={async () => {
              setBusy(true); setErr(null);
              try { await api(path, { method: "POST" }); invalidate(path); } catch (e) { setErr(e instanceof Error ? e.message : String(e)); } finally { setBusy(false); }
            }}>{busy ? "Searching (about 2 min)" : `${c ? "Refresh" : "Retrieve"} the Malaysian context · about US$${estimate.usd.toFixed(2)}`}</button>
            <p className="sp-caption" style={{ margin: "6px 0 0" }}>
              {available ? `Cost measured on the last run: ${estimate.basis}.` : "Unavailable: no API key. Reports show the last retrieved version."}
            </p>
          </div>
        )}
        {err && <p role="alert" className="sp-caption">{err}</p>}
      </div>
    </section>
  );
}
