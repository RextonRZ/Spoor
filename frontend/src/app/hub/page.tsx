"use client";
/**
 * Hub, ops-console style (owner 31 Oct): what needs attention, as tables, with the detail in a side panel.
 * - KPI strip: open cases, stalled parcels, places with stalls, found today (each switches to its tab).
 * - Tabs (an underline that slides to the chosen tab): Open cases (n) · Places (n) · Resolved (n).
 *   Open cases: a customer is waiting. Places: every scanner, its load in the log and what is stalled there now.
 *   Resolved: cases floor staff marked found.
 * - A row opens the detail panel on the right: the camera view of the place, the six scan checkpoints, where to look
 *   next and the actions (a case); or the parcels stalled at that place, each with Investigate (a place).
 * - Parcels (owner 1 Nov): every parcel scanned today (GET /sites/{id}/parcels): its last checkpoint, where, when, its
 *   size; a row opens it (tunnel photo, size, where it was last scanned, Open case / Investigate). /hub?parcel=CTX… opens one.
 * - Places opens on the hub map (owner 1 Nov): every scanner a numbered checkpoint on the hub from above; any place
 *   opens in the panel with "Where is this?" (its zone as a 3D map, from above, at eye height). List keeps the table.
 *   /hub?place=SP-DIV-C12 opens that place (links from a case's checkpoints).
 * Data: the case read models, the exceptions inbox (late next scan while the next scanner kept working) and the
 * per-scanner counts. Motion: state only (tab underline, panel in and out, 150-280 ms); reduced motion: none.
 */
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMemo, useRef, useState, useSyncExternalStore } from "react";
import { api, ApiError, invalidate, useResource } from "@/lib/api";
import { hhmm, minutes, missingNextSentence } from "@/lib/words";
import type { Capabilities, Site } from "@/lib/types";
import { ErrorState } from "@/components/ui";
import { SpoorLoader } from "@/components/brand/SpoorLoader";
import {
  CASE_PILL, CaseDetail, CasesTable, Drawer, Skeleton, Tabs, View, WIDE, onWideChange,
  type CaseItem, type Dashboard, type Tone,
} from "@/components/hub/parts";
import { HubMap, WhereIs } from "@/components/hub/HubMap";
import { placeName, STAGES, stageOf } from "@/lib/places";
import type { ParcelRow } from "@/components/case/Identity";
import "./hub.css";

interface Stalled { waybill: string; last_event_kind: string; read_point: string; last_at: string; age_s: number; expected_next: string; case_id: string | null }
interface Inbox { as_of: string | null; stalled: Stalled[] }
interface PlaceGroup { kind: "group"; key: string; place: string; point: string; lastKind: string; rows: Stalled[]; oldest: number; from: string; to: string }
/** any scanner, nothing stalled there (opened from the map, the list or a link) */
interface PointItem { kind: "point"; key: string; place: string; point: string }
/** a parcel from the day's scan log (the Parcels tab, a search suggestion) */
interface ParcelItem { kind: "parcel"; key: string; place: string; point: string; p: ParcelRow }
type Item = CaseItem | PlaceGroup | PointItem | ParcelItem;
type Open = (key: string, el: HTMLElement | null) => void;
const pointKey = (id: string) => `point|${id}`;
const noSubscribe = () => () => {};
interface Place { point: string; name: string; scans: number | null; noReads: number; stalled: Stalled[]; oldest: number; group: PlaceGroup | null }
type Tab = "cases" | "places" | "parcels" | "resolved";
const parcelKey = (id: string) => `parcel|${id}`;
const cm = (d: number[]) => [...d].sort((a, b) => b - a).map((v) => (v / 10).toFixed(0)).join(" × ");
type Sort = "stalled" | "busiest" | "name";
const SORTS: Record<Sort, { label: string; by: (a: Place, b: Place) => number }> = {
  stalled: { label: "Most stalled", by: (a, b) => b.stalled.length - a.stalled.length || b.oldest - a.oldest || (b.scans ?? 0) - (a.scans ?? 0) },
  busiest: { label: "Busiest", by: (a, b) => (b.scans ?? 0) - (a.scans ?? 0) },
  name: { label: "A to Z", by: (a, b) => a.name.localeCompare(b.name, "en", { numeric: true }) },
};

const siteLine = (name: string | undefined) => (name ?? "Hub").replace(/\s*\(fictional\)/i, "").replace(/^CONTOH Express /, "CONTOH Express · ");
const lower = (t: string) => t.charAt(0).toLowerCase() + t.slice(1);
const rangeWords = (g: PlaceGroup) => `${hhmm(g.from)}${hhmm(g.to) !== hhmm(g.from) ? `–${hhmm(g.to)}` : ""}`;

export default function HubPage() {
  const sites = useResource<Site[]>("/v1/sites");
  const site = sites.data?.[0];
  const inbox = useResource<Inbox>(site ? `/v1/sites/${site.site_id}/exceptions?limit=50` : null);
  const dash = useResource<Dashboard>(site ? `/v1/sites/${site.site_id}/dashboard` : null);
  const parcelList = useResource<{ total: number; parcels: ParcelRow[] }>(site ? `/v1/sites/${site.site_id}/parcels?limit=2000` : null);
  const counts = useResource<{ points: { point: string; scans: number; no_reads: number }[] }>(site ? `/v1/sites/${site.site_id}/scan-points` : null);
  const caps = useResource<Capabilities>("/v1/capabilities");
  const keyed = !!(caps.data?.sam || caps.data?.spark);
  // /hub?place=SP-DIV-C12 (a case's checkpoint): starts on Places with that scanner open, until the user picks
  const linked = useSyncExternalStore(noSubscribe, () => {
    const p = new URLSearchParams(window.location.search).get("place");
    return p?.startsWith("SP-") ? p : null;
  }, () => null);
  const linkedParcel = useSyncExternalStore(noSubscribe, () => new URLSearchParams(window.location.search).get("parcel"), () => null);
  const [tabPicked, setTab] = useState<Tab | null>(null);
  const tab: Tab = tabPicked ?? (linkedParcel ? "parcels" : linked ? "places" : "cases");
  const [sort, setSort] = useState<Sort>("stalled");
  const [pview, setPview] = useState<"map" | "list">("map");
  const [q, setQ] = useState("");
  const [openPicked, setOpenKey] = useState<string | null | undefined>(undefined);
  const openKey = openPicked === undefined ? (linkedParcel ? parcelKey(linkedParcel) : linked ? pointKey(linked) : null) : openPicked;
  const opener = useRef<HTMLElement | null>(null);

  const caseItem = (c: Dashboard["cases"][number]): CaseItem => {
    const [pill, tone] = CASE_PILL[c.status] ?? CASE_PILL.unknown;
    return { kind: "case", key: c.case_id, c, pill, tone };
  };
  const openAll = useMemo(() => (dash.data?.cases ?? []).filter((c) => c.status !== "found").map(caseItem), [dash.data]);
  const resolvedAll = useMemo(() => (dash.data?.cases ?? []).filter((c) => c.status === "found").map(caseItem), [dash.data]);
  const hit = (a: CaseItem) => !q.trim() || a.c.target.toUpperCase().includes(q.trim().toUpperCase());
  const shownOpen = openAll.filter(hit);
  const shownResolved = resolvedAll.filter(hit);
  // stalled parcels, one group per place (a parcel already in an open case is that case's, not a stall)
  const groups = useMemo<PlaceGroup[]>(() => {
    const inCase = new Set(openAll.map((a) => a.c.target.split(" ").at(-1)));
    const by = new Map<string, Stalled[]>();
    for (const s of inbox.data?.stalled ?? []) {
      if (inCase.has(s.waybill)) continue;
      by.set(s.read_point, [...(by.get(s.read_point) ?? []), s]);
    }
    return [...by.entries()].map(([point, rows]) => {
      const sorted = [...rows].sort((a, b) => b.age_s - a.age_s);
      const times = rows.map((r) => r.last_at).sort();
      return { kind: "group" as const, key: `place|${point}`, place: placeName(point), point, lastKind: sorted[0].last_event_kind,
        rows: sorted, oldest: sorted[0].age_s, from: times[0], to: times.at(-1)! };
    });
  }, [inbox.data, openAll]);
  const places = useMemo<Place[]>(() => {
    const rows = new Map<string, Place>();
    for (const c of counts.data?.points ?? []) {
      if (c.point.startsWith("SP-")) rows.set(c.point, { point: c.point, name: placeName(c.point), scans: c.scans, noReads: c.no_reads, stalled: [], oldest: 0, group: null });
    }
    for (const g of groups) {
      const r = rows.get(g.point) ?? { point: g.point, name: g.place, scans: null, noReads: 0, stalled: [], oldest: 0, group: null };
      rows.set(g.point, { ...r, stalled: g.rows, oldest: g.oldest, group: g });
    }
    return [...rows.values()].sort(SORTS[sort].by);
  }, [counts.data, groups, sort]);

  const wide = useSyncExternalStore(onWideChange, () => window.matchMedia(WIDE).matches, () => true);
  const items: Item[] = [...openAll, ...resolvedAll, ...groups];
  // docked: the top open case (else the place with most stalls) is chosen from the start, so the page is never empty
  const first = openAll[0] ?? [...groups].sort((a, b) => b.rows.length - a.rows.length || b.oldest - a.oldest)[0] ?? null;
  // a scanner opened from the map / list / a link shows its stalls when it has any, else the place itself
  const pointItem = (k: string | null): Item | null => {
    if (!k?.startsWith("point|")) return null;
    const id = k.slice(6);
    return groups.find((g) => g.point === id) ?? { kind: "point", key: k, place: placeName(id), point: id };
  };
  // wide screens dock the detail on the right; x closes it (the map / table takes the room), picking anything reopens it
  const [docked, setDocked] = useState(true);
  const parcelItem = (k: string | null): Item | null => {
    if (!k?.startsWith("parcel|")) return null;
    const row = parcelList.data?.parcels.find((x) => x.id === k.slice(7));
    return row ? { kind: "parcel", key: k, place: row.id, point: row.last?.point ?? "", p: row } : null;
  };
  const chosen = items.find((i) => i.key === openKey) ?? pointItem(openKey) ?? parcelItem(openKey) ?? (wide && docked ? first : null);
  const show: Open = (key, el) => { opener.current = el; setOpenKey(key); setDocked(true); };
  const dockOpen = wide && docked;
  const stalledAt = useMemo(() => Object.fromEntries(groups.map((g) => [g.point, g.rows.length])), [groups]);
  const chosenPoint = chosen && chosen.kind !== "case" ? chosen.point : null;
  const close = () => { setOpenKey(null); opener.current?.focus(); };

  const ready = !!inbox.data && !!dash.data;
  const err = sites.error ?? inbox.error ?? dash.error;
  const nStalled = groups.reduce((n, g) => n + g.rows.length, 0);
  const total = openAll.length + nStalled;
  const kpis: { label: string; n: number; tone?: Tone; tab: Tab }[] = [
    { label: "Open cases", n: openAll.length, tone: openAll.length ? "bad" : undefined, tab: "cases" },
    { label: "Stalled parcels", n: nStalled, tone: nStalled ? "warn" : undefined, tab: "places" },
    { label: "Places with stalls", n: groups.length, tone: groups.length ? "warn" : undefined, tab: "places" },
    { label: "Found today", n: dash.data?.kpis.found ?? 0, tone: dash.data?.kpis.found ? "ok" : undefined, tab: "resolved" },
  ];
  const tabs: { id: Tab; label: string; n: number }[] = [
    { id: "cases", label: "Open cases", n: openAll.length },
    { id: "places", label: "Places", n: groups.length },
    { id: "parcels", label: "Parcels", n: parcelList.data?.total ?? 0 },
    { id: "resolved", label: "Resolved", n: resolvedAll.length },
  ];

  return (
    <div className="hb">
      <header className="hb-head">
        <div>
          <h1 className="hb-title" data-testid="hub-title">
            {!ready ? "Checking the hub" : total === 0 ? "Every parcel is on track" : `${total} parcel${total === 1 ? "" : "s"} need${total === 1 ? "s" : ""} attention`}
          </h1>
          <p className="hb-sub">{siteLine(site?.name)}{inbox.data?.as_of ? ` · scan log updated ${hhmm(inbox.data.as_of)}` : ""}</p>
        </div>
        <Link className="hb-btn" href="/wall">
          <svg viewBox="0 0 16 16" aria-hidden="true"><path d="M8 2.2 2.5 5v6L8 13.8 13.5 11V5zM2.5 5 8 7.8 13.5 5M8 7.8v6" /></svg>
          Open 3D hub
        </Link>
      </header>

      {err && <ErrorState error={err} what="the hub" onRetry={() => { inbox.reload(); dash.reload(); }} />}

      {!ready && !err && <SpoorLoader label="Reading the scan log" fill />}

      {ready && <div className={dockOpen ? "hb-split" : "hb-stack"}>
      <div className="hb-left">
      <dl className="hb-kpis">
        {kpis.map((k) => (
          <div key={k.label}>
            <button type="button" className="hb-kpi" onClick={() => setTab(k.tab)}>
              <dt>{k.tone && <i data-tone={k.tone} aria-hidden="true" />}{k.label}</dt>
              <dd>{ready ? k.n : <span className="hb-skel hb-skel-n" />}</dd>
            </button>
          </div>
        ))}
      </dl>

      <section className="hb-panel" aria-label="Alerts">
        <div className="hb-tabbar">
          <Tabs tabs={tabs} tab={tab} onTab={setTab} />
          {tab !== "places" && (
            <label className="hb-filter">
              <svg viewBox="0 0 20 20" aria-hidden="true"><circle cx="8.5" cy="8.5" r="5.5" /><path d="m12.6 12.6 4 4" /></svg>
              <span className="sp-sr">{tab === "parcels" ? "Filter parcels by tracking number" : "Filter cases by tracking number"}</span>
              <input type="search" placeholder="Filter by tracking number" value={q} onChange={(e) => setQ(e.target.value)} autoComplete="off" spellCheck={false} />
            </label>
          )}
          {tab === "places" && (
            <div className="hb-places-tools">
              {pview === "list" && (
                <label className="hb-sort">
                  <span>Sort</span>
                  <select value={sort} onChange={(e) => setSort(e.target.value as Sort)}>
                    {(Object.keys(SORTS) as Sort[]).map((x) => <option key={x} value={x}>{SORTS[x].label}</option>)}
                  </select>
                </label>
              )}
              <div className="hb-vtog" role="radiogroup" aria-label="Show places as">
                {(["map", "list"] as const).map((x) => (
                  <button key={x} type="button" role="radio" aria-checked={pview === x} onClick={() => setPview(x)}>{x === "map" ? "Map" : "List"}</button>
                ))}
              </div>
            </div>
          )}
        </div>
        <div role="tabpanel" aria-label={tabs.find((t) => t.id === tab)?.label}>
          {!ready ? <Skeleton /> : tab === "parcels" ? (
            <ParcelsTable rows={parcelList.data?.parcels ?? null} q={q} openKey={chosen?.key ?? null} onOpen={show} />
          ) : tab === "places" ? (pview === "map"
            ? <HubMap stalled={stalledAt} selected={chosenPoint} onOpen={(id, el) => show(pointKey(id), el)} />
            : <PlacesTable places={places} openKey={chosen?.key ?? null} counted={!!counts.data} onOpen={show} />
          ) : (
            <CasesTable rows={tab === "cases" ? shownOpen : shownResolved} openKey={chosen?.key ?? null} onOpen={show} asOf={inbox.data?.as_of ?? null}
              empty={q ? "No case matches that tracking number. Check the number, or clear the filter." : tab === "cases" ? "No open cases. A case opens when a customer asks, or when you investigate a stalled parcel under Places."
                : "No cases resolved yet. A case lands here once floor staff mark the parcel found."} />
          )}
        </div>
      </section>

      <p className="hb-note">A parcel shows as stalled when its next scan is late and the next scanner kept working. You hear about it before the customer calls.</p>
      </div>

      {dockOpen && site && ready && (
        <aside className="hb-dock" aria-label="Detail" aria-live="polite">
          {chosen ? (
            <div className="hb-dock-in" key={chosen.key}>
              <DetailHead item={chosen}>
                <button type="button" className="hb-x" aria-label="Close detail" onClick={() => { setDocked(false); setOpenKey(null); opener.current?.focus(); }}>
                  <svg viewBox="0 0 16 16" aria-hidden="true"><path d="M4 4l8 8M12 4l-8 8" /></svg>
                </button>
              </DetailHead>
              <div className="hb-drawer-body"><DetailBody item={chosen} siteId={site.site_id} keyed={keyed} onOpen={show} /></div>
            </div>
          ) : (
            <p className="hb-dock-empty">Nothing needs attention. Pick any row to see it here.</p>
          )}
        </aside>
      )}
      </div>}

      {!wide && site && chosen && <Drawer key={chosen.key} label={chosen.kind === "case" ? "Case detail" : `${chosen.place} detail`}
        head={(x) => <DetailHead item={chosen}>{x}</DetailHead>} onClose={close}>
        <DetailBody item={chosen} siteId={site.site_id} keyed={keyed} onOpen={show} />
      </Drawer>}
    </div>
  );
}

/** Places: every scanner, how busy it was in the log, and what is stalled there now; a row opens the place (its stalls
 *  when it has any). */
function PlacesTable({ places, openKey, counted, onOpen }: { places: Place[]; openKey: string | null; counted: boolean; onOpen: Open }) {
  if (!places.length) return <p className="hb-empty">No scans at this hub yet. Places fill in as the scan log is imported.</p>;
  return (
    <div className="hb-table" aria-label="Places">
      <div className="hb-tr hb-th hb-cols-place">
        <span>Place</span><span className="hb-num">Scans in the log</span>
        <span className="hb-num">No reads</span><span className="hb-num">Stalled now</span>
        <span className="hb-num">Longest stall</span><span />
      </div>
      {places.map((r) => {
        const cells = (
          <>
            <span className="hb-place"><i data-tone={r.stalled.length ? "warn" : undefined} aria-hidden="true" />{r.name}</span>
            <span className="hb-num">{r.scans ?? ""}</span>
            <span className="hb-num hb-dim">{r.scans === null ? "" : r.noReads}</span>
            <span className="hb-num">{r.stalled.length ? <b className="hb-warn">{r.stalled.length}</b> : <span className="hb-dim">0</span>}</span>
            <span className="hb-num">{r.stalled.length ? minutes(r.oldest) : ""}</span>
            <span className="hb-chev" aria-hidden="true">›</span>
          </>
        );
        const key = r.group?.key ?? pointKey(r.point);
        return (
          <button key={r.point} type="button" className={`hb-tr hb-cols-place${r.group ? "" : " hb-tr-quiet"}`} data-stalled={r.group ? "" : undefined}
            aria-pressed={openKey === key} onClick={(e) => onOpen(key, e.currentTarget)}>{cells}</button>
        );
      })}
      {!counted && <p className="hb-foot">Scan counts per place appear once the backend is updated. Stalls are shown now.</p>}
    </div>
  );
}

function DetailHead({ item, children }: { item: Item; children?: React.ReactNode }) {
  return (
    <div className="hb-drawer-head">
      {item.kind === "case"
        ? <><span className="hb-chip" data-tone={item.tone}>{item.pill}</span><span className="hb-mono">{item.c.target.split(" ").at(-1)}</span></>
        : item.kind === "parcel"
          ? <><span className="hb-chip" data-tone={item.p.case_id ? "bad" : "step"}>{item.p.case_id ? "In a case" : `Checkpoint ${stageOf(item.point)}`}</span><span className="hb-mono">{item.p.id}</span></>
        : item.kind === "group"
          ? <><span className="hb-chip" data-tone="warn">{item.rows.length} stalled</span><span className="hb-drawer-place">{item.place}</span></>
          : <><span className="hb-chip" data-tone="step">Checkpoint {stageOf(item.point)}</span><span className="hb-drawer-place">{item.place}</span></>}
      {children}
    </div>
  );
}

function DetailBody({ item, siteId, keyed, onOpen }: { item: Item; siteId: string; keyed: boolean; onOpen: Open }) {
  const pick = (id: string, el: HTMLElement) => onOpen(pointKey(id), el);
  return item.kind === "case" ? <CaseDetail siteId={siteId} a={item} keyed={keyed} />
    : item.kind === "group" ? <PlaceDetail siteId={siteId} g={item} onPick={pick} />
      : item.kind === "parcel" ? <ParcelDetail siteId={siteId} it={item} onPick={pick} /> : <PointDetail p={item} onPick={pick} />;
}

/** A place with nothing stalled: which step of the journey it is, how it scans, and where it is. */
function PointDetail({ p, onPick }: { p: PointItem; onPick: (id: string, el: HTMLElement) => void }) {
  const s = STAGES[stageOf(p.point) - 1];
  return (
    <>
      <h2 className="hb-d-h">Checkpoint {s.n} of {STAGES.length}: {lower(s.label)}.</h2>
      <p className="hb-d-sub">{s.how} · scanner <span className="hb-mono">{p.point}</span> · nothing stalled here now</p>
      <section className="hb-d-sec">
        <h3>Where this is</h3>
        <WhereIs point={p.point} onPick={onPick} />
      </section>
    </>
  );
}

function PlaceDetail({ siteId, g, onPick }: { siteId: string; g: PlaceGroup; onPick: (id: string, el: HTMLElement) => void }) {
  return (
    <>
      <h2 className="hb-d-h">{g.rows.length} parcel{g.rows.length === 1 ? "" : "s"} stopped at {lower(g.place)}. {missingNextSentence(g.lastKind)}</h2>
      <p className="hb-d-sub">Last scans {rangeWords(g)} · longest stall {minutes(g.oldest)} · next scan expected: {g.rows[0].expected_next}</p>
      <p className="hb-d-note">{g.rows.length > 1 ? "Several parcels at one place usually means one cause there. Start with the oldest." : "Investigate to see where it went."}</p>
      <View siteId={siteId} point={g.point} at={g.to} tone="warn" place={lower(g.place)} />
      <section className="hb-d-sec">
        <h3>Stalled parcels, oldest first</h3>
        <ul className="hb-rows">{g.rows.map((s) => <StalledRow key={s.waybill} siteId={siteId} s={s} />)}</ul>
      </section>
      <section className="hb-d-sec">
        <h3>Where this is</h3>
        <WhereIs point={g.point} onPick={onPick} />
      </section>
    </>
  );
}

function StalledRow({ siteId, s }: { siteId: string; s: Stalled }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
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
    <li className="hb-row">
      <span className="hb-mono">{s.waybill}</span>
      <span className="hb-dim">{hhmm(s.last_at)}</span>
      <span className="hb-warn">{minutes(s.age_s)}</span>
      <button type="button" className="hb-btn hb-btn-sm" onClick={investigate} disabled={busy} aria-busy={busy}>{busy ? "Opening" : "Investigate"}</button>
      {err && <span className="hb-err" role="alert">{err}</span>}
    </li>
  );
}

/** Parcels: every parcel scanned at the hub today, newest scan first; a row opens it in the panel. */
function ParcelsTable({ rows, q, openKey, onOpen }: { rows: ParcelRow[] | null; q: string; openKey: string | null; onOpen: Open }) {
  if (!rows) return <Skeleton />;
  const v = q.trim().toUpperCase();
  const shown = v ? rows.filter((r) => r.id.toUpperCase().includes(v)) : rows;
  if (!shown.length) return <p className="hb-empty">{v ? "No parcel scanned today matches that tracking number." : "No scans imported yet."}</p>;
  return (
    <div className="hb-table" aria-label="Parcels">
      <div className="hb-tr hb-th hb-cols-parcel">
        <span>Parcel</span><span>Last checkpoint</span><span>Where</span><span className="hb-num">When</span><span className="hb-num">Size (cm)</span><span />
      </div>
      {shown.slice(0, 300).map((r) => {
        const n = r.last ? stageOf(r.last.point) : 0;
        return (
          <button key={r.id} type="button" className="hb-tr hb-cols-parcel" aria-pressed={openKey === parcelKey(r.id)} onClick={(e) => onOpen(parcelKey(r.id), e.currentTarget)}>
            <span className="hb-mono">{r.id}{r.case_id && <i className="hb-incase">In a case</i>}</span>
            <span className="hb-step">{n > 0 && <b>{n}</b>}{n > 0 ? STAGES[n - 1].label : ""}</span>
            <span className="hb-ellipsis hb-dim">{r.last ? placeName(r.last.point) : ""}</span>
            <span className="hb-num">{r.last ? hhmm(r.last.t) : ""}</span>
            <span className="hb-num hb-dim">{r.dims_mm ? cm(r.dims_mm) : ""}</span>
            <span className="hb-chev" aria-hidden="true">›</span>
          </button>
        );
      })}
      {shown.length > 300 && <p className="hb-foot">Showing the 300 most recent of {shown.length}. Filter by tracking number to find the rest.</p>}
    </div>
  );
}

/** One parcel from the day's log: what the scanners know (tunnel photo, size, last scan), where that is, and the action. */
function ParcelDetail({ siteId, it, onPick }: { siteId: string; it: ParcelItem; onPick: (id: string, el: HTMLElement) => void }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [photoOk, setPhotoOk] = useState(true);
  const r = it.p;
  const n = r.last ? stageOf(r.last.point) : 0;
  async function investigate() {
    setBusy(true);
    try {
      const c = await api<{ case: { case_id: string } }>("/v1/cases", { method: "POST", json: {
        site_id: siteId, question: `Where did parcel ${r.id} go after its last scan?`, target_description: `parcel ${r.id}`,
        identifiers: [{ scheme: "carrier_waybill", value: r.id }] } });
      invalidate("/v1/cases");
      router.push(`/cases/${c.case.case_id}/investigate`);
    } catch { setBusy(false); }
  }
  return (
    <>
      <h2 className="hb-d-h">{r.last ? `Last scanned ${n ? `at checkpoint ${n}, ` : ""}${lower(placeName(r.last.point))}, at ${hhmm(r.last.t)}.` : "No scans at this hub."}</h2>
      <p className="hb-d-sub">{r.scans} scan{r.scans === 1 ? "" : "s"} today{r.dims_mm ? ` · ${cm(r.dims_mm)} cm` : ""}{r.weight_g ? ` · ${(r.weight_g / 1000).toFixed(2)} kg` : ""}{r.container ? ` · in ${r.container}` : ""}</p>
      <div className="hb-d-actions">
        {r.case_id
          ? <Link className="hb-btn hb-btn-primary" href={`/cases/${r.case_id}`}>Open case</Link>
          : <button type="button" className="hb-btn hb-btn-primary" onClick={investigate} disabled={busy} aria-busy={busy}>{busy ? "Opening" : "Investigate"}</button>}
      </div>
      {photoOk && r.tunnel_t && (
        <figure className="hb-view">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <span className="hb-view-img"><img src={`/scanner/${r.id}.jpg`} alt={`The scan tunnel's photo of ${r.id}`} onError={() => setPhotoOk(false)} /></span>
          <figcaption>Scan tunnel photo at {hhmm(r.tunnel_t)}: its label and barcode, as the tunnel read them</figcaption>
        </figure>
      )}
      {r.last && (
        <section className="hb-d-sec">
          <h3>Where it was last scanned</h3>
          <WhereIs point={r.last.point} onPick={onPick} />
        </section>
      )}
    </>
  );
}
