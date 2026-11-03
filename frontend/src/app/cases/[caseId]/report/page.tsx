"use client";
/**
 * Report (step 4): the case file a hub manager signs (Rexton 3 Nov; reviewer 03:40 spec). One paper sheet, A4 when
 * printed, six sections in the order a reader asks: what happened (summary, how sure), the journey on camera (the reel
 * and EVERY step as its own frame card, the frames the API cut from the reel), where (a clean vector plan: the route
 * numbered like the cards, solid where a camera saw it, dashed where none did, the cameras used, the answer zone), the
 * records against the cameras, the floor check, and the evidence list (clips with SHA-256, models and cost, limits).
 * "Draft the update to the customer" opens a side sheet beside the report (not over it): channel, language, tone, the
 * draft from verified facts only with each fact linked to its frame, Approve and send (a person approves; in this demo
 * nothing leaves Spoor: an audited record), Copy text.
 */
import Link from "next/link";
import { use, useMemo, useState } from "react";
import { api, invalidate, signedUrl, useResource } from "@/lib/api";
import type { Conflict } from "@/lib/conflict";
import type { Journey, XY } from "@/lib/journey";
import { hhmm, hms } from "@/lib/words";
import { HUB } from "@/lib/hub";
import { CaseSteps } from "@/components/flow/CaseSteps";
import type { Chapter, Reel } from "@/components/case/JourneyReel";
import { waited } from "@/components/hub/parts";
import FloorPlan, { type FPCam, type FPLeg, type FPStop } from "@/components/plan/FloorPlan";
import "@/app/hub/hub.css";
import "./report.css";

interface CaseState { case: { case_id: string; target_description: string; complaint?: string | null; created_at: string };
  answer?: { objects: { inside: { place: string; carried_in_at: string; iso: Record<string, string> } | null }[] } | null }
interface Conflicts { objects: { conflicts: Conflict[] }[] }
interface SearchView { found: { area_id: string; name: string; by: string; at: string } | null;
  tasks: { search_task_id: string; created_at: string; places: { area_id: string; name: string }[];
    outcomes: { area_id: string; outcome: "found" | "not_found"; note?: string | null; recorded_by?: string; recorded_at?: string }[] }[] }
interface Draft { status?: string; draft: string; facts: string[]; refs?: ({ kind: string; at?: string; label: string } | null)[]; model: string;
  note: string; approved: boolean; sent: boolean; stage?: string; channel?: string; language?: string; tone?: string; approved_by?: string;
  sent_at?: string; edited?: boolean }
interface RunView { steps: { type: string; t_s?: number; cost_usd?: number; text?: string; model?: string; role?: string }[];
  crew: { role: string; who: string; model: string }[] }
type Source = { kind: string; camera?: string; sha256?: string; frames?: number[]; title?: string; path?: string };
type FullReel = Reel & { sources?: Source[] };

const CHIP: Record<string, string> = { scan: "Scanned", seen: "On camera", noscan: "Not scanned in", record: "Records disagree", wait: "No camera", card: "Answer" };
const CLOSE: Record<string, string> = { UNLOAD: "Unload", TUNNEL: "Tunnel", CAGE_W: "Cage", CAGE_E: "Cage", STORE: "Store door", DOCK: "Dock", CHUTE: "Chute" };
const camWords = (c: string) => c === "Tunnel reader" ? "Tunnel reader's photo"
  : c.startsWith("CHK_") ? `${CLOSE[c.slice(4)] ?? c.slice(4)} close-up camera` : c.replace("_", " ");
const modelName = (m: string) => /spark-open/i.test(m) ? "Muse Spark Open" : /spark/i.test(m) ? "Muse Spark" : /wonder/i.test(m) ? "Muse Wonder" : m;
const floorName = (n: string) => n.replace(/^Z\d+ /, "").replace(/\s*[(,;].*$/, "");
const day = (iso: string) => new Date(iso).toLocaleDateString("en-GB", { timeZone: "Asia/Kuala_Lumpur", day: "numeric", month: "short", year: "numeric" });

export default function ReportPage({ params }: { params: Promise<{ caseId: string }> }) {
  const { caseId } = use(params);
  const st = useResource<CaseState>(`/v1/cases/${caseId}/state`);
  const jr = useResource<Journey>(`/v1/cases/${caseId}/journey`);
  const cr = useResource<Conflicts>(`/v1/cases/${caseId}/conflicts`);
  const sr = useResource<SearchView>(`/v1/cases/${caseId}/search-tasks`);
  const rr = useResource<FullReel>(`/v1/cases/${caseId}/journey-reel`);
  const run = useResource<RunView>(`/v1/cases/${caseId}/run`);
  const saved = useResource<Draft | null>(`/v1/cases/${caseId}/customer-update`);
  const [sheet, setSheet] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const [flash, setFlash] = useState<number | null>(null);

  const waybill = st.data?.case.target_description.split(" ").at(-1) ?? "";
  const scans = jr.data?.objects[0]?.scans ?? [];
  const last = scans.at(-1);
  const inside = st.data?.answer?.objects.find((o) => o.inside)?.inside ?? null;
  const conflict = cr.data?.objects[0]?.conflicts[0];
  const found = sr.data?.found ?? null;
  const task = sr.data?.tasks.at(-1);
  const chapters: Chapter[] = useMemo(() => rr.data?.chapters ?? [], [rr.data]);
  const steps = chapters.filter((c) => c.tone !== "card");
  const wait = last && st.data ? waited(last.t, st.data.case.created_at) : null;
  const end = run.data?.steps.findLast((s) => s.type === "run_end");
  const sent = saved.data?.sent ? saved.data : null;
  const place = inside?.place.replace(/\s*\(Z\d+\)$/, "") ?? null;

  // nothing is claimed until the case, its scans and the floor search have loaded (it flashed "No scans" first)
  const loaded = !!(st.data && jr.data && sr.data);
  const head = !loaded ? "" : found ? `Found in the ${found.name.replace(/\s*\(Z\d+\)$/, "")}.` : inside ? `Most likely in the ${place}.`
    : last ? "Lost track after the last scan." : "No scans of this parcel at this hub.";
  const summary = [
    last ? `${waybill} was last scanned at ${hhmm(last.t)} on ${day(last.t)}, ${(steps.find((c) => c.last_scan)?.title ?? "at the hub").replace(/^\w/, (x) => x.toLowerCase())}.` : "",
    inside ? `At ${hhmm(inside.iso.carried_in_at)} it was carried into the ${place} without a scan-in, and no camera saw it come out.` : "",
    found ? `Floor staff found it there at ${hhmm(found.at)}.` : inside ? "A floor search has been sent to confirm it." : "",
  ].filter(Boolean);
  const sure = inside
    ? found ? "Confirmed on the floor." : "Likely, not confirmed. A camera saw it carried in; none sees inside, so the floor search decides."
    : "Unconfirmed: the cameras lose the parcel after its last scan.";

  // the map: the steps that have a place, numbered like the cards; a leg is solid when both ends were on camera
  const stops: FPStop[] = steps.flatMap((c) => c.xy ? [{ n: steps.indexOf(c) + 1, xy: c.xy as XY, tone: c.tone === "scan" ? "scan" as const : c.tone === "noscan" || c.tone === "record" ? "bad" as const : "seen" as const, label: c.title }] : []);
  const legs: FPLeg[] = stops.slice(1).map((s, i) => {
    const a = steps[Number(stops[i].n) - 1], b = steps[Number(s.n) - 1];
    const between = steps.slice(Number(stops[i].n), Number(s.n) - 1);
    return { from: stops[i].xy, to: s.xy, seen: !!a.camera && !!b.camera && !between.some((c) => c.tone === "wait") && b.tone !== "wait" };
  });
  const cams: FPCam[] = [...new Set(steps.map((c) => c.camera).filter((c) => /^(CAM|CHK)_/.test(c)))].flatMap((id) => {
    const h = (HUB.cameras as unknown as { id: string; position_m: number[]; heading_deg: number }[]).find((x) => x.id === id);
    return h ? [{ id, xy: [h.position_m[0], h.position_m[1]] as XY, heading_deg: h.heading_deg }] : [];
  });
  const zoneId = (found?.name ?? inside?.place ?? "").match(/Z\d+/)?.[0];

  // records against the cameras: every scan, the missing scan-in, the disagreeing truck record
  const rows = steps.filter((c) => c.tone === "scan" || c.tone === "noscan" || c.tone === "record").map((c) => ({
    n: steps.indexOf(c) + 1, t: c.t,
    record: c.tone === "scan" ? `Scan: ${c.title.toLowerCase()}` : c.tone === "noscan" ? "No scan-in at the store's post" : c.title,
    camera: c.tone === "scan" ? `${camWords(c.camera)}${c.label ? ", number confirmed" : ", seen"}`
      : c.tone === "record" && inside ? `Carried into the ${place} at ${hhmm(inside.iso.carried_in_at)}, never seen coming out` : c.sub || camWords(c.camera),
    verdict: c.tone === "scan" ? "Agree" : c.tone === "noscan" ? "Not scanned in" : "Records disagree", tone: c.tone, label: !!c.label,
  }));
  // Rexton 3 Nov (too long): the scans that agree are one row; only the disagreements get a row each
  const agree = rows.filter((r) => r.tone === "scan"), clash = rows.filter((r) => r.tone !== "scan");

  async function exportPdf() {
    setBusy("pdf"); setNote(null);
    try {
      const r = await api<{ report_id: string }>(`/v1/cases/${caseId}/export`, { method: "POST" });
      void r; window.print();
    } catch (e) { setNote(e instanceof Error ? e.message : String(e)); } finally { setBusy(null); }
  }
  const jump = (at?: string) => {
    if (!at) return;
    const i = steps.reduce((best, c, k) => Math.abs(Date.parse(c.t) - Date.parse(at)) < Math.abs(Date.parse(steps[best].t) - Date.parse(at)) ? k : best, 0);
    document.getElementById(`rp-step-${i + 1}`)?.scrollIntoView({ behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth", block: "center" });
    setFlash(i + 1); window.setTimeout(() => setFlash(null), 1600);
  };

  return (
    <div className="rp" data-sheet={sheet ? "" : undefined}>
      <CaseSteps caseId={caseId} waybill={waybill} page="Report" here={3} />
      <div className="rp-body">
        <article className="rp-paper" aria-label="Case report">
          <header className="rp-head">
            <div className="rp-head-top">
              <span className="rp-brand">
                {/* eslint-disable-next-line @next/next/no-img-element -- the brand's own logo file (light, for paper) */}
                <img src="/brand/spoor-logo-light.png" alt="Spoor" width={78} height={25} /><span>Case report</span>
              </span>
              <div className="rp-acts">
                <button type="button" className="rp-btn" onClick={exportPdf} disabled={!!busy}>{busy === "pdf" ? "Preparing" : "Export PDF"}</button>
                <button type="button" className="rp-btn rp-btn-primary" onClick={() => setSheet(true)}>
                  {sent ? "Customer update sent" : saved.data?.draft ? "Update to the customer" : "Draft the update to the customer"}
                </button>
              </div>
            </div>
            <span className="rp-status" data-tone={found ? "ok" : inside ? "open" : "bad"} hidden={!loaded}>{found ? "Found" : inside ? "Open · likely location" : "Open · lost track"}</span>
            {loaded ? <h1 className="rp-h1">{head}</h1> : <span className="rp-skel rp-skel-h" aria-busy="true" />}
            <dl className="rp-meta">
              <div><dt>Parcel</dt><dd className="rp-mono">{waybill}</dd></div>
              <div><dt>Case</dt><dd className="rp-mono">{caseId.replace(/^case_/, "").slice(0, 10)}</dd></div>
              <div><dt>Customer waiting</dt><dd>{wait ? `${wait} before asking` : "Not a customer case"}</dd></div>
              <div><dt>{found ? "Closed by" : "Opened"}</dt><dd>{found ? `${found.by} · ${hhmm(found.at)}, ${day(found.at)}` : st.data ? `${hhmm(st.data.case.created_at)}, ${day(st.data.case.created_at)}` : ""}</dd></div>
            </dl>
            {sent && <p className="rp-sent">Update to the customer approved by {sent.approved_by} and sent to customer service at {sent.sent_at ? hhmm(sent.sent_at) : ""}.</p>}
            {note && <p className="rp-note" role="status">{note}</p>}
          </header>

          <section className="rp-sec" aria-labelledby="rp-1">
            <h2 id="rp-1" className="rp-h2"><span>1</span>Summary</h2>
            {loaded ? <p className="rp-summary">{summary.join(" ")}</p> : <span className="rp-skel" style={{ height: 72 }} aria-busy="true" />}
            <p className="rp-sure"><b>How sure.</b> {sure}</p>
          </section>

          <section className="rp-sec" aria-labelledby="rp-2">
            <h2 id="rp-2" className="rp-h2"><span>2</span>Journey on camera</h2>
            {rr.data && (
              <video className="rp-video" src={signedUrl(rr.data.url)} controls preload="metadata" playsInline muted
                poster={steps[0]?.thumb_url ? signedUrl(steps[0].thumb_url) : undefined} aria-label="The parcel's journey, every step on camera" />
            )}
            <ol className="rp-steps">
              {steps.map((c, i) => (
                <li key={`${c.t}-${i}`} id={`rp-step-${i + 1}`} className="rp-step" data-tone={c.tone} data-flash={flash === i + 1 ? "" : undefined}>
                  <figure className="rp-frame">
                    {/* eslint-disable-next-line @next/next/no-img-element -- a signed frame of the step, cut from the reel by the API */}
                    {c.thumb_url ? <img src={signedUrl(c.thumb_url)} alt={`${c.title}, ${camWords(c.camera || "")}`} loading="lazy" /> : <span className="rp-frame-none" />}
                    <span className="rp-frame-n">{i + 1}</span>
                    {c.label && <span className="rp-frame-id">{c.camera === "Tunnel reader" ? "Number read" : "Number confirmed"}</span>}
                  </figure>
                  <div className="rp-step-txt">
                    <span className="rp-step-top"><span className="rp-time">{hms(c.t)}</span><span className="rp-chip" data-tone={c.tone}>{c.last_scan ? "Last scan" : CHIP[c.tone]}</span></span>
                    <b>{c.title}</b>
                    {c.sub && <span className="rp-step-sub">{c.sub}</span>}
                    <span className="rp-step-cam">{c.camera ? camWords(c.camera) : "No camera"}</span>
                  </div>
                </li>
              ))}
            </ol>
          </section>

          <section className="rp-sec rp-break" aria-labelledby="rp-3">
            <h2 id="rp-3" className="rp-h2"><span>3</span>Where it went</h2>
            <FloorPlan label="Floor plan: the parcel's route, numbered like the steps above" stops={stops} legs={legs} cameras={cams} highlight={zoneId}
              labels="major" legend onStop={(n) => { const el = document.getElementById(`rp-step-${n}`); el?.scrollIntoView({ behavior: "smooth", block: "center" }); setFlash(Number(n)); window.setTimeout(() => setFlash(null), 1600); }} />
          </section>

          <section className="rp-sec" aria-labelledby="rp-4">
            <h2 id="rp-4" className="rp-h2"><span>4</span>Records against the cameras</h2>
            <table className="rp-table">
              <thead><tr><th>Step</th><th>Time</th><th>The record says</th><th>The cameras show</th><th>Verdict</th></tr></thead>
              <tbody>
                {agree.length > 1 && (
                  <tr data-tone="scan">
                    <td className="rp-mono">{agree[0].n}–{agree.at(-1)!.n}</td><td className="rp-mono">{hhmm(agree[0].t)}–{hhmm(agree.at(-1)!.t)}</td>
                    <td>{agree.length} scans, unloaded to {(steps.find((c) => c.last_scan)?.title ?? "the last scan").replace(/^\w/, (x) => x.toLowerCase())}</td>
                    <td>Each one on camera · {agree.filter((r) => r.label).length} numbers confirmed</td>
                    <td><span className="rp-chip" data-tone="scan">Agree</span></td>
                  </tr>
                )}
                {(agree.length > 1 ? clash : rows).map((r) => (
                  <tr key={r.n} data-tone={r.tone}>
                    <td className="rp-mono">{r.n}</td><td className="rp-mono">{hms(r.t)}</td><td>{r.record}</td><td>{r.camera}</td>
                    <td><span className="rp-chip" data-tone={r.tone}>{r.verdict}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
            {conflict && <p className="rp-fix"><b>To fix.</b> The dock door&apos;s RFID read marks every parcel in a cage as loaded, even one taken out of it.</p>}
          </section>

          <section className="rp-sec" aria-labelledby="rp-5">
            <h2 id="rp-5" className="rp-h2"><span>5</span>Floor check</h2>
            {task && !task.outcomes.length && !found ? (
              <p className="rp-p">Not started. {task.places.filter((p, i, all) => all.findIndex((q) => floorName(q.name) === floorName(p.name)) === i).length} places to check, in order: {task.places.filter((p, i, all) => all.findIndex((q) => floorName(q.name) === floorName(p.name)) === i).map((p) => floorName(p.name).replace(/ \/ non-conveyable area$/i, "")).join(", ")}.</p>
            ) : task ? (
              <ul className="rp-floor">
                {task.places.filter((p, i, all) => all.findIndex((q) => floorName(q.name) === floorName(p.name)) === i).slice(0, 6).map((p) => {
                  const same = task.places.filter((q) => floorName(q.name) === floorName(p.name)).map((q) => q.area_id);
                  const o = task.outcomes.find((x) => same.includes(x.area_id));
                  return (
                    <li key={p.area_id} data-out={o?.outcome ?? "waiting"}>
                      <span className="rp-floor-place">{floorName(p.name)}</span>
                      <span className="rp-chip" data-tone={o?.outcome === "found" ? "scan" : o ? "seen" : "wait"}>{o?.outcome === "found" ? "Found" : o ? "Not here" : "Not checked yet"}</span>
                      <span className="rp-floor-who">{o ? `${o.recorded_by ?? "Floor staff"}${o.recorded_at ? ` · ${hhmm(o.recorded_at)}` : ""}` : ""}</span>
                      {o?.note && <q>{o.note}</q>}
                    </li>
                  );
                })}
              </ul>
            ) : <p className="rp-p">No floor search yet. <Link href={`/cases/${caseId}/search`}>Send someone to look</Link>.</p>}
          </section>

          <section className="rp-sec rp-break" aria-labelledby="rp-6">
            <h2 id="rp-6" className="rp-h2"><span>6</span>Evidence</h2>
            <table className="rp-table rp-ev">
              <thead><tr><th>Step</th><th>Source</th><th>Frames</th><th>SHA-256</th></tr></thead>
              <tbody>
                {(rr.data?.sources ?? []).map((s, i) => (
                  <tr key={i}>
                    <td className="rp-mono">{i + 1}</td>
                    <td>{s.kind === "clip" ? camWords(s.camera ?? "") : s.kind === "still" ? "Tunnel reader's photo" : s.title}</td>
                    <td className="rp-mono">{s.frames ? `${s.frames[0]}–${s.frames[1]}` : "1 photo"}</td>
                    <td>{s.sha256 ? <Hash h={s.sha256} /> : <span className="rp-mute">{s.path}</span>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <dl className="rp-models">
              {(run.data?.crew ?? []).filter((c, i, all) => all.findIndex((x) => x.model === c.model) === i).map((c) => (
                <div key={c.model}><dt>{c.model}</dt><dd>{c.who}</dd></div>
              ))}
              {end && <div><dt>Run</dt><dd>{end.text}</dd></div>}
            </dl>
            <ul className="rp-limits">
              <li>No camera sees inside the {place ?? "store"}; the floor search confirms where.</li>
              <li>A step has no number when its outline could not be told from a person or the next carton. The agents&apos; ideas guide the search; they are never evidence.</li>
            </ul>
          </section>
          <footer className="rp-fine">Decision support for the hub, not a forensic certificate. Every parcel leaves a trail.</footer>
        </article>
      </div>
      <CustomerSheet caseId={caseId} open={sheet} onClose={() => setSheet(false)} saved={saved.data ?? null} onFact={jump} />
    </div>
  );
}

function Hash({ h }: { h: string }) {
  const [ok, setOk] = useState(false);
  return (
    <button type="button" className="rp-hash" title={h} onClick={() => { void navigator.clipboard?.writeText(h).then(() => { setOk(true); window.setTimeout(() => setOk(false), 1400); }); }}>
      <span className="rp-mono">{h.slice(0, 12)}…</span><span className="rp-hash-copy">{ok ? "Copied" : "Copy"}</span>
    </button>
  );
}

/** The update to the customer who asked: a side sheet beside the report (the report stays readable), drafted from verified
 *  facts only; each fact links to its frame; a person approves it. */
function CustomerSheet({ caseId, open, onClose, saved, onFact }: { caseId: string; open: boolean; onClose: () => void; saved: Draft | null;
  onFact: (at?: string) => void }) {
  // the person's choices; until they choose, the saved draft's (it may load after the sheet first renders)
  const [pick, setPick] = useState<{ channel?: string; language?: string; tone?: string }>({});
  const [d, setD] = useState<Draft | null>(null);
  const [edit, setText] = useState<string | null>(null); // the person's edit; until then the draft as written
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const cur = d ?? saved;
  const text = edit ?? cur?.draft ?? "";
  const channel = pick.channel ?? cur?.channel ?? "chat", language = pick.language ?? cur?.language ?? "en", tone = pick.tone ?? cur?.tone ?? "short";
  const setChannel = (v: string) => setPick((x) => ({ ...x, channel: v }));
  const setLanguage = (v: string) => setPick((x) => ({ ...x, language: v }));
  const setTone = (v: string) => setPick((x) => ({ ...x, tone: v }));
  async function make(next?: Partial<{ channel: string; language: string; tone: string }>) {
    const o = { channel, language, tone, ...next };
    setBusy("draft"); setErr(null);
    try {
      const r = await api<Draft>(`/v1/cases/${caseId}/customer-update`, { method: "POST", json: o });
      setD(r); setText(null);
    } catch (e) { setErr(e instanceof Error ? e.message : String(e)); } finally { setBusy(null); }
  }
  async function send() {
    setBusy("send"); setErr(null);
    try {
      const r = await api<Draft>(`/v1/cases/${caseId}/customer-update/approve`, { method: "POST", json: { text } });
      setD(r); invalidate(`/v1/cases/${caseId}/customer-update`);
    } catch (e) { setErr(e instanceof Error ? e.message : String(e)); } finally { setBusy(null); }
  }
  const seg = (v: string, set: (x: string) => void, key: "channel" | "language" | "tone", opts: [string, string][]) => (
    <div className="cs-seg" role="radiogroup">
      {opts.map(([k, label]) => (
        <button key={k} type="button" role="radio" aria-checked={v === k} disabled={!!busy || cur?.sent}
          onClick={() => { if (v !== k) { set(k); void make({ [key]: k }); } }}>{label}</button>
      ))}
    </div>
  );
  return (
    <aside className="cs" data-open={open ? "" : undefined} aria-hidden={!open} inert={!open} aria-label="Update to the customer">
      <header className="cs-head">
        <div><h2>Update to the customer</h2><p>{cur?.stage === "found" ? "Found on the floor: the found update." : "Not found on the floor yet: a holding update."}</p></div>
        <button type="button" className="cs-x" onClick={onClose} aria-label="Close"><svg viewBox="0 0 20 20" aria-hidden><path d="M5 5l10 10M15 5L5 15" /></svg></button>
      </header>
      <div className="cs-body">
        <div className="cs-controls">
          <label>Channel{seg(channel, setChannel, "channel", [["chat", "Marketplace chat"], ["email", "Email"]])}</label>
          <label>Language{seg(language, setLanguage, "language", [["en", "English"], ["ms", "Malay"]])}</label>
          <label>Length{seg(tone, setTone, "tone", [["short", "Short"], ["detailed", "Detailed"]])}</label>
        </div>
        <div className="cs-draft" data-busy={busy === "draft" ? "" : undefined}>
          {!cur && !busy ? (
            <div className="cs-start">
              <p>Pick how customer service will send it, then Spark writes it from the verified facts below.</p>
              <button type="button" className="rp-btn rp-btn-primary" onClick={() => make()}>Write the draft</button>
            </div>
          ) : busy === "draft" && !text ? <span className="cs-skel" aria-busy="true"><i /><i /><i /></span> : (
            <textarea value={text} onChange={(e) => setText(e.target.value)} rows={channel === "email" ? 11 : 7} readOnly={!!cur?.sent}
              aria-label="The update, edit before approving" />
          )}
          <span className="cs-by">{cur ? (cur.model === "template" ? "Plain template" : `Worded by ${modelName(cur.model)}`) : ""}{busy === "draft" ? " · rewording…" : ""}</span>
        </div>
        {cur?.facts && (
          <div className="cs-facts">
            <span className="cs-k">Every sentence comes from these verified facts</span>
            <ul>
              {cur.facts.slice(1).map((f, i) => {
                const ref = cur.refs?.[i + 1];
                return (
                  <li key={f}>
                    <span>{f}</span>
                    {ref && (ref.at ? <button type="button" className="cs-ref" onClick={() => onFact(ref.at)}>{ref.label} <span aria-hidden>→</span></button>
                      : <span className="cs-ref cs-ref-plain">{ref.label}</span>)}
                  </li>
                );
              })}
            </ul>
          </div>
        )}
        {err && <p className="cs-err" role="alert">{err}</p>}
      </div>
      <footer className="cs-foot">
        {cur?.sent ? (
          <p className="cs-sent"><svg viewBox="0 0 16 16" aria-hidden><path d="m3.5 8.5 3 3 6-6.5" /></svg>Approved by {cur.approved_by} and sent to customer service at {cur.sent_at ? hhmm(cur.sent_at) : ""}. Kept on the case with its hash.</p>
        ) : (
          <>
            <button type="button" className="rp-btn" onClick={() => { void navigator.clipboard?.writeText(text).then(() => { setCopied(true); window.setTimeout(() => setCopied(false), 1400); }); }}>{copied ? "Copied" : "Copy text"}</button>
            <button type="button" className="rp-btn rp-btn-primary" disabled={!text.trim() || !!busy} onClick={send}>{busy === "send" ? "Sending" : "Approve and send"}</button>
          </>
        )}
      </footer>
      <p className="cs-fine">A person approves every update. It goes to customer service, who answer the customer; Spoor never writes to customers itself.</p>
    </aside>
  );
}

