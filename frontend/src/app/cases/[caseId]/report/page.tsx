"use client";
/**
 * Report, ported from review/refs/flow/Report.dc.html (owner 09:22/09:24): the answer, four key moments, what to fix,
 * what to tell the customer, and three actions: Download PDF (the full report document, printable), Evidence video
 * (the reel) and Share report. One demo user, so there is no approval step in the UI; a shared report stays marked
 * "not reviewer-approved" in the document, because the backend's four-eyes rule is kept.
 */
import Link from "next/link";
import { use, useState } from "react";
import { API_BASE, api, signedUrl, useResource } from "@/lib/api";
import type { Journey, MissingMoment, XY } from "@/lib/journey";
import { hhmm, hms, momentLabel, placeOf, shortPlace } from "@/lib/words";
import { CaseSteps } from "@/components/flow/CaseSteps";
import HubPlan, { ZONE_NAMES } from "@/components/plan/HubPlan";
import "./report.css";

interface CaseState { case: { target_description: string; complaint?: string | null; created_at: string } }
interface Possible { objects: { places: { area_id: string; name: string; zone_id: string | null; possible_share: number; centroid_xy: XY }[] }[] }
interface Conflicts { objects: { conflicts: { divergence_t: string; statement: string }[] }[] }
interface SearchView { found: { area_id: string; name: string; by: string; at: string } | null }
const low = (t: string) => t.charAt(0).toLowerCase() + t.slice(1); // keeps "C12"
interface Moment { key: string; t: string | null; text: string; who: string; xy: XY | null; frame?: string; tone?: "bad" | "ok" }

export default function ReportPage({ params }: { params: Promise<{ caseId: string }> }) {
  const { caseId } = use(params);
  const st = useResource<CaseState>(`/v1/cases/${caseId}/state`);
  const jr = useResource<Journey>(`/v1/cases/${caseId}/journey`);
  const mr = useResource<MissingMoment>(`/v1/cases/${caseId}/missing-moment`);
  const pr = useResource<Possible>(`/v1/cases/${caseId}/possible-locations`);
  const cr = useResource<Conflicts>(`/v1/cases/${caseId}/conflicts`);
  const sr = useResource<SearchView>(`/v1/cases/${caseId}/search-tasks`);
  const [busy, setBusy] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const [reel, setReel] = useState<string | null>(null);

  const j = jr.data?.objects[0];
  const scans = j?.scans ?? [];
  const last = scans.at(-1);
  const lc = mr.data?.objects[0]?.last_confirmed;
  const places = (pr.data?.objects[0]?.places ?? []).filter((p) => p.possible_share > 0);
  const conflict = cr.data?.objects[0]?.conflicts[0];
  const found = sr.data?.found ?? null;
  const waybill = st.data?.case.target_description.split(" ").at(-1) ?? "";
  const ready = !!(j && mr.data && pr.data && cr.data && sr.data);

  const foundPlace = found ? shortPlace({ area_id: found.area_id, name: found.name, zone_id: `zone_${found.area_id}` }, ZONE_NAMES) : null;
  const head = found ? `Found in the ${foundPlace}.` : last ? `Lost track after ${placeOf(last.event_kind, last.station_id)} at ${hms(last.t)}.` : "No scans of this parcel at this hub.";
  const story = last ? [
    `The last scan was ${low(momentLabel(last.event_kind, last.station_id))} at ${hms(last.t)}.`,
    conflict ? "The sorter's own times for this parcel don't fit the belt, so one of its records is wrong." : "",
    found ? `Floor staff found it at ${hhmm(found.at)}.` : places.length ? `It could be in ${places.length} places; the most likely is the ${shortPlace(places[0], ZONE_NAMES)}.` : "",
  ].filter(Boolean).join(" ") : "";

  // four key moments: the last two scans, the records conflict, the floor search
  const moments: Moment[] = [
    ...scans.slice(-2).map((s) => ({ key: s.scan_event_id, t: s.t, text: low(momentLabel(s.event_kind, s.station_id)),
      who: "scan record", xy: s.xy, frame: s.scan_event_id === lc?.evidence_id ? lc?.frames?.[0]?.frame_url : undefined })),
    ...(conflict ? [{ key: "conflict", t: conflict.divergence_t, text: "the sorter's times don't fit the belt", who: "records check", xy: null, tone: "bad" as const }] : []),
    found ? { key: "found", t: found.at, text: `found in the ${foundPlace}`, who: found.by, xy: null, tone: "ok" as const }
      : { key: "search", t: null, text: places.length ? `go look: ${shortPlace(places[0], ZONE_NAMES)}` : "no place left to search", who: "floor search", xy: places[0]?.centroid_xy ?? null },
  ].slice(0, 4).sort((x, y) => (x.t ?? "9").localeCompare(y.t ?? "9")); // in time order; "next" last

  async function exportReport(): Promise<string> {
    const r = await api<{ report_id: string }>(`/v1/cases/${caseId}/export`, { method: "POST" });
    return `${API_BASE}/v1/reports/${r.report_id}?format=html`;
  }
  async function download() {
    setBusy("pdf"); setNote(null);
    try {
      const url = await exportReport();
      const w = window.open(url, "_blank");
      w?.addEventListener("load", () => w.print());
    } catch (e) { setNote(e instanceof Error ? e.message : String(e)); } finally { setBusy(null); }
  }
  async function video() {
    setBusy("reel"); setNote(null);
    try { const r = await api<{ url: string }>(`/v1/cases/${caseId}/reel`, { method: "POST" }); setReel(signedUrl(r.url)); }
    catch (e) { setNote(e instanceof Error ? e.message : String(e)); } finally { setBusy(null); }
  }
  async function share() {
    setBusy("share"); setNote(null);
    try {
      const url = new URL(await exportReport(), window.location.href).toString();
      await navigator.clipboard?.writeText(url).catch(() => {});
      setNote("Report link copied.");
    } catch (e) { setNote(e instanceof Error ? e.message : String(e)); } finally { setBusy(null); }
  }

  return (
    <div className="rp">
      <CaseSteps caseId={caseId} waybill={waybill} page="Report" here={3} />
      <div className="rp-main">
        <div className="rp-top">
          <div className="rp-answer">
            <span className="rp-pill" data-tone={found ? "ok" : "bad"}>{found ? `Found · ${hhmm(found.at)} by ${found.by}` : "Lost track"}</span>
            <h1 className="rp-h1">{ready ? head : "Checking the records"}</h1>
            {story && <p className="rp-p">{story}</p>}
          </div>
          <div className="rp-acts">
            <button type="button" className="rp-btn" onClick={download} disabled={!!busy}>{busy === "pdf" ? "Preparing" : "Download PDF"}</button>
            <button type="button" className="rp-btn" onClick={video} disabled={!!busy}>{busy === "reel" ? "Building" : "Evidence video"}</button>
            <button type="button" className="rp-btn rp-btn-primary" onClick={share} disabled={!!busy}>{busy === "share" ? "Sharing" : "Share report"}</button>
          </div>
        </div>
        {note && <p className="rp-note" role="status">{note}</p>}
        {reel && <video className="rp-reel" controls src={reel} aria-label="Evidence video" />}

        <div className="rp-frames">
          {moments.map((m) => (
            <figure key={m.key} className="rp-fig">
              {m.frame ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={signedUrl(m.frame)} alt={m.text} />
              ) : m.xy ? (
                <span className="rp-fig-plan"><HubPlan label={m.text} focus={{ xy: m.xy, radius_m: 9, tone: m.tone === "bad" ? "bad" : "warn" }} legend={false} fit="contain" minHeight={0} /></span>
              ) : (
                <span className="rp-fig-none" data-tone={m.tone}>{m.tone === "bad" ? "Records disagree" : m.tone === "ok" ? "Found" : "No picture"}</span>
              )}
              <figcaption><strong>{m.t ? hms(m.t) : "next"}</strong> · {m.text} · {m.who}</figcaption>
            </figure>
          ))}
        </div>

        <div className="rp-bottom">
          <section className="rp-card">
            {conflict && (
              <>
                <h2>What to fix</h2>
                <p>The sorter&apos;s records for this parcel don&apos;t add up: {conflict.statement.replace(/: the records conflict$/, "")}. Ask the sorter team to check this parcel&apos;s tracking between induction and the chute.</p>
              </>
            )}
            <h2 className={conflict ? "rp-h2-gap" : undefined}>For the customer</h2>
            <p>{found ? "The parcel is in the hub and goes out on the next run." : `We are checking ${places.length || "the"} places in the hub where it could be. We will update you as soon as it is found.`}</p>
          </section>
          <section className="rp-side">
            <div className="rp-plan"><HubPlan label="Floor plan with the parcel's route" journey={j} fit="width" legend={false} quiet /></div>
            <p className="rp-fine">Decision support, not a forensic certificate. Full evidence list, recordings and their fingerprints in the{" "}
              <button type="button" className="rp-link" onClick={download}>full report</button>.</p>
          </section>
        </div>
        <p className="rp-tag">Every parcel leaves a trail. Spoor reads it.</p>
        <p className="rp-back"><Link href={`/cases/${caseId}`}>Back to the answer</Link></p>
      </div>
    </div>
  );
}
