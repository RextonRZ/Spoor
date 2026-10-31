"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { api, invalidate, useResource } from "@/lib/api";
import { fmtDate, fmtTime, TZ_LABEL } from "@/lib/time";
import type { Capabilities, CameraRow, CaseListRow, ScanRow, Site } from "@/lib/types";
import { Empty, ErrorState, Loading } from "@/components/ui";

export default function CasesPage() {
  const sites = useResource<Site[]>("/v1/sites");
  const site = sites.data?.[0];
  const cases = useResource<CaseListRow[]>("/v1/cases");
  const cams = useResource<CameraRow[]>(site ? `/v1/sites/${site.site_id}/cameras` : null);
  const scans = useResource<{ total: number; scans: ScanRow[] }>(site ? `/v1/sites/${site.site_id}/scans?limit=1` : null);
  const caps = useResource<Capabilities>("/v1/capabilities");
  const withFootage = cams.data?.filter((c) => c.coverage.length > 0).length ?? 0;

  return (
    <div className="sp-page sp-stack" style={{ gap: 24 }}>
      <header>
        <p className="sp-eyebrow">Parcel investigations</p>
        <h1 className="sp-h1">Cases</h1>
        <p className="sp-muted sp-body" style={{ marginTop: 6 }}>
          Each case traces one consignment reported not received. The scan history says where it was scanned; footage
          and what has been observed in it can show where it went. Answers come only from stored evidence.
        </p>
      </header>

      <section aria-labelledby="site-h" className="sp-tint" style={{ padding: "20px 22px" }}>
        <div className="sp-row sp-wrap" style={{ justifyContent: "space-between", gap: 12 }}>
          <div>
            <p className="sp-micro" id="site-h">Site</p>
            <div className="sp-h3" style={{ marginTop: 4 }}>{site?.name ?? (sites.loading ? "Loading site" : "No site registered")}</div>
          </div>
          <dl className="sp-row sp-wrap" style={{ gap: 28, margin: 0 }}>
            <Stat label="Cameras" value={cams.data ? String(cams.data.length) : "…"} />
            <Stat label="With footage" value={cams.data ? String(withFootage) : "…"} />
            <Stat label="Scan events" value={scans.data ? String(scans.data.total) : "…"} />
            <Stat label="Model analysis" value={caps.data ? (caps.data.sam || caps.data.spark ? "On" : "Off") : "…"}
              hint={caps.data && !caps.data.sam ? "no API key" : undefined} />
          </dl>
        </div>
        {sites.error && <div style={{ marginTop: 12 }}><ErrorState error={sites.error} what="the site" onRetry={sites.reload} /></div>}
      </section>

      <div className="sp-home-grid">
        <section aria-labelledby="cases-h" className="sp-panel">
          <div className="sp-panel-head"><h2 className="sp-h3" id="cases-h">Open cases</h2>
            <span className="sp-muted" style={{ fontSize: 12 }}>{cases.data?.length ?? 0} total</span></div>
          <div className="sp-panel-body">
            {cases.loading && <Loading label="Loading cases" />}
            {cases.error && <ErrorState error={cases.error} what="cases" onRetry={cases.reload} />}
            {cases.data && cases.data.length === 0 && (
              <Empty title="No cases yet">Start one with the waybill number of the parcel.</Empty>
            )}
            {cases.data && cases.data.length > 0 && (
              <ul className="sp-list" style={{ gap: 0 }}>
                {cases.data.map((c) => (
                  <li key={c.case.case_id} style={{ borderBottom: "1px solid var(--hairline)" }}>
                    <Link href={`/cases/${c.case.case_id}`} className="sp-caserow">
                      <span className="sp-grow">
                        <span className="sp-strong" style={{ fontWeight: 600, display: "block" }}>{c.case.question}</span>
                        <span className="sp-caption">{c.case.target_description} · opened {fmtDate(c.case.created_at)}{" "}
                          {fmtTime(c.case.created_at, false)} {TZ_LABEL}</span>
                      </span>
                      
                      <span className={c.report_status === "approved" ? "sp-chip sp-chip-safe" : "sp-chip"}>
                        {c.report_status ? `report ${c.report_status}` : "no report"}
                      </span>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </section>
        <NewCase siteId={site?.site_id} cameras={cams.data ?? []} />
      </div>
      <style>{`.sp-home-grid{display:grid;gap:20px;grid-template-columns:minmax(0,1.6fr) minmax(0,1fr)}
        @media (max-width: 900px){.sp-home-grid{grid-template-columns:minmax(0,1fr)}}
        .sp-caserow{display:flex;align-items:center;gap:12px;padding:12px 6px;text-decoration:none;border-radius:10px}
        .sp-caserow:hover{background:color-mix(in srgb, var(--accent) 6%, var(--surface-2))}`}</style>
    </div>
  );
}

function Stat({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div>
      <dt className="sp-micro">{label}</dt>
      <dd className="sp-num sp-strong" style={{ margin: "2px 0 0", fontSize: 22, fontWeight: 600 }}>{value}</dd>
      {hint && <dd className="sp-caption" style={{ margin: 0 }}>{hint}</dd>}
    </div>
  );
}

function NewCase({ siteId, cameras }: { siteId?: string; cameras: CameraRow[] }) {
  const router = useRouter();
  const [waybill, setWaybill] = useState("");
  const [question, setQuestion] = useState("");
  const [claimRef, setClaimRef] = useState("");
  const [complaint, setComplaint] = useState("");
  const [reported, setReported] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const scanHit = useResource<{ scans: unknown[] }>(
    siteId && /^[A-Za-z0-9]{6,40}$/.test(waybill) ? `/v1/sites/${siteId}/parcels/carrier_waybill/${waybill}` : null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!siteId) return;
    setBusy(true);
    setErr(null);
    try {
      const r = await api<{ case: { case_id: string } }>("/v1/cases", { method: "POST", json: {
        site_id: siteId,
        question: question.trim() || `Where did parcel ${waybill} go after its last scan?`,
        target_description: `parcel ${waybill}`,
        camera_ids: cameras.filter((c) => c.coverage.length).map((c) => c.camera.camera_id),
        identifiers: [{ scheme: "carrier_waybill", value: waybill }],
        // The complaint as the customer gave it (review 012 #3). Left empty = "not recorded" in the report.
        claim_reference: claimRef.trim() || null,
        complaint: complaint.trim() || null,
        reported_at: reported ? `${reported}T00:00:00+08:00` : null,
      } });
      invalidate("/v1/cases");
      router.push(`/cases/${r.case.case_id}`);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
      setBusy(false);
    }
  }

  return (
    <section aria-labelledby="new-h" className="sp-panel">
      <div className="sp-panel-head"><h2 className="sp-h3" id="new-h">Start a case</h2></div>
      <form className="sp-panel-body sp-stack" onSubmit={submit}>
        <label className="sp-field">
          <span className="sp-label">Waybill / tracking no. <span className="sp-muted">(consignment note, AWB)</span></span>
          <input className="sp-input sp-num" value={waybill} onChange={(e) => setWaybill(e.target.value.trim())}
            placeholder="e.g. CTX026892360674" required pattern="[A-Za-z0-9]{6,40}" autoComplete="off" />
          <span className="sp-caption">
            {scanHit.data ? `${scanHit.data.scans.length} scan events found for this waybill`
              : "The number on the consignment note the customer quotes. Identity comes from scans of it; footage alone cannot tell look-alike parcels apart."}
          </span>
        </label>
        <label className="sp-field">
          <span className="sp-label">Customer&apos;s complaint <span className="sp-muted">(as reported)</span></span>
          <textarea className="sp-input" rows={2} value={complaint} onChange={(e) => setComplaint(e.target.value)}
            maxLength={1000} placeholder="e.g. Parcel shows 'in transit' since 28 Oct, never arrived." />
        </label>
        <div className="sp-row sp-wrap" style={{ gap: 12 }}>
          <label className="sp-field sp-grow">
            <span className="sp-label">Claim reference <span className="sp-muted">(optional)</span></span>
            <input className="sp-input sp-num" value={claimRef} onChange={(e) => setClaimRef(e.target.value)}
              maxLength={80} autoComplete="off" />
          </label>
          <label className="sp-field">
            <span className="sp-label">Date reported</span>
            <input className="sp-input sp-num" type="date" value={reported} onChange={(e) => setReported(e.target.value)} />
          </label>
        </div>
        <label className="sp-field">
          <span className="sp-label">Question <span className="sp-muted">(optional)</span></span>
          <input className="sp-input" value={question} onChange={(e) => setQuestion(e.target.value)}
            placeholder="Where did this parcel go after its last scan?" />
        </label>
        {err && <div role="alert" className="sp-state sp-state-error">{err}</div>}
        <div><button className="sp-btn sp-btn-primary" disabled={!siteId || !waybill || busy}>
          {busy ? "Opening case" : "Open the case"}</button></div>
        <p className="sp-caption">Requires the investigator role. Cameras in scope: every camera with footage.</p>
      </form>
    </section>
  );
}
