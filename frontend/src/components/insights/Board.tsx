"use client";
/**
 * Hub insights as an ops dashboard (Rexton 3 Nov: "follow a professional hub dashboard"): a grid of panels read in a
 * few seconds. KPI tiles (label, big tabular number, one context line, a small trend), throughput by stage as small
 * multiples on ONE scale, a compact "Needs attention" list, a checkpoint health grid (one tile per place, status first),
 * then the hop charts, the loop and the self-checks. Work surface: no ambient motion; hover and press states only
 * (emil: 140-160 ms ease-out, scale 0.97 on press, none under reduced motion). Data: GET /sites/{id}/insights.
 */
import Link from "next/link";
import { useState } from "react";
import { placeName } from "@/lib/places";
import type { Score, ScoreRow } from "./Scorecard";
import "./board.css";

const ACC = "#818cf8";
const STATUS = { ok: "Fine", warn: "Watch", bad: "Problem" } as const;
type Tone = keyof typeof STATUS;

export function Panel({ title, meta, children, className = "" }: { title: string; meta?: React.ReactNode; children: React.ReactNode; className?: string }) {
  return (
    <section className={`db-panel ${className}`} aria-label={title}>
      <header className="db-ph"><h2>{title}</h2>{meta && <span className="db-pm">{meta}</span>}</header>
      {children}
    </section>
  );
}

export function Spark({ v, h = 30, tone = "acc" }: { v: (number | null)[]; h?: number; tone?: "acc" | "warn" | "bad" }) {
  const W = 200;
  const xs = v.map((y, i) => [i, y] as const).filter((p): p is readonly [number, number] => p[1] != null);
  if (xs.length < 2) return <svg className="db-spark" viewBox={`0 0 ${W} ${h}`} aria-hidden="true" />;
  const lo = Math.min(...xs.map((p) => p[1])), hi = Math.max(...xs.map((p) => p[1]));
  const X = (i: number) => (i / Math.max(1, v.length - 1)) * (W - 4) + 2, Y = (y: number) => h - 3 - ((y - lo) / Math.max(1e-9, hi - lo)) * (h - 6);
  const col = tone === "warn" ? "#fbbf24" : tone === "bad" ? "#f87171" : ACC;
  const line = xs.map(([i, y]) => `${X(i).toFixed(1)},${Y(y).toFixed(1)}`).join(" ");
  return (
    <svg className="db-spark" viewBox={`0 0 ${W} ${h}`} preserveAspectRatio="none" aria-hidden="true">
      <polygon points={`${X(xs[0][0])},${h} ${line} ${X(xs.at(-1)![0])},${h}`} fill={col} fillOpacity={0.1} />
      <polyline points={line} fill="none" stroke={col} strokeWidth={1.6} vectorEffect="non-scaling-stroke" strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  );
}

export function Kpi({ label, value, unit, sub, tone, spark }: { label: string; value: string; unit?: string; sub: React.ReactNode; tone?: Tone; spark?: (number | null)[] }) {
  return (
    <div className="db-kpi" data-tone={tone}>
      <span className="db-kpi-l">{tone && tone !== "ok" && <i className="db-dot" data-tone={tone} />}{label}</span>
      <span className="db-kpi-v">{value}{unit && <small>{unit}</small>}</span>
      <span className="db-kpi-s">{sub}</span>
      {spark && <Spark v={spark} tone={tone === "warn" ? "warn" : tone === "bad" ? "bad" : "acc"} />}
    </div>
  );
}

/** throughput per stage, per minute, every row on the same scale (so the rows compare) */
export function Stages({ s }: { s: Score }) {
  const stages = [["Unload", ["Unload"]], ["Scan tunnel", ["Scan tunnel"]], ["Sorter", ["Sorter"]], ["Chutes", ["Chutes", "Reject chute"]],
    ["Bagging", ["Bagging"]]] as const;
  const series = stages.map(([name, groups]) => {
    const rows = s.rows.filter((r) => (groups as readonly string[]).includes(r.group));
    return { name, total: rows.reduce((a, r) => a + r.reads + r.no_reads, 0), v: Array.from({ length: s.minutes }, (_, i) => rows.reduce((a, r) => a + (r.per_minute[i] ?? 0), 0)) };
  });
  const max = Math.max(1, ...series.flatMap((x) => x.v));
  const W = 400, H = 34;
  const t = (m: number) => new Date(Date.parse(s.start) + m * 60000).toLocaleTimeString("en-GB", { timeZone: "Asia/Kuala_Lumpur", hour: "2-digit", minute: "2-digit" });
  return (
    <div className="db-stages">
      {series.map((x) => (
        <div key={x.name} className="db-stage">
          <span className="db-stage-n">{x.name}</span>
          <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" aria-label={`${x.name}: ${x.total} scans`}>
            <line x1={0} x2={W} y1={H - 0.5} y2={H - 0.5} stroke="rgba(255,255,255,0.08)" />
            <polygon points={`0,${H} ${x.v.map((y, i) => `${(i / (x.v.length - 1)) * W},${H - 2 - (y / max) * (H - 4)}`).join(" ")} ${W},${H}`} fill={ACC} fillOpacity={0.12} />
            <polyline points={x.v.map((y, i) => `${(i / (x.v.length - 1)) * W},${H - 2 - (y / max) * (H - 4)}`).join(" ")} fill="none" stroke={ACC} strokeWidth={1.5} vectorEffect="non-scaling-stroke" />
          </svg>
          <span className="db-stage-t">{x.total}</span>
        </div>
      ))}
      <div className="db-stage db-stage-axis" aria-hidden="true"><span /><span><i>{t(0)}</i><i>{t(Math.round(s.minutes / 2))}</i><i>{t(s.minutes)}</i></span><span>scans</span></div>
    </div>
  );
}

/** one tile per place (like places as one tile), status first */
export function Health({ s, name }: { s: Score; name: (id: string) => string }) {
  const groups: { g: string; rows: ScoreRow[] }[] = [];
  s.rows.forEach((r) => { const last = groups.at(-1); if (last && last.g === r.group) last.rows.push(r); else groups.push({ g: r.group, rows: [r] }); });
  const tiles = groups.flatMap(({ g, rows }) => rows.length < 3 ? rows.map((r) => ({ key: r.id, title: placeName(r.id), rows: [r] })) : [{ key: g, title: `${g} · ${rows.length} places`, rows }]);
  return (
    <ul className="db-health">
      {tiles.map((t) => {
        const tone: Tone = t.rows.some((r) => r.status === "bad") ? "bad" : t.rows.some((r) => r.status === "warn") ? "warn" : "ok";
        const through = t.rows.reduce((a, r) => a + r.reads + r.no_reads, 0);
        const rate = t.rows.some((r) => r.read_rate != null) ? Math.min(...t.rows.map((r) => r.read_rate ?? 1)) : null;
        const prob = t.rows.flatMap((r) => r.problems)[0];
        const cases = t.rows.flatMap((r) => r.cases);
        const reads = t.rows.reduce((a, r) => a + r.reads, 0);
        return (
          <li key={t.key} className="db-ht" data-tone={tone}>
            <span className="db-ht-h"><i className="db-dot" data-tone={tone} title={STATUS[tone]} /><span>{t.title}</span></span>
            <span className="db-ht-v">{through}<small>{reads === 0 ? " unread" : rate != null ? ` · ${(rate * 100).toFixed(1)}% read` : " · all read"}</small></span>
            <Spark v={t.rows[0].per_minute.map((_, i) => t.rows.reduce((a, r) => a + r.per_minute[i], 0))} h={22} tone={tone === "ok" ? "acc" : tone} />
            <span className="db-ht-p">{prob ?? "No problems"}{cases[0] && <> · <Link href={`/cases/${cases[0]}`}>{name(cases[0])}</Link></>}</span>
          </li>
        );
      })}
    </ul>
  );
}

export interface Action { key: string; tone: "bad" | "warn"; count: number; unit: string; title: string; why: string; fix: string;
  cases: string[]; parcels: { waybill: string; t: string }[] }

/** the fix list, compact: severity, what, the fix; its parcels open in place (grid-rows 0fr to 1fr, 220 ms ease-out) */
export function Attention({ items, name }: { items: Action[]; name: (id: string) => string }) {
  return (
    <ol className="db-att">
      {items.map((a) => <AttRow key={a.key} a={a} name={name} />)}
    </ol>
  );
}

function AttRow({ a, name }: { a: Action; name: (id: string) => string }) {
  const [open, setOpen] = useState(false);
  const hm = (iso: string) => new Date(iso).toLocaleTimeString("en-GB", { timeZone: "Asia/Kuala_Lumpur", hour: "2-digit", minute: "2-digit" });
  return (
    <li className="db-att-i" data-tone={a.tone}>
      <i className="db-dot" data-tone={a.tone} />
      <div>
        <p className="db-att-h"><b>{a.count}</b> {a.title}</p>
        <p className="db-att-f">{a.fix}</p>
        <div className="db-att-a">
          {a.cases[0] && <Link href={`/cases/${a.cases[0]}`}>Open {name(a.cases[0])}</Link>}
          {a.parcels.length > 0 && <button type="button" aria-expanded={open} onClick={() => setOpen((v) => !v)}>{open ? "Hide the parcels" : `${a.parcels.length} parcels`}</button>}
        </div>
        {a.parcels.length > 0 && (
          <div className="db-att-l" data-open={open ? "" : undefined} inert={!open}>
            <div><ul>{a.parcels.map((p) => <li key={p.waybill}><Link href={`/hub?parcel=${p.waybill}`}>{p.waybill}</Link><span>{hm(p.t)}</span></li>)}</ul></div>
          </div>
        )}
      </div>
    </li>
  );
}
