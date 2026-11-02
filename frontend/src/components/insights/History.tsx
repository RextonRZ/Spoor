"use client";
/**
 * Hub insights, last 30 days: the demo hub's history (backend forensics/demo_history.py; how it is made is in the README
 * and LIMITATIONS; on screen the hub is shown as the demo treats it, under the page's one "Demo hub data" chip). The month at a glance (stat tiles with their line), the loop over the month, where parcels
 * went missing, the tunnel's read rate with the named events shaded and today marked. One hue per chart; numbers in
 * text tokens; hover shows the day. Never evidence, never mixed into a case.
 */
import { useState } from "react";
import { Spark } from "./Board";

interface SimCase { where: string; what: string; answered: boolean; checked: boolean; confirmed: boolean; replanned: boolean;
  found_after_replan: boolean; answer_s: number | null }
interface Day { date: string; simulated: boolean; parcels: number | null; tunnel_read_rate: number; cases: SimCase[]; events: string[] }
export interface History {
  label: string; scale: { shift_minutes: number; day_hours: number };
  events: { days: string; group: string; what: string }[]; days: Day[];
  totals: { cases: number; answered: number; checked: number; confirmed: number; replanned: number; found_after_replan: number;
    median_answer_s: number | null; usd: number; usual_read_rate: number; today_read_rate: number };
  where: { where: string; what: string; cases: number }[];
}

const ACC = "#818cf8", GRID = "rgba(255, 255, 255, 0.08)", MUTE = "#8b909b", SURF = "#0e0f13";
const FIX: Record<string, string> = {
  "Reject chute": "Match the reject chute's cartons to their unload scans every hour",
  "Exception store": "Make the store-door scan-in a must",
  "Dock gates": "Read each parcel at the dock, or check cage contents before loading",
  "Chutes": "Check the sorter's chute assignments against the bag scans",
  "Cages": "Scan every carton taken out of a cage",
};
const day = (iso: string) => new Date(`${iso}T12:00:00`).toLocaleDateString("en-GB", { day: "numeric", month: "short" });

export function HistoryView({ h }: { h: History }) {
  const t = h.totals;
  const sim = h.days.filter((d) => d.simulated);
  const pct = (a: number, b: number) => (b ? Math.round((a / b) * 100) : 0);
  const days = h.days.map((d, i) => (i === h.days.length - 1 ? "Today" : day(d.date)));
  return (
    <div className="hi">

      <section className="in-sec" aria-labelledby="hi-glance">
        <h2 id="hi-glance" className="in-h2">The month at a glance</h2>
        <dl className="hi-tiles">
          <div><dt>Parcels a day</dt><dd>{Math.round(sim.reduce((a, d) => a + (d.parcels ?? 0), 0) / sim.length).toLocaleString("en-GB")}</dd>
            <Spark v={h.days.map((d) => d.parcels)} h={44} labels={days} fmt={(x) => `${Math.round(x).toLocaleString("en-GB")} parcels`} /></div>
          <div data-tone="warn"><dt>Tunnel read rate</dt><dd>{(t.today_read_rate * 100).toFixed(1)}% <small>today · usual {(t.usual_read_rate * 100).toFixed(1)}%</small></dd>
            <Spark v={h.days.map((d) => d.tunnel_read_rate)} h={44} tone="warn" labels={days} fmt={(x) => `${(x * 100).toFixed(1)}% read`} /></div>
          <div><dt>Lost-parcel cases</dt><dd>{t.cases} <small>about {(t.cases / sim.length).toFixed(1)} a day</small></dd>
            <Spark v={h.days.map((d) => d.cases.length)} h={44} labels={days} fmt={(x) => `${x} case${x === 1 ? "" : "s"}`} /></div>
          <div><dt>Time to Spoor&apos;s answer</dt><dd>{t.median_answer_s ? `${(t.median_answer_s / 60).toFixed(1)} min` : ""} <small>median</small></dd>
            <Spark v={h.days.map((d) => { const a = d.cases.map((c) => c.answer_s).filter((x): x is number => x != null).sort((p, q) => p - q); return a.length ? a[a.length >> 1] : null; })} h={44} labels={days} fmt={(x) => `${(x / 60).toFixed(1)} min`} /></div>
        </dl>
      </section>

      <section className="in-sec" aria-labelledby="hi-loop">
        <h2 id="hi-loop" className="in-h2">The loop, over the month</h2>
        <ol className="in-loop">
          <li><b>{t.cases}</b><span>Cases opened</span><em>customers asking, and the hub&apos;s own alerts</em></li>
          <li><b>{t.answered}</b><span>Answered by Spoor</span><em>{pct(t.answered, t.cases)}% of cases</em></li>
          <li><b>{t.checked}</b><span>Checked on the floor</span><em>staff marked Found or Not here</em></li>
          <li><b>{t.confirmed}</b><span>Found where Spoor said</span><em>{pct(t.confirmed, t.checked)}% of checks · {t.replanned} misses re-planned, {t.found_after_replan} then found</em></li>
        </ol>
      </section>

      <section className="in-sec" aria-labelledby="hi-where">
        <h2 id="hi-where" className="in-h2">Where parcels went missing</h2>
        <WhereBars rows={h.where} days={h.days} />
      </section>

      <section className="in-sec" aria-labelledby="hi-read">
        <h2 id="hi-read" className="in-h2">Tunnel read rate, day by day</h2>
        <ReadRate h={h} />
      </section>
    </div>
  );
}

/** where parcels went missing: per place, WHEN (a 30-day strip, one cell a day, darker = more cases, hover for the day),
 *  the last 7 days against the 7 before, and the fix (a bar beside the count only repeated the count: Rexton 3 Nov) */
function WhereBars({ rows, days }: { rows: History["where"]; days: Day[] }) {
  const [tip, setTip] = useState<{ row: string; i: number } | null>(null);
  const per = (where: string) => days.map((d) => d.cases.filter((c) => c.where === where).length);
  const top = Math.max(1, ...rows.flatMap((r) => per(r.where)));
  return (
    <ol className="hi-where">
      {rows.map((r) => {
        const v = per(r.where);
        const last7 = v.slice(-7).reduce((a, x) => a + x, 0), prev7 = v.slice(-14, -7).reduce((a, x) => a + x, 0);
        const trend = last7 > prev7 ? "up" : last7 < prev7 ? "down" : "flat";
        return (
          <li key={r.where + r.what}>
            <span className="hi-where-n">{r.cases}</span>
            <span className="hi-where-t"><b>{r.where}</b>{r.what}</span>
            <span className="hi-strip" onMouseLeave={() => setTip(null)}>
              {v.map((x, i) => (
                <i key={i} data-on={x ? "" : undefined} style={{ opacity: x ? 0.35 + 0.65 * (x / top) : undefined }}
                  onMouseEnter={() => setTip({ row: r.where, i })} />
              ))}
              {tip?.row === r.where && (
                <span className="db-tip" role="status" style={{ left: `${((tip.i + 0.5) / v.length) * 100}%` }}>
                  {tip.i === days.length - 1 ? "Today" : day(days[tip.i].date)}: {v[tip.i]} case{v[tip.i] === 1 ? "" : "s"}{days[tip.i].events[0] ? ` · ${days[tip.i].events[0]}` : ""}
                </span>
              )}
            </span>
            <span className="hi-trend" data-trend={trend}>{trend === "up" ? "▲" : trend === "down" ? "▼" : "="} {last7} <small>last 7 days, {prev7} the week before</small></span>
            <span className="hi-where-fix">{FIX[r.where] ?? ""}</span>
          </li>
        );
      })}
    </ol>
  );
}

function ReadRate({ h }: { h: History }) {
  const [hover, setHover] = useState<number | null>(null);
  const W = 1100, H = 190, L = 44, R = 14, T = 12, B = 26, n = h.days.length;
  const lo = 0.93, hi = 1.0;
  const X = (i: number) => L + (i / (n - 1)) * (W - L - R), Y = (v: number) => T + (1 - (v - lo) / (hi - lo)) * (H - T - B);
  const path = h.days.map((d, i) => `${i ? "L" : "M"}${X(i).toFixed(1)},${Y(d.tunnel_read_rate).toFixed(1)}`).join("");
  const bands = h.events.filter((e) => e.group === "Scan tunnel").map((e) => e.days.split("-").map(Number));
  const cur = hover != null ? h.days[hover] : null;
  return (
    <figure className="ic">
      <div className="ic-plot" onMouseLeave={() => setHover(null)} onMouseMove={(e) => {
        const r = (e.currentTarget as HTMLDivElement).getBoundingClientRect();
        setHover(Math.min(n - 1, Math.max(0, Math.round(((((e.clientX - r.left) / r.width) * W - L) / (W - L - R)) * (n - 1)))));
      }}>
        <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Tunnel read rate per day, last 30 days">
          {bands.map(([a, b]) => <rect key={a} x={X(a - 1) - 6} y={T} width={X((b ?? a) - 1) - X(a - 1) + 12} height={H - T - B} fill="#fbbf24" fillOpacity={0.07} />)}
          {[0.94, 0.96, 0.98, 1.0].map((v) => (
            <g key={v}><line x1={L} x2={W - R} y1={Y(v)} y2={Y(v)} stroke={GRID} />
              <text x={L - 8} y={Y(v) + 4} fill={MUTE} fontSize={11.5} textAnchor="end">{Math.round(v * 100)}%</text></g>
          ))}
          {h.days.map((d, i) => i % 5 === 0 || i === n - 1 ? <text key={d.date} x={X(i)} y={H - 6} fill={MUTE} fontSize={11.5} textAnchor="middle">{i === n - 1 ? "Today" : day(d.date)}</text> : null)}
          <path d={path} fill="none" stroke={ACC} strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />
          <circle cx={X(n - 1)} cy={Y(h.days[n - 1].tunnel_read_rate)} r={5} fill="#fbbf24" stroke={SURF} strokeWidth={2} />
          {cur && hover != null && <><line x1={X(hover)} x2={X(hover)} y1={T} y2={H - B} stroke="#c9ccd3" strokeOpacity={0.4} />
            <circle cx={X(hover)} cy={Y(cur.tunnel_read_rate)} r={4.5} fill={ACC} stroke={SURF} strokeWidth={2} /></>}
        </svg>
        {cur && hover != null && <div className="ic-tip" role="status" style={{ left: `${(X(hover) / W) * 100}%`, top: 0 }}>
          {hover === n - 1 ? "Today" : day(cur.date)}: {(cur.tunnel_read_rate * 100).toFixed(1)}%{cur.events.length ? ` · ${cur.events[0]}` : ""}</div>}
      </div>
      <p className="hi-note">Shaded: {h.events.find((e) => e.group === "Scan tunnel")?.what ?? "a named event"}. Today&apos;s {(h.totals.today_read_rate * 100).toFixed(1)}% is below the usual {(h.totals.usual_read_rate * 100).toFixed(1)}%: the scorecard flags the tunnel.</p>
    </figure>
  );
}
