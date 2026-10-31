"use client";
/**
 * Hub, ported from review/refs/flow/Main.dc.html (owner 09:22: follow the prototype 100 %). Same layout, sizes and
 * copy; the rows come from real data: open cases (a customer asked) and stalled parcels (the scan log shows a late next
 * scan while the next scanner kept working). The first row is the large card; the rest are compact.
 */
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api, ApiError, invalidate, signedUrl, useResource } from "@/lib/api";
import type { Journey } from "@/lib/journey";
import { hhmm, lastScanSentence, minutes, missingNextSentence } from "@/lib/words";
import { camId, scanPoint, zoneId } from "@/lib/hub";
import type { Capabilities, MediaRow, Site } from "@/lib/types";
import { ErrorState } from "@/components/ui";
import HubPlan, { ZONE_NAMES } from "@/components/plan/HubPlan";
import "./hub.css";

interface Inbox {
  as_of: string | null;
  stalled: { waybill: string; last_event_kind: string; read_point: string; last_at: string; age_s: number; expected_next: string;
    case_id: string | null }[];
}
interface Dashboard {
  kpis: { open_cases: number; found: number; median_hours_to_locate: number | null };
  trail_ends_by_zone: { zone_id: string; zone: string; cases: number }[];
  cases: { case_id: string; target: string; status: string }[];
}
type Tone = "bad" | "warn" | "ok";
const CASE_PILL: Record<string, [string, Tone]> = { found: ["Found", "ok"], located: ["Likely location", "ok"], unknown: ["Lost track", "bad"] };
const STAGES = ["Tunnel", "Sorter", "Chute", "Cage", "Truck"];

function stageOf(kind: string | undefined): number {
  switch (kind) {
    case "inducted": case "induct_to_carrier": case "recirculated": return 1;
    case "divert_confirmed": case "divert_confirm": case "exception_diverted": return 2;
    case "bagged": case "bag_scan": case "container_add": case "container_closed": return 3;
    case "container_loaded": case "departed_facility": return 4;
    default: return 0;
  }
}

const siteLine = (name: string | undefined) => (name ?? "Hub").replace(/\s*\(fictional\)/i, "").replace(/^CONTOH Express /, "CONTOH Express · ");
const clockS = (iso: string) => new Date(iso).toLocaleTimeString("en-GB", { timeZone: "Asia/Kuala_Lumpur", hour12: false });

export default function HubPage() {
  const sites = useResource<Site[]>("/v1/sites");
  const site = sites.data?.[0];
  const inbox = useResource<Inbox>(site ? `/v1/sites/${site.site_id}/exceptions?limit=50` : null);
  const dash = useResource<Dashboard>(site ? `/v1/sites/${site.site_id}/dashboard` : null);
  const caps = useResource<Capabilities>("/v1/capabilities");
  const keyed = !!(caps.data?.sam || caps.data?.spark);
  const [show, setShow] = useState<string>("All");
  const open = (dash.data?.cases ?? []).filter((c) => c.status !== "found");
  const inCase = new Set(open.map((c) => c.target.split(" ").at(-1)));
  const stalled = (inbox.data?.stalled ?? []).filter((s) => !inCase.has(s.waybill));
  const items = [
    ...open.map((c) => {
      const [pill, tone] = CASE_PILL[c.status] ?? CASE_PILL.unknown;
      return { kind: "case" as const, key: c.case_id, pill, tone, c };
    }),
    ...stalled.map((s) => ({ kind: "stalled" as const, key: s.waybill, pill: "Stalled", tone: "warn" as Tone, s })),
  ];
  const groups = [...new Set(items.map((i) => i.pill))];
  const shown = items.filter((i) => show === "All" || i.pill === show);
  const ready = !!inbox.data && !!dash.data;
  const err = sites.error ?? inbox.error ?? dash.error;
  const k = dash.data?.kpis;
  const tiles = k ? [{ n: String(k.found), u: "", l: "found today" },
    k.median_hours_to_locate !== null ? { n: String(Math.round(k.median_hours_to_locate * 60)), u: " min", l: "median time to find" }
      : { n: String(k.open_cases), u: "", l: k.open_cases === 1 ? "open case" : "open cases" }] : [];

  return (
    <div className="hb">
      <section className="hb-main">
        <div className="hb-head">
          <div>
            <p className="hb-site">{siteLine(site?.name)}{inbox.data?.as_of ? ` · updated ${hhmm(inbox.data.as_of)}` : ""}</p>
            <h1 className="hb-title" data-testid="hub-title">
              {!ready ? "Checking the hub" : items.length === 0 ? "Every parcel is on track" : `${items.length} parcel${items.length === 1 ? "" : "s"} need${items.length === 1 ? "s" : ""} attention`}
            </h1>
          </div>
          {groups.length > 1 && (
            <div role="group" aria-label="Filter" className="hb-filter">
              {["All", ...groups].map((g) => (
                <button key={g} type="button" aria-pressed={show === g} onClick={() => setShow(g)}>
                  {g} {g === "All" ? items.length : items.filter((i) => i.pill === g).length}
                </button>
              ))}
            </div>
          )}
        </div>

        {err && <ErrorState error={err} what="the hub" onRetry={() => { inbox.reload(); dash.reload(); }} />}
        {ready && site && shown.map((it, i) => it.kind === "case"
          ? <CaseCard key={it.key} siteId={site.site_id} c={it.c} pill={it.pill} tone={it.tone} big={i === 0} keyed={keyed} />
          : <StalledCard key={it.key} siteId={site.site_id} s={it.s} big={i === 0} keyed={keyed} />)}
        {ready && items.length === 0 && <p className="hb-empty">No open cases and no late scans right now.</p>}

        <p className="hb-note">A parcel shows here when its next scan is late and the next scanner kept working. You hear about it before the customer calls.</p>
      </section>

      <aside className="hb-side">
        {tiles.length > 0 && (
          <div className="hb-tiles">
            {tiles.map((t) => (
              <div key={t.l} className="hb-tile"><p className="hb-tile-n">{t.n}{t.u && <span>{t.u}</span>}</p><p className="hb-tile-l">{t.l}</p></div>
            ))}
          </div>
        )}
        {dash.data && (
          <div className="hb-trails">
            <div className="hb-trails-head">
              <h2>Where today&apos;s trails ended</h2>
              <Link href="/wall">Open 3D hub</Link>
            </div>
            <TrailsPlan dash={dash.data} caseId={open[0]?.case_id} />
          </div>
        )}
        <p className="hb-tag">Every parcel leaves a trail.</p>
      </aside>
    </div>
  );
}

/** Where today's trails ended: the building, the zones where cases end, and the top case's route (as the prototype). */
function TrailsPlan({ dash, caseId }: { dash: Dashboard; caseId?: string }) {
  const j = useResource<Journey>(caseId ? `/v1/cases/${caseId}/journey` : null);
  return (
    <HubPlan label={`Floor plan of the hub: where today's cases end. ${dash.trail_ends_by_zone.map((z) => `${ZONE_NAMES[zoneId.toHub(z.zone_id)] ?? z.zone} ${z.cases}`).join(", ") || "none yet"}`}
      heat={Object.fromEntries(dash.trail_ends_by_zone.map((z) => [zoneId.toHub(z.zone_id), z.cases]))} journey={j.data?.objects[0]} fit="width" legend={false} quiet />
  );
}

/** Thumbnail: a camera's frame of the last scan point at that time, else the plan pinned where it stopped. */
function Thumb({ siteId, point, at, tone, big }: { siteId: string; point: string | null | undefined; at: string | undefined; tone: Tone; big: boolean }) {
  const media = useResource<MediaRow[]>(`/v1/sites/${siteId}/media`);
  const sp = scanPoint(point);
  const [frame, setFrame] = useState<{ url: string; cam: string } | null>(null);
  const hit = at && sp ? (media.data ?? []).find((m) => m.media.camera_id && sp.visible_by.includes(camId.toHub(m.media.camera_id))
    && m.coverage.some((c) => c.start_utc <= at && at <= c.end_utc)) : undefined;
  const mediaId = hit?.media.media_id;
  const camHub = hit?.media.camera_id ? camId.toHub(hit.media.camera_id) : null;
  useEffect(() => {
    if (!mediaId || !at || !camHub) return;
    let live = true;
    api<{ frame_url: string }>(`/v1/media/${mediaId}/frame-at?time=${encodeURIComponent(at)}`)
      .then((r) => live && setFrame({ url: r.frame_url, cam: camHub })).catch(() => {});
    return () => { live = false; };
  }, [mediaId, at, camHub]);
  const tag = frame && at ? `${frame.cam.replace("_", " ")} · ${big ? clockS(at) : hhmm(at)}` : `Where it stopped${at ? ` · ${hhmm(at)}` : ""}`;
  return (
    <span className={big ? "hb-thumb hb-thumb-big" : "hb-thumb"}>
      {frame ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={signedUrl(frame.url)} alt={`Last camera sighting: ${frame.cam.replace("_", " ")}`} />
      ) : sp ? (
        <HubPlan label={`Where it stopped: ${sp.id}`} focus={{ xy: [sp.position_m[0], sp.position_m[1]], radius_m: 8, tone: tone === "bad" ? "bad" : "warn" }}
          legend={false} fit="contain" minHeight={0} />
      ) : null}
      <span className="hb-thumb-tag">{tag}</span>
    </span>
  );
}

function Trail({ stage }: { stage: number }) {
  const shown = STAGES.slice(0, Math.min(stage + 2, STAGES.length));
  return (
    <div className="hb-trail" aria-label="How far it got">
      {shown.map((s, i) => (
        <span key={s} className="hb-trail-step">
          {i > 0 && <span className="hb-trail-line" />}
          <span className={i <= stage ? "hb-trail-dot" : "hb-trail-next"} />
        </span>
      ))}
      <span className="hb-trail-words">{shown.map((s, i) => (i > stage ? `${s}?` : s)).join(" · ")}</span>
    </div>
  );
}

function Act({ big, href, label, keyed, onClick, busy }: { big: boolean; href?: string; label: string; keyed: boolean; onClick?: () => void; busy?: boolean }) {
  const cls = big ? "hb-btn hb-btn-primary" : "hb-btn";
  const btn = href ? <Link className={cls} href={href}>{label}</Link>
    : <button type="button" className={cls} onClick={onClick} disabled={busy}>{busy ? "Opening" : label}</button>;
  if (!big) return btn;
  return <div className="hb-act">{btn}<span>{keyed ? "about 1 min · ~US$0.30" : "Shows what the scan log knows"}</span></div>;
}

function CaseCard({ siteId, c, pill, tone, big, keyed }: { siteId: string; c: Dashboard["cases"][number]; pill: string; tone: Tone; big: boolean; keyed: boolean }) {
  const j = useResource<Journey>(`/v1/cases/${c.case_id}/journey`);
  const cs = useResource<{ case: { complaint?: string | null; created_at: string } }>(`/v1/cases/${c.case_id}/state`);
  const run = useResource<{ steps: unknown[] }>(`/v1/cases/${c.case_id}/run`);
  const scans = j.data?.objects[0]?.scans ?? [];
  const last = scans.at(-1);
  const waybill = c.target.split(" ").at(-1) ?? c.target;
  const dims = scans.find((s) => s.dims_mm)?.dims_mm;
  const head = last ? `${lastScanSentence(last.event_kind, last.station_id, last.t)} ${missingNextSentence(last.event_kind)}` : "No scans of this parcel at this hub.";
  const investigated = (run.data?.steps.length ?? 0) > 0;
  const action = investigated ? { href: `/cases/${c.case_id}`, label: "Open case" } : { href: `/cases/${c.case_id}/investigate`, label: "Investigate" };
  const context = cs.data?.case.complaint ? `Customer says it never arrived · case opened ${ago(cs.data.case.created_at)}` : null;
  const foot = `${waybill}${dims ? ` · ${dims.map((d) => Math.round(d / 10)).join(" × ")} cm` : ""}`;
  return (
    <article className={big ? "hb-card hb-card-big" : "hb-card"} data-tone={tone}>
      <Thumb siteId={siteId} point={last?.station_id ?? last?.device_id} at={last?.t} tone={tone} big={big} />
      <div className="hb-body">
        <div className="hb-pills"><span className="hb-pill" data-tone={tone}>{pill}</span>{context && big && <span className="hb-context">{context}</span>}</div>
        {big ? <h2 className="hb-h">{head}</h2> : <span className="hb-h-sm">{head}</span>}
        {big && <Trail stage={stageOf(last?.event_kind)} />}
        <p className="hb-foot">{foot}</p>
      </div>
      <Act big={big} href={action.href} label={action.label} keyed={keyed} />
    </article>
  );
}

function StalledCard({ siteId, s, big, keyed }: { siteId: string; s: Inbox["stalled"][number]; big: boolean; keyed: boolean }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const head = `${lastScanSentence(s.last_event_kind, s.read_point, s.last_at)} ${missingNextSentence(s.last_event_kind)}`;
  async function investigate() {
    if (s.case_id) return router.push(`/cases/${s.case_id}/investigate`);
    setBusy(true);
    setErr(null);
    try {
      const r = await api<{ case: { case_id: string } }>("/v1/cases", { method: "POST", json: {
        site_id: siteId, question: `Where did parcel ${s.waybill} go after its last scan?`, target_description: `parcel ${s.waybill}`,
        identifiers: [{ scheme: "carrier_waybill", value: s.waybill }] } });
      invalidate("/v1/cases");
      invalidate("/v1/sites/");
      router.push(`/cases/${r.case.case_id}/investigate`);
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : String(e));
      setBusy(false);
    }
  }
  return (
    <article className={big ? "hb-card hb-card-big" : "hb-card"} data-tone="warn">
      <Thumb siteId={siteId} point={s.read_point} at={s.last_at} tone="warn" big={big} />
      <div className="hb-body">
        <span className="hb-pill" data-tone="warn">Stalled {minutes(s.age_s)}</span>
        {big ? <h2 className="hb-h">{head}</h2> : <span className="hb-h-sm">{head}</span>}
        {big && <Trail stage={stageOf(s.last_event_kind)} />}
        <p className="hb-foot">{s.waybill} · next: {s.expected_next}</p>
        {err && <p className="hb-err" role="alert">{err}</p>}
      </div>
      <Act big={big} label="Investigate" keyed={keyed} onClick={investigate} busy={busy} />
    </article>
  );
}

function ago(iso: string): string {
  const d = Math.floor((Date.now() - new Date(iso).getTime()) / 86400000);
  return d <= 0 ? "today" : d === 1 ? "yesterday" : `${d} days ago`;
}
