"use client";
/**
 * Hub insights (Rexton 2 Nov, tick 2315): the feedback loop, from records already in the store (GET
 * /sites/{id}/insights) and nothing else. Cases opened -> answered -> checked on the floor -> resolved; where the trail
 * breaks, with the fix in plain words; the records the cameras contradicted; how well the system checks itself; what it
 * cost. Every number links to what it was counted from (a case, the cameras, the spend). With no floor check recorded
 * yet it says so; a Go look "Found here" or "Not here" changes it on the next visit. Labelled "Demo hub data".
 * Operate surface: hairline sections, tabular numbers, no charts that would invent precision.
 */
import Link from "next/link";
import { useResource } from "@/lib/api";
import type { Site } from "@/lib/types";
import { HopTimes, MissingByHop, ScansPerMinute, type Flow } from "@/components/insights/Charts";
import "@/app/hub/hub.css";
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
  cost: { usd: number; calls: number; cases_with_spend: number; answer_seconds: number[]; footage_hours: number };
}
interface Dash { cases: { case_id: string; target: string }[] }

const cam = (id: string) => id.replace(/^cam_/, "").replaceAll("_", " ");
const mins = (s: number) => (s < 90 ? `${Math.round(s)} s` : `${(s / 60).toFixed(1)} min`);
const plural = (n: number, w: string) => `${n} ${w}${n === 1 ? "" : "s"}`;

export default function InsightsPage() {
  const sites = useResource<Site[]>("/v1/sites");
  const site = sites.data?.[0]?.site_id;
  const r = useResource<Insights>(site ? `/v1/sites/${site}/insights` : null);
  const dash = useResource<Dash>(site ? `/v1/sites/${site}/dashboard` : null);
  const name = (id: string) => dash.data?.cases.find((c) => c.case_id === id)?.target.split(" ").at(-1) ?? "the case";
  const d = r.data;
  const CaseLinks = ({ ids }: { ids: string[] }) => (
    <span className="in-cases">{ids.map((id) => <Link key={id} href={`/cases/${id}`}>{name(id)}</Link>)}</span>
  );

  return (
    <div className="hb in">
      <header className="in-head">
        <div>
          <h1 className="in-h1">Hub insights</h1>
          <p className="in-sub">Where this hub loses parcels, and whether the answers held up on the floor.</p>
        </div>
        <span className="in-demo">{d?.label ?? "Demo hub data"}</span>
      </header>
      {!d ? <div className="an-skel" style={{ height: 320, borderRadius: 12 }} aria-busy="true" /> : (
        <>
          <section className="in-sec" aria-labelledby="in-loop">
            <h2 id="in-loop" className="in-h2">The loop</h2>
            <ol className="in-loop">
              <li><b>{d.loop.opened.length}</b><span>Cases opened</span>
                <em>{d.loop.customer_asked.length} customer asked · {plural(d.loop.alerts.length, "live alert")}</em></li>
              <li><b>{d.loop.answered.length}</b><span>Answered by Spoor</span><em>from the hub&apos;s own cameras and scans</em></li>
              <li data-empty={d.loop.checked.length ? undefined : ""}><b>{d.loop.checked.length}</b><span>Checked on the floor</span>
                <em>{d.loop.checked.length ? `${d.loop.confirmed.length} found where Spoor said · ${d.loop.refuted.length} not there` : "staff mark Found or Not here on Go look"}</em></li>
              <li><b>{d.loop.resolved.length + (d.loop.resolved_on_camera ?? []).length}</b><span>Resolved</span>
                <em>{d.loop.resolved.length} found by staff · {(d.loop.resolved_on_camera ?? []).length} confirmed on camera</em></li>
            </ol>
            <p className="in-note">
              {d.loop.checked.length
                ? <>Spoor&apos;s answer confirmed by staff: <b>{d.loop.confirmed.length} of {d.loop.checked.length}</b> checked.</>
                : <>No floor checks recorded yet. When staff mark a place on Go look, it counts here: a confirmed answer, or a miss that sends the agents back to plan again.</>}
            </p>
          </section>

          <section className="in-sec" aria-labelledby="in-breaks">
            <h2 id="in-breaks" className="in-h2">Where parcels go missing</h2>
            {d.breaks.length ? (
              <ul className="in-rank">
                {d.breaks.map((b) => (
                  <li key={b.where + b.what}>
                    <span className="in-n">{b.cases.length}</span>
                    <span className="in-what"><b>{b.where}</b>{b.what}</span>
                    <span className="in-fix">{b.fix}</span>
                    <CaseLinks ids={b.cases} />
                  </li>
                ))}
              </ul>
            ) : <p className="in-empty">No lost parcels among the cases yet.</p>}
          </section>

          {d.flow?.hops?.length ? (
            <section className="in-sec" aria-labelledby="in-flow">
              <h2 id="in-flow" className="in-h2">Across the whole scan log</h2>
              <p className="in-sub2">{d.flow.parcels} parcels, {new Date(d.flow.window[0]).toLocaleTimeString("en-GB", { timeZone: "Asia/Kuala_Lumpur", hour: "2-digit", minute: "2-digit" })} to {new Date(d.flow.window[1]).toLocaleTimeString("en-GB", { timeZone: "Asia/Kuala_Lumpur", hour: "2-digit", minute: "2-digit" })}, every parcel, not only the cases.</p>
              <div className="in-charts">
                <div className="in-chart">
                  <h3>No next scan</h3>
                  <p>Overdue: waited more than twice the slow end of that hop. The rest were still on their way when the log ended.</p>
                  <MissingByHop hops={d.flow.hops} />
                </div>
                <div className="in-chart">
                  <h3>How long each hop takes</h3>
                  <p>Dot: the usual time. Bar: 8 in 10 parcels.</p>
                  <HopTimes hops={d.flow.hops} />
                </div>
                <div className="in-chart in-chart-wide">
                  <h3>Scans per minute</h3>
                  <p>All checkpoints together.</p>
                  <ScansPerMinute data={d.flow.per_minute} />
                </div>
              </div>
            </section>
          ) : null}

          <section className="in-sec" aria-labelledby="in-dis">
            <h2 id="in-dis" className="in-h2">Records the cameras disagreed with</h2>
            {d.disagreed.length ? (
              <ul className="in-rank">
                {d.disagreed.map((b) => (
                  <li key={b.where + b.what} data-bad="">
                    <span className="in-n">{b.cases.length}</span>
                    <span className="in-what"><b>{b.where}</b>{b.what}</span>
                    <span className="in-fix">Check what the reader counts as loaded</span>
                    <CaseLinks ids={b.cases} />
                  </li>
                ))}
              </ul>
            ) : <p className="in-empty">No record contradicted by the cameras yet.</p>}
          </section>

          <section className="in-sec" aria-labelledby="in-health">
            <h2 id="in-health" className="in-h2">How well it can check itself</h2>
            <dl className="in-health">
              <div><dt>Scan points no camera sees</dt><dd><b>{d.health.scan_points_unseen.length}</b> of {d.health.scan_points}
                {d.health.scan_points_unseen.length ? <span>{d.health.scan_points_unseen.slice(0, 4).join(", ")}</span> : null}</dd></div>
              <div><dt>Camera clocks matched to the sorter</dt><dd><b>{d.health.cameras_fitted}</b> of {d.health.cameras}
                <span>close-ups: {d.health.checkpoint_cameras.map((c) => `${cam(c.camera_id)} ${c.clock_fitted ? "matched" : "not yet"}`).join(" · ")}</span></dd></div>
              <div><dt>Numbers shown on cartons</dt><dd>
                <b>{d.health.numbers_by_camera.reduce((a, c) => a + c.labelled, 0)}</b> of {d.health.numbers_by_camera.reduce((a, c) => a + c.outlined, 0)} outlines
                <span>{d.health.numbers_by_camera.filter((c) => c.labelled).map((c) => `${cam(c.camera_id)} ${c.labelled}`).join(" · ")}; a number only where no other carton could be it</span></dd></div>
              {d.health.footage_skipped && <div><dt>Footage skipped before the cloud</dt><dd><b>{Math.round(d.health.footage_skipped.share * 100)}%</b>
                <span>Glimmer sent only moments with parcel handling (<Link href={`/cases/${d.health.footage_skipped.case_id}/investigate`}>the run</Link>)</span></dd></div>}
            </dl>
            <p className="in-links"><Link href="/wall">Cameras</Link></p>
          </section>

          <section className="in-sec" aria-labelledby="in-cost">
            <h2 id="in-cost" className="in-h2">What it cost</h2>
            <dl className="in-health">
              <div><dt>Model spend, all cases</dt><dd><b>US${d.cost.usd.toFixed(2)}</b><span>{d.cost.calls} recorded calls across {plural(d.cost.cases_with_spend, "case")} (<Link href="/operator">ledger</Link>)</span></dd></div>
              {d.cost.answer_seconds.length > 0 && <div><dt>Time to an answer</dt><dd><b>{mins(d.cost.answer_seconds[d.cost.answer_seconds.length >> 1])}</b>
                <span>median of {plural(d.cost.answer_seconds.length, "run")}, against {d.cost.footage_hours} h of footage a person would scroll</span></dd></div>}
            </dl>
          </section>
          <p className="in-foot">With real hub data, this ranks the places that lose parcels most. Every count comes from stored records; nothing is estimated.</p>
        </>
      )}
    </div>
  );
}
