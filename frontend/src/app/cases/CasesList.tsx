"use client";
/**
 * Cases, ops-console style (the Hub's look): every case at this hub as a dense table, newest first.
 * Tabs: All · Open · Resolved (a case is resolved once floor staff mark the parcel found). A filter box narrows by
 * tracking number. Each row says where the parcel stopped (from its own scans), when it was last scanned, how long ago
 * the case was opened, whether anyone has investigated it, and goes to the case on click. A new case starts from the
 * tracking-number search in the header. Loading: skeleton rows shaped like the table; empty: says how to start one.
 */
import Link from "next/link";
import { useMemo, useState } from "react";
import { useResource } from "@/lib/api";
import type { Journey } from "@/lib/journey";
import type { CaseListRow, Site } from "@/lib/types";
import { hhmm, lastScanSentence } from "@/lib/words";
import { ErrorState } from "@/components/ui";
import "./cases.css";

interface Dashboard { cases: { case_id: string; status: string }[] }
type Tone = "bad" | "warn" | "ok";
const PILL: Record<string, [string, Tone]> = { found: ["Found", "ok"], located: ["Likely location", "ok"], unknown: ["Lost track", "bad"] };
type Tab = "all" | "open" | "resolved";

const opened = (iso: string) => {
  const d = Math.floor((Date.now() - new Date(iso).getTime()) / 86400000);
  return d <= 0 ? "Today" : d === 1 ? "Yesterday" : `${d} days ago`;
};

export default function CasesList() {
  const sites = useResource<Site[]>("/v1/sites");
  const site = sites.data?.[0];
  const cases = useResource<CaseListRow[]>("/v1/cases");
  const dash = useResource<Dashboard>(site ? `/v1/sites/${site.site_id}/dashboard` : null);
  const [tab, setTab] = useState<Tab>("all");
  const [q, setQ] = useState("");
  const status = (id: string) => dash.data?.cases.find((c) => c.case_id === id)?.status ?? "unknown";
  const all = useMemo(() => [...(cases.data ?? [])].sort((a, b) => b.case.created_at.localeCompare(a.case.created_at)), [cases.data]);
  const resolvedN = all.filter((r) => status(r.case.case_id) === "found").length;
  const rows = all.filter((r) => {
    const found = status(r.case.case_id) === "found";
    if (tab === "open" && found) return false;
    if (tab === "resolved" && !found) return false;
    return !q.trim() || r.case.target_description.toUpperCase().includes(q.trim().toUpperCase());
  });
  const tabs: { id: Tab; label: string; n: number }[] = [
    { id: "all", label: "All", n: all.length },
    { id: "open", label: "Open", n: all.length - resolvedN },
    { id: "resolved", label: "Resolved", n: resolvedN },
  ];
  const ready = !!cases.data;
  return (
    <div className="cs">
      <header className="cs-head">
        <div>
          <h1 className="cs-title">Cases</h1>
          <p className="cs-sub">{ready ? `${all.length} case${all.length === 1 ? "" : "s"} at this hub, newest first` : "Reading the cases"}</p>
        </div>
      </header>

      {cases.error && <ErrorState error={cases.error} what="the cases" onRetry={cases.reload} />}

      <section className="cs-panel" aria-label="Cases">
        <div className="cs-tabbar">
          <div className="cs-tabs" role="tablist" aria-label="Case views">
            {tabs.map((t) => (
              <button key={t.id} type="button" role="tab" aria-selected={tab === t.id} tabIndex={tab === t.id ? 0 : -1} onClick={() => setTab(t.id)}>
                {t.label} <span className="cs-count">({t.n})</span>
              </button>
            ))}
          </div>
          <label className="cs-filter">
            <svg viewBox="0 0 20 20" aria-hidden="true"><circle cx="8.5" cy="8.5" r="5.5" /><path d="m12.6 12.6 4 4" /></svg>
            <span className="sp-sr">Filter cases by tracking number</span>
            <input type="search" placeholder="Filter by tracking number" value={q} onChange={(e) => setQ(e.target.value)} autoComplete="off" spellCheck={false} />
          </label>
        </div>

        {!ready ? (
          <div className="cs-table" aria-busy="true" aria-label="Loading">
            {[0, 1, 2].map((i) => (
              <div key={i} className="cs-tr cs-tr-skel">
                <span className="cs-skel" style={{ width: 84 }} /><span className="cs-skel" style={{ width: 150 }} />
                <span className="cs-skel" style={{ width: 210 }} /><span className="cs-skel" style={{ width: 52 }} />
              </div>
            ))}
          </div>
        ) : rows.length === 0 ? (
          <div className="cs-empty">
            <p className="cs-empty-h">{all.length === 0 ? "No cases yet" : q ? "No case matches that tracking number" : tab === "resolved" ? "Nothing resolved yet" : "No open cases"}</p>
            <p>
              {all.length === 0 ? "Type a parcel's tracking number in the search bar and press Enter. If it has scans at this hub you can open a case on it."
                : q ? "Check the number, or clear the filter."
                : tab === "resolved" ? "A case lands here once floor staff mark the parcel found."
                : "A case opens when a customer asks about a parcel, or when you investigate a stalled one on the Hub."}
            </p>
            {all.length === 0 && <Link className="cs-btn" href="/hub">Go to the Hub</Link>}
          </div>
        ) : (
          <div className="cs-table">
            <div className="cs-tr cs-th">
              <span>Status</span><span>Parcel</span><span>Where it stopped</span><span>Last scan</span><span>Opened</span><span>Investigated</span><span />
            </div>
            {rows.map((r) => <Row key={r.case.case_id} row={r} status={status(r.case.case_id)} />)}
          </div>
        )}
      </section>
    </div>
  );
}

function Row({ row, status }: { row: CaseListRow; status: string }) {
  const id = row.case.case_id;
  const j = useResource<Journey>(`/v1/cases/${id}/journey`);
  const run = useResource<{ steps: unknown[] }>(`/v1/cases/${id}/run`);
  const last = j.data?.objects[0]?.scans.at(-1);
  const [pill, tone] = PILL[status] ?? PILL.unknown;
  const waybill = row.case.target_description.split(" ").at(-1);
  const where = last ? lastScanSentence(last.event_kind, last.station_id, last.t).replace(/ at \d\d:\d\d\.$/, "") : j.data ? "No scans at this hub" : null;
  const done = (run.data?.steps.length ?? 0) > 0;
  return (
    <Link className="cs-tr cs-row" href={`/cases/${id}`}>
      <span><span className="cs-chip" data-tone={tone}>{pill}</span></span>
      <span className="cs-mono">{waybill}</span>
      <span className="cs-ellipsis">{where ?? <span className="cs-skel" style={{ width: 150 }} />}</span>
      <span className="cs-dim">{last ? hhmm(last.t) : ""}</span>
      <span className="cs-dim">{opened(row.case.created_at)}</span>
      <span className={done ? "cs-yes" : "cs-dim"}>{run.data ? (done ? "Yes" : "Not yet") : ""}</span>
      <span className="cs-chev" aria-hidden="true">›</span>
    </Link>
  );
}
