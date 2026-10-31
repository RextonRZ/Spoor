"use client";
/**
 * Cases: every case at this hub, newest first, in the Hub's compact row style (review/refs/flow look). One sentence
 * per case from its own scans, a status pill, and Open. A new case starts from the tracking-number search in the top bar.
 */
import Link from "next/link";
import { useResource } from "@/lib/api";
import type { Journey } from "@/lib/journey";
import type { CaseListRow, Site } from "@/lib/types";
import { lastScanSentence, missingNextSentence } from "@/lib/words";
import { ErrorState } from "@/components/ui";
import "./cases.css";

interface Dashboard { cases: { case_id: string; status: string }[] }
const PILL: Record<string, [string, string]> = { found: ["Found", "ok"], located: ["Likely location", "ok"], unknown: ["Lost track", "bad"] };

export default function CasesPage() {
  const sites = useResource<Site[]>("/v1/sites");
  const site = sites.data?.[0];
  const cases = useResource<CaseListRow[]>("/v1/cases");
  const dash = useResource<Dashboard>(site ? `/v1/sites/${site.site_id}/dashboard` : null);
  const rows = [...(cases.data ?? [])].sort((a, b) => b.case.created_at.localeCompare(a.case.created_at));
  const status = (id: string) => dash.data?.cases.find((c) => c.case_id === id)?.status ?? "unknown";
  return (
    <div className="cs">
      <div className="cs-main">
        <div>
          <p className="cs-site">{rows.length} case{rows.length === 1 ? "" : "s"} at this hub</p>
          <h1 className="cs-h1">Cases</h1>
        </div>
        {cases.error && <ErrorState error={cases.error} what="the cases" onRetry={cases.reload} />}
        {cases.data && rows.length === 0 && <p className="cs-empty">No cases yet. Find a parcel by its tracking number in the bar above to open one.</p>}
        {rows.map((r) => <Row key={r.case.case_id} row={r} status={status(r.case.case_id)} />)}
      </div>
    </div>
  );
}

function Row({ row, status }: { row: CaseListRow; status: string }) {
  const j = useResource<Journey>(`/v1/cases/${row.case.case_id}/journey`);
  const last = j.data?.objects[0]?.scans.at(-1);
  const [pill, tone] = PILL[status] ?? PILL.unknown;
  const waybill = row.case.target_description.split(" ").at(-1);
  return (
    <article className="cs-row">
      <div className="cs-body">
        <span className="cs-pill" data-tone={tone}>{pill}</span>
        <span className="cs-say">{last ? `${lastScanSentence(last.event_kind, last.station_id, last.t)} ${missingNextSentence(last.event_kind)}` : j.data ? "No scans of this parcel at this hub." : "Reading the scans"}</span>
        <span className="cs-foot">{waybill}{row.case.complaint ? " · customer says it never arrived" : ""}</span>
      </div>
      <Link className="cs-btn" href={`/cases/${row.case.case_id}`}>Open</Link>
    </article>
  );
}
