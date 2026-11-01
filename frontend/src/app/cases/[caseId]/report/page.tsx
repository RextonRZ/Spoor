"use client";
/**
 * Report (step 4), ops-console style: "Close the case". The report itself is shown as a sheet (the answer, four key
 * moments, what to fix, what to tell the customer), and the actions sit beside it, docked: Download PDF (the full report
 * document, printable), Evidence video (the reel) and Share report. One demo user, so there is no approval step in the
 * UI; a shared report stays marked "not reviewer-approved" in the document, because the backend's four-eyes rule is kept.
 */
import { conflictWords, type Conflict } from "@/lib/conflict";
import Link from "next/link";
import { use, useState } from "react";
import { API_BASE, api, signedUrl, useResource } from "@/lib/api";
import type { Journey, MissingMoment, XY } from "@/lib/journey";
import { hhmm, hms, momentLabel, placeOf, shortPlace } from "@/lib/words";
import { scanPoint } from "@/lib/hub";
import { CaseSteps } from "@/components/flow/CaseSteps";
import HubPlan, { ZONE_NAMES } from "@/components/plan/HubPlan";
import "@/app/hub/hub.css";
import "./report.css";

interface CaseState { case: { target_description: string; complaint?: string | null; created_at: string } }
interface Possible { objects: { places: { area_id: string; name: string; zone_id: string | null; possible_share: number; centroid_xy: XY }[] }[] }
interface Conflicts { objects: { conflicts: Conflict[] }[] }
interface SearchView { found: { area_id: string; name: string; by: string; at: string } | null }
const low = (t: string) => t.charAt(0).toLowerCase() + t.slice(1); // keeps "C12"
interface Moment { key: string; t: string | null; text: string; who: string; xy: XY | null; frame?: string; cam?: string | null; tone?: "bad" | "ok" }

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
    conflict ? conflictWords(conflict).headline : "",
    found ? `Floor staff found it at ${hhmm(found.at)}.` : places.length ? `It could be in ${places.length} places; the most likely is the ${shortPlace(places[0], ZONE_NAMES)}.` : "",
  ].filter(Boolean).join(" ") : "";

  // four key moments: the last two scans, the records conflict, the floor search
  const moments: Moment[] = [
    ...scans.slice(-2).map((s) => ({ key: s.scan_event_id, t: s.t, text: low(momentLabel(s.event_kind, s.station_id)),
      who: "scan record", xy: s.xy, cam: scanPoint(s.station_id ?? s.device_id)?.visible_by[0] ?? null,
      frame: s.scan_event_id === lc?.evidence_id ? lc?.frames?.[0]?.frame_url : undefined })),
    ...(conflict ? [{ key: "conflict", t: conflict.divergence_t, text: conflictWords(conflict).short, who: "records check", xy: null, tone: "bad" as const }] : []),
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

  const checks: [string, boolean][] = [
    ["Answer reviewed", !!last],
    ["Checked on camera", !!lc || scans.length > 0],
    ["Floor search", !!sr.data && (found !== null || !!sr.data.found)],
  ];

  return (
    <div className="rp">
      <CaseSteps caseId={caseId} waybill={waybill} page="Report" here={3} />
      <div className="rp-body">
        <article className="rp-sheet" aria-label="Case report">
          <header className="rp-sheet-head">
            <span className="rp-brand">Spoor · Case report</span>
            <span className="rp-ref">{waybill}</span>
          </header>
          <span className="rp-pill" data-tone={found ? "ok" : "bad"}>{found ? `Found · ${hhmm(found.at)} by ${found.by}` : "Lost track"}</span>
          <h1 className="rp-h1">{ready ? head : "Checking the records"}</h1>
          {story && <p className="rp-p">{story}</p>}

          <h2 className="rp-h2">Key moments</h2>
          <div className="rp-frames">
            {moments.map((m) => (
              <figure key={m.key} className="rp-fig">
                {m.frame ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={signedUrl(m.frame)} alt={m.text} />
                ) : m.cam ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={`/cameras/${m.cam}.jpg`} alt={`${m.cam.replace("_", " ")}'s view of the place`} loading="lazy" />
                ) : m.xy ? (
                  <span className="rp-fig-plan"><HubPlan label={m.text} focus={{ xy: m.xy, radius_m: 9, tone: m.tone === "bad" ? "bad" : "warn" }} legend={false} fit="contain" minHeight={0} /></span>
                ) : (
                  <span className="rp-fig-none" data-tone={m.tone}>{m.tone === "bad" ? "Records disagree" : m.tone === "ok" ? "Found" : "No picture"}</span>
                )}
                <figcaption><strong>{m.t ? hms(m.t) : "next"}</strong> · {m.text} · {m.cam ? `${m.cam.replace("_", " ")} view` : m.who}</figcaption>
              </figure>
            ))}
          </div>

          {conflict && (
            <>
              <h2 className="rp-h2">What to fix</h2>
              <p className="rp-p">{conflictWords(conflict).body}{conflict.kind === "custody" ? " The scan records and the cameras disagree about where it was." : " Ask the sorter team to check this parcel\u2019s tracking between induction and the chute."}</p>
            </>
          )}
          <h2 className="rp-h2">For the customer</h2>
          <p className="rp-p">{found ? "The parcel is in the hub and goes out on the next run." : `We are checking ${places.length || "the"} places in the hub where it could be. We will update you as soon as it is found.`}</p>

          <div className="rp-plan"><HubPlan label="Floor plan with the parcel's route" journey={j} fit="width" legend={false} quiet /></div>
          <footer className="rp-fine">Decision support, not a forensic certificate. Every parcel leaves a trail. Spoor reads it.</footer>
        </article>

        <aside className="rp-dock" aria-label="Close the case">
          <h2 className="rp-dock-h">Close the case</h2>
          <ul className="rp-checks">
            {checks.map(([label, ok]) => <li key={label} data-ok={ok ? "" : undefined}><i aria-hidden="true">{ok ? <svg viewBox="0 0 16 16"><path d="m3.5 8.5 3 3 6-6.5" /></svg> : null}</i>{label}</li>)}
          </ul>
          <div className="rp-acts">
            <button type="button" className="hb-btn hb-btn-primary" onClick={share} disabled={!!busy}>{busy === "share" ? "Sharing" : "Share report"}</button>
            <button type="button" className="hb-btn" onClick={download} disabled={!!busy}>{busy === "pdf" ? "Preparing" : "Download PDF"}</button>
            <button type="button" className="hb-btn" onClick={video} disabled={!!busy}>{busy === "reel" ? "Building" : "Evidence video"}</button>
          </div>
          {note && <p className="rp-note" role="status">{note}</p>}
          {reel && <video className="rp-reel" controls src={reel} aria-label="Evidence video" />}
          <p className="rp-dock-fine">A shared report is marked &ldquo;not reviewer-approved&rdquo;: this demo has one user.</p>
          <Link className="rp-back" href={`/cases/${caseId}`}>Back to the answer</Link>
        </aside>
      </div>
    </div>
  );
}
