"use client";
/**
 * Hub home (QUEUE H15, review F-style #1-#3): the first screen a hub or regional manager opens. Tracking-number search
 * on top, then the exceptions inbox (parcels whose next expected scan is overdue, from the scan log) and the hub
 * dashboard. Alerting comes from the scan log; cameras are only analysed once a case is opened.
 */
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, useSyncExternalStore } from "react";
import { inboxQuery, readInboxClock, type InboxClock } from "@/lib/inboxClock";
import { api, ApiError, invalidate, useResource } from "@/lib/api";
import { describeScan } from "@/lib/scans";
import { clock } from "@/lib/journey";
import { fmtDate } from "@/lib/time";
import { zoneId } from "@/lib/hub";
import type { CaseListRow, Site } from "@/lib/types";
import { ErrorState, Loading } from "@/components/ui";
import { HubDashboard } from "@/components/dashboard/HubDashboard";
import { ZONE_NAMES } from "@/components/plan/HubPlan";
import "./hub.css";

interface Inbox {
  as_of: string | null;
  basis: string;
  rule?: string;
  counts: { parcels?: number; stalled?: number; in_progress?: number; closed?: number; cannot_judge?: number };
  stalled: { waybill: string; last_event_kind: string; raw_code: string | null; raw_description: string | null; read_point: string;
    zone_id: string | null; last_at: string; age_s: number; allowance_s: number; overdue_s: number; expected_next: string;
    case_id: string | null; proof?: { station: string; at: string } }[];
}

const age = (s: number) => (s < 90 ? `${Math.round(s)} s` : s < 5400 ? `${Math.round(s / 60)} min` : `${(s / 3600).toFixed(1)} h`);

export default function HubPage() {
  const sites = useResource<Site[]>("/v1/sites");
  const site = sites.data?.[0];
  const clockSetting = useSyncExternalStore(() => () => {}, () => JSON.stringify(readInboxClock()), () => "null");
  const inboxClock: InboxClock = clockSetting === "null" ? { kind: "log", minutes: 0 } : JSON.parse(clockSetting);
  const inbox = useResource<Inbox>(site ? `/v1/sites/${site.site_id}/exceptions?limit=50&${inboxQuery(inboxClock)}` : null);
  return (
    <div className="sp-page sp-stack hub" style={{ gap: 22 }}>
      <header className="hub-head">
        <div>
          <h1 className="sp-h1">Hub</h1>
        </div>
        <Search siteId={site?.site_id} />
      </header>

      <section className="sp-panel" aria-labelledby="inbox-h">
        <div className="sp-panel-head">
          <h2 className="sp-h3" id="inbox-h">Stalled parcels</h2>
          {inbox.data?.as_of && <span className="sp-caption" style={{ margin: 0 }} data-testid="inbox-clock">as of {fmtDate(inbox.data.as_of)}, {clock(inbox.data.as_of, true)} · {inbox.data.basis} · <Link href="/operator#inbox-clock">change in Operator</Link></span>}
        </div>
        <div className="sp-panel-body">
          {inbox.loading && <Loading lines={3} />}
          {inbox.error && <ErrorState error={inbox.error} what="the exceptions inbox" onRetry={inbox.reload} />}
          {inbox.data && inbox.data.stalled.length === 0 && (
            <div className="hub-empty" data-testid="inbox-empty">
              <p className="sp-strong" style={{ margin: 0, fontWeight: 620 }}>No stalled parcels.</p>
              <p className="sp-caption">{inbox.data.counts.parcels ?? 0} parcels in the imported scan log, {inbox.data.counts.in_progress ?? 0} still within the time their next scan is expected
                {inbox.data.counts.cannot_judge ? `, ${inbox.data.counts.cannot_judge} past it but the log ends before the next point shows the hub kept working (can't judge)` : ""}.
                A parcel appears here when that time runs out: catch it before the customer complains.</p>
            </div>
          )}
          {inbox.data && inbox.data.stalled.length > 0 && (
            <div className="sp-tablewrap">
              <table className="sp-table">
                <thead><tr><th>Waybill</th><th>Last scan</th><th>Where</th><th>Waiting for</th><th className="num">Overdue</th><th></th></tr></thead>
                <tbody>{inbox.data.stalled.map((r) => (
                  <tr key={r.waybill}>
                    <td className="sp-num">{r.waybill}</td>
                    <td>{describeScan({ event_kind: r.last_event_kind, raw_code: r.raw_code, raw_description: r.raw_description, device_id: r.read_point, station_id: r.read_point }).title}
                      <span className="sp-caption"> · {clock(r.last_at, true)}</span></td>
                    <td>{(r.zone_id && ZONE_NAMES[zoneId.toHub(r.zone_id)]) ?? r.read_point}</td>
                    <td>{r.expected_next}{r.proof && <span className="sp-caption" style={{ display: "block", margin: 0 }}>
                      {r.proof.station} kept scanning other parcels ({clock(r.proof.at, false)})</span>}</td>
                    <td className="num"><span className="sp-chip sp-chip-warn">{age(r.overdue_s)}</span></td>
                    <td>{r.case_id ? <Link className="sp-btn sp-btn-sm" href={`/cases/${r.case_id}/summary`}>Open case</Link>
                      : <OpenCase siteId={site!.site_id} waybill={r.waybill} />}</td>
                  </tr>
                ))}</tbody>
              </table>
            </div>
          )}
          {inbox.data && inbox.data.stalled.length > 0 && (inbox.data.counts.cannot_judge ?? 0) > 0 && (
            <p className="sp-caption">{inbox.data.counts.cannot_judge} more parcels are past their time, but the log ends before the next point shows the hub kept working: not counted.</p>
          )}
          {inbox.data?.rule && <p className="sp-caption">Rule: {inbox.data.rule}. Allowances come from the site plan&apos;s belt times plus operating limits for manual steps.</p>}
        </div>
      </section>

      <HubDashboard siteId={site?.site_id} />
    </div>
  );
}

function OpenCase({ siteId, waybill, label = "Open a case", primary = false }: { siteId: string; waybill: string; label?: string; primary?: boolean }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  return (
    <span>
      <button className={`sp-btn sp-btn-sm${primary ? " sp-btn-primary" : ""}`} disabled={busy} onClick={async () => {
        setBusy(true);
        setErr(null);
        try {
          const r = await api<{ case: { case_id: string } }>("/v1/cases", { method: "POST", json: {
            site_id: siteId, question: `Where did parcel ${waybill} go after its last scan?`, target_description: `parcel ${waybill}`,
            identifiers: [{ scheme: "carrier_waybill", value: waybill }] } });
          invalidate("/v1/cases");
          router.push(`/cases/${r.case.case_id}/summary`);
        } catch (e) {
          setErr(e instanceof ApiError && e.status === 403 ? "Needs the investigator role" : e instanceof Error ? e.message : String(e));
          setBusy(false);
        }
      }}>{busy ? "Opening" : label}</button>
      {err && <span className="sp-caption" role="alert"> {err}</span>}
    </span>
  );
}

/** Tracking-number search: an open case goes straight to its summary; otherwise the scan count and "Open a case". */
function Search({ siteId }: { siteId?: string }) {
  const [q, setQ] = useState("");
  const [hit, setHit] = useState<{ waybill: string; scans: number; caseId: string | null } | "none" | null>(null);
  const cases = useResource<CaseListRow[]>("/v1/cases");
  const router = useRouter();
  async function go(e: React.FormEvent) {
    e.preventDefault();
    const v = q.trim().toUpperCase();
    if (!siteId || !/^[A-Z0-9]{6,40}$/.test(v)) return;
    const open = cases.data?.find((c) => c.case.target_description.toUpperCase().endsWith(v));
    if (open) return router.push(`/cases/${open.case.case_id}/summary`);
    try {
      const r = await api<{ scans: unknown[] }>(`/v1/sites/${siteId}/parcels/carrier_waybill/${v}`);
      setHit(r.scans.length ? { waybill: v, scans: r.scans.length, caseId: null } : "none");
    } catch {
      setHit("none");
    }
  }
  return (
    <form className="hub-search" onSubmit={go} role="search">
      <label className="sp-sr" htmlFor="hub-q">Tracking number</label>
      <input id="hub-q" className="sp-input sp-num" value={q} onChange={(e) => { setQ(e.target.value); setHit(null); }}
        placeholder="Tracking number, e.g. CTX160258795857" autoComplete="off" />
      <button className="sp-btn sp-btn-primary" disabled={!siteId || q.trim().length < 6}>Find</button>
      {hit === "none" && <p className="sp-caption hub-hit">No scans of this tracking number at this hub.</p>}
      {hit && hit !== "none" && siteId && (
        <p className="sp-caption hub-hit">{hit.scans} scans of {hit.waybill}, no open case. <OpenCase siteId={siteId} waybill={hit.waybill} primary /></p>
      )}
    </form>
  );
}
