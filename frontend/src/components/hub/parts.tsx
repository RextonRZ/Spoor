"use client";
/**
 * The Hub's building blocks, shared with the Cases page so the two are one design (owner 31 Oct: "hub and cases not the
 * same"): the sliding-underline tabs, the case table, the camera view of a place, the case detail (what happened, actions,
 * the six scan checkpoints, where to look next), the slide-in panel for narrower screens, and the skeleton rows.
 * Styles: app/hub/hub.css (prefix hb-).
 */
import Link from "next/link";
import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { api, previewUrl, useResource } from "@/lib/api";
import type { Journey, MissingMoment } from "@/lib/journey";
import { hhmm, hms, lastScanSentence, minutes, missingNextSentence, momentLabel, placeOf } from "@/lib/words";
import { low, type LastScan } from "@/lib/answer";
import { camId, scanPoint } from "@/lib/hub";
import { buildCheckpoints, type CaseRecord } from "@/lib/checkpoints";
import type { MediaRow } from "@/lib/types";
import { CheckpointStrip } from "@/components/checkpoints/Checkpoints";
import HubPlan from "@/components/plan/HubPlan";
import "@/app/hub/hub.css";

export interface Dashboard {
  kpis: { open_cases: number; found: number; median_hours_to_locate: number | null };
  trail_ends_by_zone: { zone_id: string; zone: string; cases: number }[];
  cases: { case_id: string; target: string; status: string; customer_asked?: boolean }[];
}
export type Tone = "bad" | "warn" | "ok";
// a floor find, else the latest verified run's answer (dashboard.py): never "Lost track" once a run placed it
export const CASE_PILL: Record<string, [string, Tone]> = { found: ["Found", "ok"], located: ["Likely location found", "ok"],
  confirmed: ["Confirmed on camera", "ok"], by_scan: ["Located by scan", "warn"], unknown: ["Lost track", "bad"] };
export interface CaseItem { kind: "case"; key: string; c: Dashboard["cases"][number]; pill: string; tone: Tone }

export const placeWords = (kind: string | undefined, point: string | null | undefined) => (kind ? placeOf(kind, point).replace(/^the /, "") : undefined);

// wide screens dock the detail beside the tables (a split view); narrower ones slide it in over them
export const WIDE = "(min-width: 1200px)";
export const onWideChange = (cb: () => void) => {
  const m = window.matchMedia(WIDE);
  m.addEventListener("change", cb);
  return () => m.removeEventListener("change", cb);
};


/** Underline tabs; the underline slides to the chosen tab (transform only; the first placement doesn't slide). */
export function Tabs<T extends string>({ tabs, tab, onTab }: { tabs: { id: T; label: string; n: number }[]; tab: T; onTab: (t: T) => void }) {
  const box = useRef<HTMLDivElement>(null);
  const [bar, setBar] = useState<{ x: number; w: number } | null>(null);
  const [moving, setMoving] = useState(false);
  const sig = tabs.map((t) => t.n).join();
  useLayoutEffect(() => {
    const el = box.current?.querySelector<HTMLElement>('[aria-selected="true"]');
    setBar(el ? { x: el.offsetLeft, w: el.offsetWidth } : null);
  }, [tab, sig]);
  useEffect(() => {
    if (!bar) return;
    const id = requestAnimationFrame(() => setMoving(true));
    return () => cancelAnimationFrame(id);
  }, [bar]);
  const onKey = (e: React.KeyboardEvent) => {
    if (e.key !== "ArrowRight" && e.key !== "ArrowLeft") return;
    const i = tabs.findIndex((t) => t.id === tab);
    const next = tabs[(i + (e.key === "ArrowRight" ? 1 : tabs.length - 1)) % tabs.length];
    onTab(next.id);
    box.current?.querySelector<HTMLElement>(`[data-tab="${next.id}"]`)?.focus();
  };
  return (
    <div className="hb-tabs" role="tablist" aria-label="Hub views" ref={box} onKeyDown={onKey}>
      {tabs.map((t) => (
        <button key={t.id} type="button" role="tab" data-tab={t.id} aria-selected={tab === t.id} tabIndex={tab === t.id ? 0 : -1} onClick={() => onTab(t.id)}>
          {t.label} <span className="hb-count">({t.n})</span>
        </button>
      ))}
      {bar && <span className="hb-tabline" data-moving={moving ? "" : undefined} style={{ transform: `translateX(${bar.x}px) scaleX(${bar.w})` }} aria-hidden="true" />}
    </div>
  );
}

export function Skeleton() {
  return (
    <div className="hb-table" aria-busy="true" aria-label="Loading">
      {[0, 1, 2, 3].map((i) => (
        <div key={i} className="hb-tr hb-tr-skel">
          <span className="hb-skel" style={{ width: 72 }} /><span className="hb-skel" style={{ width: 160 }} />
          <span className="hb-skel" style={{ width: 220 }} /><span className="hb-skel" style={{ width: 56 }} />
        </div>
      ))}
    </div>
  );
}

/** How long the customer has waited by the time they asked: from the parcel's last scan here to the case's opening. */
export function waited(lastScan: string, opened: string): string | null {
  const days = Math.floor((Date.parse(opened) - Date.parse(lastScan)) / 86_400_000);
  return days >= 1 ? `${days} day${days === 1 ? "" : "s"}` : null;
}

export function useCase(caseId: string) {
  const j = useResource<Journey>(`/v1/cases/${caseId}/journey`);
  const cs = useResource<{ case: { complaint?: string | null; created_at: string };
    answer?: { objects: { inside: { place: string; iso: Record<string, string> } | null; last_scan?: LastScan | null }[] } | null }>(`/v1/cases/${caseId}/state`);
  const cf = useResource<{ objects: { records?: CaseRecord[] }[] }>(`/v1/cases/${caseId}/conflicts`);
  const run = useResource<{ steps: unknown[] }>(`/v1/cases/${caseId}/run`);
  const scans = j.data?.objects[0]?.scans ?? [];
  return { j, cs, cf, run, scans, last: scans.at(-1) };
}

export function CasesTable({ rows, openKey, onOpen, asOf, empty }: { rows: CaseItem[]; openKey: string | null; onOpen: (k: string, el: HTMLElement) => void; asOf: string | null; empty: string }) {
  if (!rows.length) return <p className="hb-empty">{empty}</p>;
  return (
    <div className="hb-table" aria-label="Cases">
      <div className="hb-tr hb-th hb-cols-case">
        <span>Status</span><span>Parcel</span><span>Where it stopped</span>
        <span>Last scan</span><span className="hb-num">Since</span><span />
      </div>
      {rows.map((a) => <CaseRow key={a.key} a={a} open={openKey === a.key} onOpen={onOpen} asOf={asOf} />)}
    </div>
  );
}

function CaseRow({ a, open, onOpen, asOf }: { a: CaseItem; open: boolean; onOpen: (k: string, el: HTMLElement) => void; asOf: string | null }) {
  const { last, j, cs } = useCase(a.c.case_id);
  const inside = cs.data?.answer?.objects[0]?.inside;
  const waybill = a.c.target.split(" ").at(-1) ?? a.c.target;
  const since = last && asOf ? minutes(Math.max(0, (Date.parse(asOf) - Date.parse(last.t)) / 1000)) : "";
  const where = inside ? `In the ${inside.place.replace(/ \(Z\d+\)$/, "").toLowerCase()}`
    : last ? lastScanSentence(last.event_kind, last.station_id, last.t).replace(/ at \d\d:\d\d\.$/, "") : "No scans yet";
  return (
    <button type="button" className="hb-tr hb-cols-case" aria-pressed={open} onClick={(e) => onOpen(a.key, e.currentTarget)}>
      <span><span className="hb-chip" data-tone={a.tone}>{a.pill}</span></span>
      <span className="hb-parcel"><span className="hb-mono">{waybill}</span>
        {a.c.customer_asked && <span className="hb-wait">Customer waiting</span>}</span>
      <span className="hb-ellipsis">{last || !j.loading ? where : <span className="hb-skel" style={{ width: 150 }} />}</span>
      <span className="hb-dim">{last ? hhmm(last.t) : ""}</span>
      <span className="hb-num">{since}</span>
      <span className="hb-chev" aria-hidden="true">›</span>
    </button>
  );
}

/** The head of a case's detail: its status chip and its tracking number. */
export function CaseHead({ a, children }: { a: CaseItem; children?: React.ReactNode }) {
  return (
    <div className="hb-drawer-head">
      <span className="hb-chip" data-tone={a.tone}>{a.pill}</span><span className="hb-mono">{a.c.target.split(" ").at(-1)}</span>
      {children}
    </div>
  );
}

/** The slide-in detail (narrower screens): in from the right (drawer curve), Esc or x closes it, focus returns to the row. */
export function Drawer({ label, head, onClose, children }: { label: string; head: (close: React.ReactNode) => React.ReactNode; onClose: () => void; children: React.ReactNode }) {
  const closeBtn = useRef<HTMLButtonElement>(null);
  const [leaving, setLeaving] = useState(false);
  const done = () => {
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    setLeaving(true);
    window.setTimeout(onClose, reduced ? 0 : 200);
  };
  useEffect(() => {
    closeBtn.current?.focus();
    const esc = (e: KeyboardEvent) => e.key === "Escape" && done();
    window.addEventListener("keydown", esc);
    return () => window.removeEventListener("keydown", esc);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  const x = (
    <button ref={closeBtn} type="button" className="hb-x" aria-label="Close detail" onClick={done}>
      <svg viewBox="0 0 16 16" aria-hidden="true"><path d="M4 4l8 8M12 4l-8 8" /></svg>
    </button>
  );
  return (
    <aside className={`hb-drawer${leaving ? " is-leaving" : ""}`} role="dialog" aria-modal="false" aria-label={label}>
      {head(x)}
      <div className="hb-drawer-body">{children}</div>
    </aside>
  );
}

/** The place, as the hub's own cameras see it: the frame at that minute when there is footage; else the view of the
 *  camera that watches that scanner (a still of the place, labelled as not the moment); else the plan pinned there. */
export function View({ siteId, point, at, tone, place }: { siteId: string; point: string | null | undefined; at: string | undefined; tone: Tone; place?: string }) {
  const media = useResource<MediaRow[]>(`/v1/sites/${siteId}/media`);
  const sp = scanPoint(point);
  const [frame, setFrame] = useState<{ url: string; cam: string } | null>(null);
  const [viewOk, setViewOk] = useState(true);
  const hit = at && sp ? [...(media.data ?? [])].sort((x, y) => Number(!!y.media.camera_id?.includes("CHK_")) - Number(!!x.media.camera_id?.includes("CHK_")))
    .find((m) => m.media.camera_id && sp.visible_by.includes(camId.toHub(m.media.camera_id))
    && !m.purged && m.coverage.some((c) => Date.parse(c.start_utc) <= Date.parse(at) && Date.parse(at) <= Date.parse(c.end_utc))) : undefined;
  const mediaId = hit?.media.media_id;
  const camHub = hit?.media.camera_id ? camId.toHub(hit.media.camera_id) : null;
  useEffect(() => {
    if (!mediaId || !at || !camHub) return;
    let live = true;
    api<{ frame_url: string }>(`/v1/media/${mediaId}/frame-at?time=${encodeURIComponent(at)}`)
      .then((r) => live && setFrame({ url: r.frame_url, cam: camHub })).catch(() => {});
    return () => { live = false; };
  }, [mediaId, at, camHub]);
  const viewCam = sp?.visible_by[0];
  // still looking for the moment's frame (the clip list, then the frame): a skeleton, never "no footage" before we know
  const pending = !frame && (media.loading || (!!mediaId && !!at));
  return (
    <figure className="hb-view">
      <span className="hb-view-img">
        {pending ? <span className="hb-skel" style={{ position: "absolute", inset: 0, borderRadius: 10 }} aria-busy="true" /> : frame ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={previewUrl(frame.url, 800)} alt={`Camera sighting: ${frame.cam.replaceAll("_", " ")}`} />
        ) : viewCam && viewOk ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={`/landing/posters/${viewCam}.jpg`} alt={`View of ${place ?? "the place"} from ${viewCam.replace("_", " ")}`} onError={() => setViewOk(false)} />
        ) : sp ? (
          <HubPlan label={`Where it stopped: ${sp.id}`} focus={{ xy: [sp.position_m[0], sp.position_m[1]], radius_m: 12, tone: tone === "bad" ? "bad" : "warn" }}
            legend={false} fit="contain" minHeight={0} />
        ) : null}
      </span>
      <figcaption>
        {pending ? " " : frame ? `${frame.cam.replace("_", " ")} at ${at ? hhmm(at) : ""}`
          : viewCam && viewOk ? `${viewCam.replace("_", " ")} · ${place ?? "the place"} · a still of the place, no footage of ${at ? hhmm(at) : "that minute"} yet`
            : "Where it stopped, on the floor plan"}
      </figcaption>
    </figure>
  );
}

export function CaseDetail({ siteId, a, keyed }: { siteId: string; a: CaseItem; keyed: boolean }) {
  const logEnd = useResource<{ as_of: string | null }>(`/v1/sites/${siteId}/exceptions?limit=50`); // (the Hub's own inbox: shared)
  const { cs, cf, run, scans, last, j } = useCase(a.c.case_id);
  const waybill = a.c.target.split(" ").at(-1) ?? a.c.target;
  const dims = scans.find((s) => s.dims_mm)?.dims_mm;
  const investigated = (run.data?.steps.length ?? 0) > 0;
  const href = investigated ? `/cases/${a.c.case_id}` : `/cases/${a.c.case_id}/investigate`;
  // every case's panel has the same parts, in the same order (Rexton 2 Nov): a short headline (where), one callout line
  // (what the records and cameras say), the details line (size · who asked · when opened), the actions, the picture,
  // where it was scanned
  const sub = [dims ? `${dims.map((d) => Math.round(d / 10)).join(" × ")} cm` : "",
    cs.data?.case.complaint ? (last && waited(last.t, cs.data.case.created_at) ? `customer waiting ${waited(last.t, cs.data.case.created_at)}` : "customer asked")
      : cs.data ? "no customer query" : "",
    cs.data ? `opened ${ago(cs.data.case.created_at)}` : ""].filter(Boolean).join(" · ");
  const ans = cs.data?.answer?.objects[0];
  const inside = ans?.inside ?? null;
  const ls = !inside ? ans?.last_scan ?? null : null;
  const records = cf.data?.objects[0]?.records ?? [];
  const truck = records.find((r) => r.event_kind === "container_loaded" || r.event_kind === "departed_facility");
  const truckLie = !!(inside && truck && Date.parse(truck.t) > Date.parse(inside.iso.carried_in_at) && Date.parse(truck.t) < Date.parse(inside.iso.until));
  // the same checkpoints as the case page: once the run placed it, the truck and the store read from it
  const cps = scans.length ? buildCheckpoints({ scans, records, barcode: waybill, truckSeen: inside ? !truckLie : undefined,
    storeSeenAt: inside ? inside.iso.carried_in_at : undefined, logEnd: logEnd.data?.as_of }) : null;
  const onItsWay = !!(cps?.some((c) => c.notDue) && !inside);
  const where = ls ? placeWords(ls.event_kind, ls.scan_point_id) : last ? placeWords(last.event_kind, last.station_id) : undefined;
  const head = inside ? `Most likely in the ${inside.place}.` : where ? `At the ${where}.` : last ? lastScanSentence(last.event_kind, last.station_id, last.t)
    : "No scans of this parcel at this hub.";
  const call: { text: string; tone: "bad" | "plain" } | null = !cs.data ? null : truckLie && truck
    ? { text: `Records say loaded on ${truck.station_id?.match(/D\d{2}/)?.[0] ?? "a truck"} at ${hhmm(truck.t)}. Cameras say it never left.`, tone: "bad" }
    : ls ? { text: `Last scan: ${low(momentLabel(ls.event_kind, ls.scan_point_id))} at ${hms(ls.at)}. ${ls.camera ? `Seen there on ${ls.camera.replace(/^cam_/, "").replaceAll("_", " ")}.` : "No camera has shown it since."}`, tone: "plain" }
    : last && !inside ? { text: `${lastScanSentence(last.event_kind, last.station_id, last.t)} ${missingNextSentence(last.event_kind)}`, tone: "plain" } : null;
  if (onItsWay && last && call) call.text = `${lastScanSentence(last.event_kind, last.station_id, last.t)} The scan log ends ${Math.round((Date.parse(logEnd.data!.as_of!) - Date.parse(last.t)) / 1000)} s later, before its next scan was due: it is on its way, not missing.`;
  return (
    <>
      {cs.data && j.data ? <h2 className="hb-d-h">{head}</h2> : <span className="hb-skel" style={{ width: "70%", height: 22, display: "block" }} aria-busy="true" />}
      {call && <p className="hb-d-lie" data-tone={call.tone}>{call.text}</p>}
      {sub && <p className="hb-d-sub">{sub}</p>}
      <div className="hb-d-acts">
        <Link className="hb-btn hb-btn-primary" href={href}>{investigated ? "Open case" : "Investigate"}</Link>
        <Link className="hb-btn" href={`/cases/${a.c.case_id}/search`}>Send someone to look</Link>
      </div>
      {!investigated && <p className="hb-d-note">{keyed ? "Investigate: about 4 min, ~US$0.30." : "Shows what the scan log knows."}</p>}
      {!cs.data ? <span className="hb-skel" style={{ width: "100%", aspectRatio: "16 / 9", display: "block", borderRadius: 10 }} aria-busy="true" />
        : inside ? <View siteId={siteId} point="SP-STORE-IN" at={inside.iso.carried_in_at} tone="ok" place={`the ${inside.place.replace(/ \(Z\d+\)$/, "").toLowerCase()} door`} />
        : <View siteId={siteId} point={ls?.scan_point_id ?? last?.station_id ?? last?.device_id} at={ls?.at ?? last?.t} tone={a.tone} place={placeWords(ls?.event_kind ?? last?.event_kind, ls?.scan_point_id ?? last?.station_id)} />}
      {cps && (
        <section className="hb-d-sec">
          <h3>Where it was scanned</h3>
          <CheckpointStrip cps={cps} compact vertical where />
        </section>
      )}
      {!inside && !ls && <NextCams caseId={a.c.case_id} />}
    </>
  );
}

/** The cameras that would show where it went after its last scan (the case's missing moment), as their views. */
export function NextCams({ caseId }: { caseId: string }) {
  const mm = useResource<MissingMoment>(`/v1/cases/${caseId}/missing-moment`);
  const next = mm.data?.objects[0]?.expected_next ?? [];
  const cams = [...new Map(next.map((e) => [camId.toHub(e.camera_id), e])).values()].slice(0, 4);
  if (!cams.length) return null;
  const said = (r: string) => (r === "seen" ? "Saw it" : r === "no_footage" ? "No footage yet" : r === "not_seen" ? "Not seen" : "Not checked yet");
  return (
    <section className="hb-d-sec">
      <h3>Where to look next</h3>
      <ul className="hb-next">
        {cams.map((e) => {
          const id = camId.toHub(e.camera_id);
          return (
            <li key={id}>
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={`/landing/posters/${id}.jpg`} alt={`View from ${id.replace("_", " ")}`} loading="lazy" decoding="async" />
              <span className="hb-next-cam">{id.replace("_", " ")}</span>
              <span className="hb-next-r" data-r={e.result}>{said(e.result)}</span>
            </li>
          );
        })}
      </ul>
    </section>
  );
}

export function ago(iso: string): string {
  const d = Math.floor((Date.now() - new Date(iso).getTime()) / 86400000);
  return d <= 0 ? "today" : d === 1 ? "yesterday" : `${d} days ago`;
}
