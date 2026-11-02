"use client";
/**
 * Hub insights (Rexton 2 Nov, tick 2315): the feedback loop, from records already in the store (GET
 * /sites/{id}/insights) and nothing else. Cases opened -> answered -> checked on the floor -> resolved; where the trail
 * breaks, with the fix in plain words; the records the cameras contradicted; how well the system checks itself; what it
 * cost. Every number links to what it was counted from (a case, the cameras, the spend). With no floor check recorded
 * yet it says so; a Go look "Found here" or "Not here" changes it on the next visit. Labelled "Demo hub data".
 * Operate surface: hairline sections, tabular numbers, no charts that would invent precision.
 */
import { useEffect, useState } from "react";
import { useResource } from "@/lib/api";
import type { Site } from "@/lib/types";
import type { Flow } from "@/components/insights/Charts";
import type { Score } from "@/components/insights/Scorecard";
import { Attention, Kpi, minuteLabels, Panel, Stages, WIN, type Action } from "@/components/insights/Board";
import { Pipeline } from "@/components/insights/Pipeline";
import { HistoryView, type History } from "@/components/insights/History";
import "@/app/hub/hub.css";
import "@/app/wall/cameras.css";
import "./insights.css";

interface Ranked { where: string; what: string; fix?: string; cases: string[] }
interface Insights {
  label: string;
  loop: { customer_asked: string[]; alerts: string[]; opened: string[]; answered: string[]; checked: string[]; confirmed: string[];
    refuted: string[]; resolved: string[]; resolved_on_camera: string[] };
  breaks: Ranked[]; disagreed: Ranked[];
  health: { scan_points_unseen: string[]; scan_points: number; checkpoint_cameras: { camera_id: string; clock_fitted: boolean }[];
    cameras_fitted: number; cameras: number; numbers_by_camera: { camera_id: string; outlined: number; labelled: number }[];
    footage_skipped: { share: number; case_id: string } | null };
  flow?: Flow;
  unread?: { matched: { waybill: string }[] } | null;
  actions?: Action[];
  scorecard?: Score;
  history?: History;
  cost: { usd: number; calls: number; cases_with_spend: number; answer_seconds: number[]; footage_hours: number };
}
interface Dash { cases: { case_id: string; target: string }[] }


export default function InsightsPage() {
  const sites = useResource<Site[]>("/v1/sites");
  const site = sites.data?.[0]?.site_id;
  const [range, setRange] = useState<"today" | "month">("today");
  const r = useResource<Insights>(site ? `/v1/sites/${site}/insights${range === "month" ? "?history=true" : ""}` : null);
  const dash = useResource<Dash>(site ? `/v1/sites/${site}/dashboard` : null);
  const name = (id: string) => dash.data?.cases.find((c) => c.case_id === id)?.target.split(" ").at(-1) ?? "the case";
  const d = r.data;

  return (
    <div className="hb in">
      <header className="in-head">
        <div>
          <h1 className="in-h1">Hub insights</h1>
          <p className="in-sub">How every checkpoint did this shift, what to fix first, and whether Spoor&apos;s answers held up on the floor.</p>
        </div>
        <div className="in-head-r">
          <div role="group" aria-label="Range" className="cm-seg in-range">
            <button type="button" aria-pressed={range === "today"} onClick={() => setRange("today")}>This shift</button>
            <button type="button" aria-pressed={range === "month"} onClick={() => setRange("month")}>Simulated history</button>
          </div>
          <span className="in-demo">Demo hub data</span>
        </div>
      </header>
      {range === "month" ? (d?.history ? <HistoryView h={d.history} /> : <div className="an-skel" style={{ height: 320, borderRadius: 12 }} aria-busy="true" />)
        : !d ? <div className="an-skel" style={{ height: 320, borderRadius: 12 }} aria-busy="true" /> : (
        <TodayBoard d={d} name={name} />
      )}
    </div>
  );
}

/** this shift as an ops dashboard: KPI tiles, throughput by stage + needs attention, checkpoint health, hop charts,
 *  the loop and the self-checks (all from the stored records) */
/** the shift up to minute `at` (a replay): each place's count in proportion to its scans so far, lines cut at `at` */
function upTo(sc: Score, at: number | null): Score {
  if (at == null) return sc;
  return { ...sc, rows: sc.rows.map((r) => {
    const all = r.per_minute.reduce((a, x) => a + x, 0) || 1, so = r.per_minute.slice(0, at + 1).reduce((a, x) => a + x, 0);
    const no_reads = Math.round((r.no_reads * so) / all);
    // the problem's own count follows the feed too ("19 labels not read" said 19 while the tile said 12)
    return { ...r, reads: Math.round((r.reads * so) / all), no_reads, per_minute: r.per_minute.map((x, i) => (i <= at ? x : 0)),
      problems: r.no_reads ? r.problems.map((p) => p.replace(new RegExp(`^${r.no_reads}\\b`), String(no_reads))) : r.problems };
  }) };
}

function TodayBoard({ d, name }: { d: Insights; name: (id: string) => string }) {
  // The board as a live feed (Rexton 3 Nov: the demo treats the hub as live): the shift's scan log arrives a minute
  // every 2 s from a third of the way in, then the board waits at the log's last minute. A real feed would push the
  // same updates. Reduced motion: the latest minute at once. (README: the demo feed is the recorded shift played back.)
  const total = d.scorecard?.minutes ?? 0;
  const [at, setAt] = useState<number | null>(() =>
    typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches ? null : Math.min(WIN - 1, Math.max(0, total - 2)));
  useEffect(() => {
    if (at == null) return;
    const t = window.setTimeout(() => setAt((a) => (a == null || a >= total - 2 ? null : a + 1)), 2000);
    return () => window.clearTimeout(t);
  }, [at, total]);
  const sc = d.scorecard ? upTo(d.scorecard, at) : undefined;
  const tunnel = sc?.rows.find((r) => r.group === "Scan tunnel");
  const reject = sc?.rows.find((r) => r.group === "Reject chute");
  const unloads = sc ? Array.from({ length: sc.minutes }, (_, i) => sc.rows.filter((r) => r.group === "Unload").reduce((a, r) => a + r.per_minute[i], 0)) : [];
  const unloaded = at == null ? d.flow?.parcels ?? 0 : unloads.slice(0, at + 1).reduce((a, x) => a + x, 0);
  const ans = d.cost.answer_seconds;
  const open = d.loop.opened.length - d.loop.resolved.length - (d.loop.resolved_on_camera ?? []).length;
  const rate = tunnel?.read_rate ?? null;
  const allMins = sc ? minuteLabels(sc) : undefined;
  const last = at ?? (sc ? sc.minutes - 1 : 0), from = Math.max(0, last - WIN + 1);
  const w = <T,>(v?: T[]) => v?.slice(from, last + 1);
  const mins = w(allMins);
  const scans = (x: number) => `${Math.round(x)} scans`;
  const t = (iso: string) => new Date(iso).toLocaleTimeString("en-GB", { timeZone: "Asia/Kuala_Lumpur", hour: "2-digit", minute: "2-digit" });
  return (
    <div className="db">
      <div className="db-kpis">
        <Kpi label="Parcels unloaded" value={String(unloaded)} sub={d.flow ? `${t(d.flow.window[0])} to ${at != null && allMins ? allMins[at] : t(d.flow.window[1])}` : ""}
          spark={w(unloads)} labels={mins} fmt={scans} />
        <Kpi label="Tunnel read rate" value={rate != null ? (rate * 100).toFixed(1) : "100"} unit="%" tone={rate != null && rate < 0.98 ? "warn" : "ok"}
          sub={<>target 98% · {tunnel?.no_reads ?? 0} not read</>} spark={w(tunnel?.per_minute)} labels={mins} fmt={scans} />
        <Kpi label="Reject chute" value={String(reject?.no_reads ?? 0)} unit=" cartons" tone={reject?.no_reads ? "warn" : "ok"} sub="unread, to match to their unload scans" spark={w(reject?.per_minute)} labels={mins} fmt={(x) => `${Math.round(x / 2)} cartons`} />
        <Kpi label="Open cases" value={String(Math.max(0, open))} tone={d.loop.customer_asked.length ? "bad" : "ok"}
          sub={`of ${d.loop.opened.length} opened, incl. ${(d.loop.resolved_on_camera ?? []).length} controls · ${d.loop.customer_asked.length} customer waiting`} />
        <Kpi label="Time to an answer" value={ans.length ? (ans[ans.length >> 1] / 60).toFixed(1) : "0"} unit=" min" sub={`median · ${d.cost.footage_hours} h of footage`} />
      </div>

      <div className="db-row db-row-21">
        {sc && <Panel title="Throughput by stage" meta={
          <span className="db-live"><i aria-hidden="true" />Live · <b>{allMins ? allMins[last] : ""}</b> · scans per minute, one scale</span>}>
          <Stages s={d.scorecard!} upto={at} /></Panel>}
        <Panel title="Needs attention" meta={`${d.actions?.length ?? 0} open`}>
          {d.actions?.length ? <Attention items={d.actions} name={name} /> : <p className="db-empty">Nothing to fix in the records.</p>}
        </Panel>
      </div>

      {sc && <Panel title="Checkpoint pipeline" meta={<span className="db-key"><span><i className="db-dot" data-tone="bad" />Problem</span> <span><i className="db-dot" data-tone="warn" />Watch</span> <span><i className="db-dot" data-tone="ok" />Fine</span> <span>· arrows: usual time between scans</span></span>}>
        <Pipeline s={sc} hops={d.flow?.hops ?? []} name={name} unread={d.unread?.matched.length ?? 0} />
      </Panel>}

      <div className="db-row db-row-111">
        <Panel title="Lost-parcel cases" meta="from opened to resolved">
          <ol className="db-loop">
            <li><b>{d.loop.opened.length}</b><span>Opened</span><em>incl. {(d.loop.resolved_on_camera ?? []).length} controls · {d.loop.customer_asked.length} by a customer</em></li>
            <li><b>{d.loop.answered.length}</b><span>Answered by Spoor</span><em>where it is, with the proof</em></li>
            <li><b>{(d.loop.resolved_on_camera ?? []).length + d.loop.resolved.length}</b><span>Resolved</span><em>{(d.loop.resolved_on_camera ?? []).length} controls seen on camera{d.loop.resolved.length ? `, ${d.loop.resolved.length} found by staff` : ""}</em></li>
            <li data-empty={d.loop.checked.length ? undefined : ""}><b>{d.loop.checked.length}</b><span>Checked on the floor</span>
              <em>{d.loop.checked.length ? `${d.loop.confirmed.length} found where Spoor said` : `of ${Math.max(0, open)} still open: staff mark it on Go look`}</em></li>
          </ol>
        </Panel>
        <Panel title="How Spoor learns" meta="from floor checks">
          <ul className="db-learn">
            <li><span className="db-learn-in">Not here</span><span className="db-learn-ar" aria-hidden="true">→</span>
              <span className="db-learn-out"><b>Re-plan</b><small>Muse Wonder</small></span><span className="db-learn-n">{d.loop.refuted.length}</span></li>
            <li><span className="db-learn-in">Found</span><span className="db-learn-ar" aria-hidden="true">→</span>
              <span className="db-learn-out"><b>Hub memory</b><small>guides the plan, never evidence</small></span><span className="db-learn-n">{d.loop.confirmed.length}</span></li>
          </ul>
        </Panel>
        <Panel title="How far to trust it">
          <dl className="db-dl">
            <div><dt>Camera clocks checked<small>against the sorter&apos;s own events, so times line up</small></dt><dd>{d.health.cameras_fitted} of {d.health.cameras}</dd></div>
            <div><dt>Scan points no camera sees<small>a gap where a parcel could go unseen</small></dt><dd>{d.health.scan_points_unseen.length} of {d.health.scan_points}</dd></div>
            <div><dt>Outlines carrying a number<small>a number only where no other carton could be the one scanned</small></dt><dd>{d.health.numbers_by_camera.reduce((a, c) => a + c.labelled, 0)} of {d.health.numbers_by_camera.reduce((a, c) => a + c.outlined, 0)}</dd></div>
            {d.health.footage_skipped && <div><dt>Footage never sent to the cloud<small>no parcel handling in it</small></dt><dd>{Math.round(d.health.footage_skipped.share * 100)}%</dd></div>}
            <div><dt>Model spend<small>every recorded call, all cases</small></dt><dd>US${d.cost.usd.toFixed(2)}</dd></div>
          </dl>
        </Panel>
      </div>
    </div>
  );
}
