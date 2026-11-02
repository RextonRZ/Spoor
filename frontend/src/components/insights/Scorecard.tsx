"use client";
/**
 * Checkpoint scorecard (Rexton 2 Nov, Hub insights): one row per scan point in flow order, the way a shift supervisor
 * reads a board. Status dot (red: an answered case or a contradicted record at the place; amber: read rate under the
 * stated threshold or unread cartons; green), items through, read rate, the usual time from the item's previous scan,
 * the shift as a small scans-per-minute line (one clock for every row), and the problem in words with its case.
 * A group of like places (12 chutes, 12 bag scans) folds into one row that opens in place (instantly: a board is
 * scanned many times a shift, so no motion on it).
 * Data: GET /sites/{id}/insights "scorecard" (stored scan records only).
 */
import Link from "next/link";
import { Fragment, useState } from "react";
import { placeName } from "@/lib/places";

export interface ScoreRow { id: string; group: string; reads: number; no_reads: number; read_rate: number | null; usual_s: number | null;
  per_minute: number[]; problems: string[]; cases: string[]; status: "ok" | "warn" | "bad" }
export interface Score { start: string; minutes: number; read_warn: number; rows: ScoreRow[] }

const secs = (s: number | null) => (s == null ? "" : s < 90 ? `${Math.round(s)} s` : `${(s / 60).toFixed(1)} min`);
const pct = (r: number | null) => (r == null ? "" : `${(r * 100).toFixed(1)}%`);
const worst = (rows: ScoreRow[]) => (rows.some((r) => r.status === "bad") ? "bad" : rows.some((r) => r.status === "warn") ? "warn" : "ok");
const STATUS = { ok: "Fine", warn: "Watch", bad: "Problem" } as const;

function Spark({ v, max }: { v: number[]; max: number }) {
  const W = 120, H = 26;
  const pts = v.map((y, i) => `${((i / Math.max(1, v.length - 1)) * W).toFixed(1)},${(H - 2 - (y / Math.max(1, max)) * (H - 4)).toFixed(1)}`).join(" ");
  return (
    <svg className="sc-spark" viewBox={`0 0 ${W} ${H}`} aria-hidden="true">
      <polyline points={pts} fill="none" stroke="#818cf8" strokeWidth={1.5} strokeLinejoin="round" strokeLinecap="round" vectorEffect="non-scaling-stroke" />
    </svg>
  );
}

function Row({ r, max, name, sub }: { r: ScoreRow; max: number; name: (id: string) => string; sub?: boolean }) {
  return (
    <tr data-status={r.status} data-sub={sub ? "" : undefined}>
      <td><span className="sc-dot" data-status={r.status} title={STATUS[r.status]} /><span className="sp-sr">{STATUS[r.status]}</span></td>
      <th scope="row">{placeName(r.id)}</th>
      <td className="sc-num">{r.reads + r.no_reads}</td>
      <td className="sc-num" data-low={r.read_rate != null && r.read_rate < 0.98 ? "" : undefined}>{r.reads === 0 ? "" : pct(r.read_rate) || "100%"}</td>
      <td className="sc-num">{secs(r.usual_s)}</td>
      <td><Spark v={r.per_minute} max={max} /></td>
      <td className="sc-prob">{r.problems.join("; ")}{r.cases.map((c) => <Fragment key={c}> · <Link href={`/cases/${c}`}>{name(c)}</Link></Fragment>)}</td>
    </tr>
  );
}

export function Scorecard({ s, name }: { s: Score; name: (id: string) => string }) {
  const [open, setOpen] = useState<Record<string, boolean>>({});
  const groups: { g: string; rows: ScoreRow[] }[] = [];
  s.rows.forEach((r) => { const last = groups.at(-1); if (last && last.g === r.group) last.rows.push(r); else groups.push({ g: r.group, rows: [r] }); });
  const max = Math.max(1, ...s.rows.map((r) => Math.max(...r.per_minute)));
  const t = (m: number) => new Date(Date.parse(s.start) + m * 60000).toLocaleTimeString("en-GB", { timeZone: "Asia/Kuala_Lumpur", hour: "2-digit", minute: "2-digit" });
  return (
    <div className="sc">
      <table className="sc-table">
        <thead>
          <tr><th scope="col"><span className="sp-sr">Status</span></th><th scope="col">Place</th><th scope="col" className="sc-num">Through</th>
            <th scope="col" className="sc-num">Read rate</th><th scope="col" className="sc-num">Usual time</th>
            <th scope="col">Shift <span className="sc-t">{t(0)} to {t(s.minutes)}</span></th><th scope="col">Problems</th></tr>
        </thead>
        <tbody>
          {groups.map(({ g, rows }) => rows.length < 3 ? rows.map((r) => <Row key={r.id} r={r} max={max} name={name} />) : (
            <Fragment key={g}>
              <tr className="sc-group" data-status={worst(rows)}>
                <td><span className="sc-dot" data-status={worst(rows)} /></td>
                <th scope="row">
                  <button type="button" aria-expanded={!!open[g]} onClick={() => setOpen((o) => ({ ...o, [g]: !o[g] }))}>
                    <svg viewBox="0 0 12 12" aria-hidden="true"><path d="m4.5 3 3 3-3 3" /></svg>{g} <span>{rows.length} places</span>
                  </button>
                </th>
                <td className="sc-num">{rows.reduce((a, r) => a + r.reads + r.no_reads, 0)}</td>
                <td className="sc-num">{rows.some((r) => r.read_rate != null) ? pct(Math.min(...rows.map((r) => r.read_rate ?? 1))) : "100%"}</td>
                <td className="sc-num">{secs(rows.map((r) => r.usual_s ?? 0).filter(Boolean).sort((a, b) => a - b)[rows.length >> 1] ?? null)}</td>
                <td><Spark v={rows[0].per_minute.map((_, i) => rows.reduce((a, r) => a + r.per_minute[i], 0) / rows.length)} max={max} /></td>
                <td className="sc-prob">{rows.flatMap((r) => r.problems).join("; ") || (worst(rows) === "ok" ? "None" : "")}</td>
              </tr>
              {open[g] && rows.map((r) => <Row key={r.id} r={r} max={max} name={name} sub />)}
            </Fragment>
          ))}
        </tbody>
      </table>
      <p className="sc-key"><span className="sc-dot" data-status="bad" /> Problem: an answered case or a record the cameras contradicted, at this place
        <span className="sc-dot" data-status="warn" /> Watch: read rate under {Math.round(s.read_warn * 100)}% or unread cartons
        <span className="sc-dot" data-status="ok" /> Fine. Usual time: from the item&apos;s previous scan.</p>
    </div>
  );
}
