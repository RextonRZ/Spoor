"use client";
/**
 * Hub dashboard (QUEUE H15): what a hub or regional manager watches. Every number comes from GET /sites/{id}/dashboard,
 * which aggregates the same journey and missing-moment read models the cases use. Empty states say why a number is
 * missing instead of showing a zero that would look like a result.
 */
import Link from "next/link";
import { useResource } from "@/lib/api";
import { cam } from "@/lib/journey";
import { zoneId } from "@/lib/hub";
import HubPlan, { ZONE_NAMES } from "@/components/plan/HubPlan";
import { Loading, ErrorState } from "@/components/ui";
import "./dashboard.css";

interface Dashboard {
  label: string;
  kpis: { open_cases: number; cases: number; located: number; found: number; median_hours_to_locate: number | null;
    median_cost_usd: number | null; total_cost_usd: number };
  trail_ends_by_zone: { zone_id: string; zone: string; cases: number }[];
  cameras_relied_on: { camera_id: string; cases: number }[];
  conflicts_by_read_point: { read_point: string; count: number }[];
  cases: { case_id: string; question: string; target: string; status: string; open_hours: number;
    trail_end: { zone_id: string | null; zone: string | null; t: string | null; event_kind: string | null }; depends_on_cameras: string[];
    model_calls: number; cost_usd: number }[];
}

const usd = (v: number | null) => (v === null ? "—" : v === 0 ? "US$0" : `US$${v.toFixed(v < 1 ? 3 : 2)}`);

export function HubDashboard({ siteId }: { siteId?: string }) {
  const d = useResource<Dashboard>(siteId ? `/v1/sites/${siteId}/dashboard` : null);
  if (d.error) return <ErrorState error={d.error} what="the hub dashboard" onRetry={d.reload} />;
  if (!d.data) return <Loading label="Loading the hub dashboard" lines={4} />;
  const k = d.data.kpis;
  const maxCam = Math.max(1, ...d.data.cameras_relied_on.map((c) => c.cases));
  return (
    <section className="dash" aria-labelledby="dash-h">
      <div className="sp-row sp-wrap" style={{ justifyContent: "space-between", gap: 10 }}>
        <h2 className="sp-h2" id="dash-h">Hub dashboard</h2>
        <span className="sp-chip sp-chip-sim">{d.data.label}</span>
      </div>
      <dl className="dash-kpis">
        <Kpi label="Open cases" value={String(k.open_cases)} hint={`of ${k.cases}`} />
        <Kpi label="Located or found" value={String(k.located)} hint={k.located ? undefined : "none yet: needs analysed footage or a floor search"} />
        <Kpi label="Median time to locate" value={k.median_hours_to_locate === null ? "—" : `${k.median_hours_to_locate} h`}
          hint={k.median_hours_to_locate === null ? "no case located yet" : undefined} />
        <Kpi label="Model cost per case" value={usd(k.median_cost_usd)} hint={`total ${usd(k.total_cost_usd)}`} />
      </dl>

      <div className="dash-grid">
        <div className="sp-panel">
          <div className="sp-panel-head"><h3 className="sp-h3">Where evidence trails end</h3>
            <span className="sp-caption" style={{ margin: 0 }}>cases per zone</span></div>
          <div className="sp-panel-body">
            <HubPlan label={`Hub plan shaded by where cases' evidence trails end: ${d.data.trail_ends_by_zone.map((z) => `${ZONE_NAMES[zoneId.toHub(z.zone_id)] ?? z.zone} ${z.cases}`).join(", ") || "none"}`}
              heat={Object.fromEntries(d.data.trail_ends_by_zone.map((z) => [zoneId.toHub(z.zone_id), z.cases]))} minHeight={300} />
            {d.data.trail_ends_by_zone.length === 0 && <p className="sp-muted">No case has a confirmed point yet.</p>}
          </div>
        </div>

        <div className="sp-stack" style={{ gap: 14 }}>
          <div className="sp-panel">
            <div className="sp-panel-head"><h3 className="sp-h3">Cameras the open cases depend on</h3></div>
            <div className="sp-panel-body">
              <ul className="dash-bars">
                {d.data.cameras_relied_on.map((c) => (
                  <li key={c.camera_id}>
                    <span className="dash-bar-label sp-num">{cam(c.camera_id)}</span>
                    <span className="dash-bar"><span style={{ width: `${(c.cases / maxCam) * 100}%` }} /></span>
                    <span className="sp-num">{c.cases}</span>
                  </li>
                ))}
                {d.data.cameras_relied_on.length === 0 && <li className="sp-muted">No camera with footage is due next in any case.</li>}
              </ul>
              <p className="sp-caption">Cameras with footage that watch, or come next after, each case&apos;s last confirmed point.</p>
            </div>
          </div>
          <div className="sp-panel">
            <div className="sp-panel-head"><h3 className="sp-h3">Records that disagree</h3></div>
            <div className="sp-panel-body">
              {d.data.conflicts_by_read_point.length ? (
                <ul className="dash-zones">{d.data.conflicts_by_read_point.map((c) => (
                  <li key={c.read_point}><span className="sp-num">{c.read_point}</span><span className="sp-num">{c.count}</span></li>))}</ul>
              ) : <p className="sp-muted" style={{ margin: 0 }}>None found: every pair of scans fits the belt timing.</p>}
              <p className="sp-caption">Scans faster than the belt route allows. Records-versus-video conflicts join this list once footage is analysed.</p>
            </div>
          </div>
        </div>
      </div>

      <div className="sp-panel">
        <div className="sp-panel-head"><h3 className="sp-h3">Cases</h3></div>
        <div className="sp-tablewrap">
          <table className="sp-table dash-table">
            <thead><tr><th>Case</th><th>Status</th><th>Trail ends</th><th>Depends on</th><th className="num">Open</th><th className="num">Cost</th></tr></thead>
            <tbody>
              {d.data.cases.map((c) => (
                <tr key={c.case_id}>
                  <td><Link href={`/cases/${c.case_id}/summary`}>{c.target}</Link></td>
                  <td><span className="sp-chip">{c.status}</span></td>
                  <td>{c.trail_end.zone_id ? (ZONE_NAMES[zoneId.toHub(c.trail_end.zone_id)] ?? c.trail_end.zone) : "nothing confirmed"}</td>
                  <td className="sp-num">{c.depends_on_cameras.map(cam).join(", ") || "none"}</td>
                  <td className="num">{c.open_hours} h</td>
                  <td className="num">{usd(c.cost_usd)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  );
}

function Kpi({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="dash-kpi">
      <dt className="sp-micro">{label}</dt>
      <dd className="dash-kpi-v sp-num">{value}</dd>
      {hint && <dd className="sp-caption" style={{ margin: 0 }}>{hint}</dd>}
    </div>
  );
}
