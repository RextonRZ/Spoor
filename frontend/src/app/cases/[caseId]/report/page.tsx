"use client";
/**
 * Report (step 4), ops-console style: "Close the case". The report itself is shown as a sheet (the answer, four key
 * moments, what to fix, what to tell the customer), and the actions sit beside it, docked: Download PDF (the full report
 * document, printable), Evidence video (the reel) and Share report. One demo user, so there is no approval step in the
 * UI; a shared report stays marked "not reviewer-approved" in the document, because the backend's four-eyes rule is kept.
 */
import { conflictWords, type Conflict } from "@/lib/conflict";
import Link from "next/link";
import { use, useEffect, useState } from "react";
import { API_BASE, api, previewUrl, signedUrl, useResource } from "@/lib/api";
import type { Journey, MissingMoment, XY } from "@/lib/journey";
import { hhmm, hms, momentLabel, placeOf, shortPlace } from "@/lib/words";
import { scanPoint } from "@/lib/hub";
import type { MediaRow, Site } from "@/lib/types";
import { CaseSteps } from "@/components/flow/CaseSteps";
import HubPlan, { ZONE_NAMES } from "@/components/plan/HubPlan";
import "@/app/hub/hub.css";
import "./report.css";

interface CaseState { case: { target_description: string; complaint?: string | null; created_at: string };
  answer?: { objects: { inside: { place: string; carried_in_at: string; iso: Record<string, string> } | null }[] } | null }
interface Draft { draft: string; facts: string[]; model: string; note: string; approved: boolean; sent: boolean; status?: string }
interface Possible { objects: { places: { area_id: string; name: string; zone_id: string | null; possible_share: number; centroid_xy: XY }[] }[] }
interface Conflicts { objects: { conflicts: Conflict[] }[] }
interface SearchView { found: { area_id: string; name: string; by: string; at: string } | null }
const low = (t: string) => t.charAt(0).toLowerCase() + t.slice(1); // keeps "C12"
interface Moment { key: string; t: string | null; text: string; who: string; xy: XY | null; frame?: string; cam?: string | null; tone?: "bad" | "ok";
  /** a clip that shows the moment (the frame is fetched from it) */
  media?: string }

/** the frame of a clip at a moment (a signed original frame) */
function MomentFrame({ media, t, alt }: { media: string; t: string; alt: string }) {
  const [url, setUrl] = useState<string | null>(null);
  useEffect(() => {
    let live = true;
    api<{ frame_url: string }>(`/v1/media/${media}/frame-at?time=${encodeURIComponent(t)}`).then((r) => live && setUrl(previewUrl(r.frame_url, 800))).catch(() => {});
    return () => { live = false; };
  }, [media, t]);
  // eslint-disable-next-line @next/next/no-img-element -- a signed CCTV frame
  return url ? <img src={url} alt={alt} /> : <span className="rp-fig-none" aria-busy="true" />;
}

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
  const saved = useResource<Draft | null>(`/v1/cases/${caseId}/customer-update`);
  const [drafted, setDrafted] = useState<Draft | null>(null);
  const [copied, setCopied] = useState(false);
  const upd = drafted ?? saved.data ?? null;
  const inside = st.data?.answer?.objects.find((o) => o.inside)?.inside ?? null;
  const sites = useResource<Site[]>("/v1/sites");
  const media = useResource<MediaRow[]>(sites.data?.[0] ? `/v1/sites/${sites.data[0].site_id}/media` : null);
  const clipAt = (hub: string, iso: string) => (media.data ?? []).find((m) => m.media.camera_id === `cam_${hub}` && !m.purged
    && m.coverage.some((c) => Date.parse(c.start_utc) <= Date.parse(iso) && Date.parse(iso) <= Date.parse(c.end_utc)))?.media.media_id;

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
  const head = found ? `Found in the ${foundPlace}.` : inside ? `Most likely in the ${inside.place}.` : last ? `Lost track after ${placeOf(last.event_kind, last.station_id)} at ${hms(last.t)}.` : "No scans of this parcel at this hub.";
  const story = last ? [
    `The last scan was ${low(momentLabel(last.event_kind, last.station_id))} at ${hms(last.t)}.`,
    conflict ? conflictWords(conflict).headline : "",
    found ? `Floor staff found it at ${hhmm(found.at)}.` : places.length ? `It could be in ${places.length} places; the most likely is the ${shortPlace(places[0], ZONE_NAMES)}.` : "",
  ].filter(Boolean).join(" ") : "";

  const records = (cr.data?.objects[0] as { records?: { t: string; event_kind?: string | null; station_id?: string | null }[] } | undefined)?.records ?? [];
  const truckRec = records.find((r) => r.event_kind === "container_loaded");
  const cage = scans.findLast((s) => s.event_kind === "container_add");
  const answered: Moment[] = inside ? [
    ...(cage ? [{ key: "cage", t: cage.t, text: low(momentLabel(cage.event_kind, cage.station_id)), who: "scan record", xy: null,
      cam: "CHK_CAGE_W", media: clipAt("CHK_CAGE_W", cage.t) }] : []),
    { key: "in", t: inside.iso.carried_in_at, text: `carried into the ${inside.place.replace(/ \(Z\d+\)$/, "").toLowerCase()}, not scanned in`, who: "camera", xy: null,
      cam: "CHK_STORE", media: clipAt("CHK_STORE", inside.iso.carried_in_at), tone: "bad" as const },
    ...(inside.iso.came_out_0 ? [{ key: "out", t: inside.iso.came_out_0, text: "came out without it", who: "camera", xy: null, cam: "CHK_STORE",
      media: clipAt("CHK_STORE", inside.iso.came_out_0) }] : []),
    ...(truckRec ? [{ key: "truck", t: truckRec.t, text: `record says loaded on truck ${truckRec.station_id?.match(/D\d{2}/)?.[0] ?? ""}, it never left`.replace("  ", " "),
      who: "records check", xy: null, cam: "CHK_DOCK", media: clipAt("CHK_DOCK", truckRec.t), tone: "bad" as const }] : []),
  ].filter((m) => m.media) : [];
  // four key moments: the last two scans, the records conflict, the floor search
  const moments: Moment[] = answered.length ? answered : [
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
  async function draftUpdate() {
    setBusy("customer"); setNote(null); setCopied(false);
    try { setDrafted(await api<Draft>(`/v1/cases/${caseId}/customer-update`, { method: "POST" })); }
    catch (e) { setNote(e instanceof Error ? e.message : String(e)); } finally { setBusy(null); }
  }
  async function approveCopy() {
    if (!upd?.draft) return;
    await navigator.clipboard?.writeText(upd.draft).catch(() => {});
    setCopied(true);
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
            <span className="rp-brand">
              {/* eslint-disable-next-line @next/next/no-img-element -- the brand's own logo file (light, for the paper) */}
              <img src="/brand/spoor-logo-light.png" alt="Spoor" width={78} height={25} /><span>Case report</span>
            </span>
            <span className="rp-ref">{waybill}</span>
          </header>
          <span className="rp-pill" data-tone={found || inside ? "ok" : ready ? "bad" : undefined}>{found ? `Found · ${hhmm(found.at)} by ${found.by}` : inside ? "Likely location found" : ready ? "Lost track" : "Checking"}</span>
          <h1 className="rp-h1">{ready || inside ? head : "Checking the records"}</h1>
          {story && <p className="rp-p">{story}</p>}

          {(ready || answered.length > 0) && <h2 className="rp-h2">Key moments</h2>}
          {(ready || answered.length > 0) && <div className="rp-frames">
            {moments.map((m) => (
              <figure key={m.key} className="rp-fig">
                {m.media && m.t ? <MomentFrame media={m.media} t={m.t} alt={m.text} /> : m.frame ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={signedUrl(m.frame)} alt={m.text} />
                ) : m.cam ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={`/cameras/${m.cam}.jpg`} alt={`${m.cam.replaceAll("_", " ")}'s view of the place`} loading="lazy" />
                ) : m.xy ? (
                  <span className="rp-fig-plan"><HubPlan label={m.text} focus={{ xy: m.xy, radius_m: 9, tone: m.tone === "bad" ? "bad" : "warn" }} legend={false} fit="contain" minHeight={0} /></span>
                ) : (
                  <span className="rp-fig-none" data-tone={m.tone}>{m.tone === "bad" ? "Records disagree" : m.tone === "ok" ? "Found" : "No picture"}</span>
                )}
                <figcaption data-tone={m.tone}><strong>{m.t ? hms(m.t) : "next"}</strong> · {m.text} · {m.cam ? `${m.cam.replaceAll("_", " ")} view` : m.who}</figcaption>
              </figure>
            ))}
          </div>}

          {conflict && (
            <>
              <h2 className="rp-h2">What to fix</h2>
              <p className="rp-p">{conflictWords(conflict).body}{conflict.kind === "custody" ? " The scan records and the cameras disagree about where it was." : " Ask the sorter team to check this parcel\u2019s tracking between induction and the chute."}</p>
            </>
          )}
          <h2 className="rp-h2" id="customer">Update for the customer who asked</h2>
          {upd?.draft ? (
            <div className="rp-cu">
              <p className="rp-cu-draft">{upd.draft}</p>
              <p className="rp-cu-meta">Draft from the verified answer only{upd.model === "template" ? "" : `, worded by ${upd.model}`}. A person approves it; customer service sends it. Spoor sends nothing.{upd.note ? ` ${upd.note}.` : ""}</p>
              <details className="rp-cu-facts"><summary>The facts it uses</summary><ul>{upd.facts.map((f) => <li key={f}>{f}</li>)}</ul></details>
              <div className="rp-cu-acts">
                <button type="button" className="hb-btn hb-btn-primary" onClick={approveCopy}>{copied ? "Approved and copied" : "Approve and copy"}</button>
                <button type="button" className="hb-btn" onClick={draftUpdate} disabled={busy === "customer"}>{busy === "customer" ? "Drafting…" : "Draft again"}</button>
              </div>
            </div>
          ) : upd?.status === "no_answer" || (st.data && !inside && !found) ? (
            <p className="rp-p">No verified answer yet, so there is nothing to tell the customer. The update is drafted once the investigation places it.</p>
          ) : (
            <div className="rp-cu-acts">
              <button type="button" className="hb-btn hb-btn-primary" onClick={draftUpdate} disabled={busy === "customer"}>{busy === "customer" ? "Drafting…" : "Draft the update to the customer"}</button>
              <span className="rp-cu-meta">From the verified answer only. Nothing is sent.</span>
            </div>
          )}

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
