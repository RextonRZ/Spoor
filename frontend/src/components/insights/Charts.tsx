"use client";
/**
 * Hub insights charts (dataviz method): one hue (the accent) per chart, since each plots one measure; thin marks (bars
 * <= 18 px with a 4 px rounded end, 2 px lines, >= 8 px dots with a surface ring), hairline grid, labels only where the
 * story is, a hover tooltip on every mark and the same numbers as a table. Data: GET /sites/{id}/insights "flow" (the
 * whole scan log, parcel by parcel). Nothing is smoothed or estimated.
 */
import { useState } from "react";

export interface Hop { from: string; to: string; n: number; median_s: number; p10_s: number; p90_s: number; overdue: number; recent: number }
export interface Flow { parcels: number; window: [string, string]; hops: Hop[]; per_minute: { t: string; scans: number }[] }

const ACC = "#818cf8", MUTED = "rgba(201, 204, 211, 0.34)", GRID = "rgba(255, 255, 255, 0.08)", INK2 = "#c9ccd3", MUTE = "#8b909b";
const SURF = "#0e0f13";
const hm = (iso: string) => new Date(iso).toLocaleTimeString("en-GB", { timeZone: "Asia/Kuala_Lumpur", hour: "2-digit", minute: "2-digit" });
const SHORT: Record<string, string> = { Unloaded: "Unload", "Label read": "Tunnel", "On the sorter": "Sorter", "Into a chute": "Chute",
  "Into a bag or cage": "Bag or cage" };
const hopName = (h: Hop) => `${SHORT[h.from] ?? h.from} → ${SHORT[h.to] ?? h.to}`;
const secs = (s: number) => (s < 90 ? `${Math.round(s)} s` : `${(s / 60).toFixed(1)} min`);

function Tip({ tip }: { tip: { x: number; y: number; text: string } | null }) {
  return tip ? <div className="ic-tip" role="status" style={{ left: tip.x, top: tip.y }}>{tip.text}</div> : null;
}

/** per hop: parcels with no next scan, overdue (solid) vs the log ended first (muted) */
export function MissingByHop({ hops }: { hops: Hop[] }) {
  const [tip, setTip] = useState<{ x: number; y: number; text: string } | null>(null);
  const W = 520, row = 40, L = 132, R = 96, max = Math.max(1, ...hops.map((h) => h.overdue + h.recent));
  const sx = (v: number) => (v / max) * (W - L - R);
  return (
    <figure className="ic">
      <div className="ic-legend" aria-hidden="true"><span><i style={{ background: ACC }} />Overdue</span><span><i style={{ background: MUTED }} />Log ended before it was due</span></div>
      <div className="ic-plot" onMouseLeave={() => setTip(null)}>
        <svg viewBox={`0 0 ${W} ${hops.length * row + 8}`} role="img" aria-label="Parcels with no next scan, per hop">
          {hops.map((h, i) => {
            const y = i * row + 12, a = sx(h.overdue), b = sx(h.recent);
            const show = (e: React.MouseEvent, text: string) => setTip({ x: e.nativeEvent.offsetX + 12, y: e.nativeEvent.offsetY - 34, text });
            return (
              <g key={h.from + h.to}>
                <text x={0} y={y + 13} fill={INK2} fontSize={12.5}>{hopName(h)}</text>
                <line x1={L} x2={W - R} y1={y + 9} y2={y + 9} stroke={GRID} />
                {a > 0 && <path d={bar(L, y, a, 18, b > 0 ? "left" : "both")} fill={ACC}
                  onMouseMove={(e) => show(e, `${h.overdue} overdue: no ${h.to.toLowerCase()} scan after ${secs(2 * h.p90_s)}`)} />}
                {b > 0 && <path d={bar(L + a + (a > 0 ? 2 : 0), y, Math.max(2, b - (a > 0 ? 2 : 0)), 18, a > 0 ? "right" : "both")} fill={MUTED}
                  onMouseMove={(e) => show(e, `${h.recent}: the log ended before their ${h.to.toLowerCase()} scan was due`)} />}
                <text x={W - R + 10} y={y + 13} fill={h.overdue ? "#e0e7ff" : MUTE} fontSize={13} style={{ fontVariantNumeric: "tabular-nums" }}>
                  {h.overdue ? `${h.overdue} overdue` : "none overdue"}
                </text>
              </g>
            );
          })}
        </svg>
        <Tip tip={tip} />
      </div>
      <Table head={["Hop", "Overdue", "Log ended first"]} rows={hops.map((h) => [`${h.from} → ${h.to}`, h.overdue, h.recent])} />
    </figure>
  );
}

/** how long each hop takes: the usual range (10th to 90th percentile) and the median */
export function HopTimes({ hops }: { hops: Hop[] }) {
  const [tip, setTip] = useState<{ x: number; y: number; text: string } | null>(null);
  const W = 520, row = 38, L = 132, R = 64;
  const top = Math.max(...hops.map((h) => h.p90_s));
  const step = top > 150 ? 60 : top > 60 ? 30 : 10, max = Math.ceil(top / step) * step;
  const sx = (v: number) => L + (v / max) * (W - L - R);
  const ticks = Array.from({ length: max / step + 1 }, (_, i) => i * step);
  const H = hops.length * row + 26;
  return (
    <figure className="ic">
      <div className="ic-plot" onMouseLeave={() => setTip(null)}>
        <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Time each hop takes">
          {ticks.map((t) => (
            <g key={t}>
              <line x1={sx(t)} x2={sx(t)} y1={4} y2={H - 22} stroke={GRID} />
              <text x={sx(t)} y={H - 6} fill={MUTE} fontSize={11.5} textAnchor="middle" style={{ fontVariantNumeric: "tabular-nums" }}>{t ? secs(t) : "0"}</text>
            </g>
          ))}
          {hops.map((h, i) => {
            const y = i * row + 18;
            const text = `${h.from} → ${h.to}: usually ${secs(h.median_s)}; 8 in 10 between ${secs(h.p10_s)} and ${secs(h.p90_s)} (${h.n} parcels)`;
            return (
              <g key={h.from + h.to} onMouseMove={(e) => setTip({ x: e.nativeEvent.offsetX + 12, y: e.nativeEvent.offsetY - 34, text })}>
                <rect x={0} y={y - 16} width={W} height={row - 4} fill="transparent" />
                <text x={0} y={y + 4} fill={INK2} fontSize={12.5}>{hopName(h)}</text>
                <line x1={sx(h.p10_s)} x2={sx(h.p90_s)} y1={y} y2={y} stroke={ACC} strokeOpacity={0.45} strokeWidth={6} strokeLinecap="round" />
                <circle cx={sx(h.median_s)} cy={y} r={5} fill={ACC} stroke={SURF} strokeWidth={2} />
                <text x={W - R + 10} y={y + 4} fill={INK2} fontSize={13} style={{ fontVariantNumeric: "tabular-nums" }}>{secs(h.median_s)}</text>
              </g>
            );
          })}
        </svg>
        <Tip tip={tip} />
      </div>
      <Table head={["Hop", "Usual", "Fast (10th %)", "Slow (90th %)", "Parcels"]}
        rows={hops.map((h) => [`${h.from} → ${h.to}`, secs(h.median_s), secs(h.p10_s), secs(h.p90_s), h.n])} />
    </figure>
  );
}

/** scans per minute across the log (all checkpoints) */
export function ScansPerMinute({ data }: { data: Flow["per_minute"] }) {
  const [hover, setHover] = useState<number | null>(null);
  const W = 1100, H = 200, L = 36, R = 12, T = 10, B = 24;
  const max = Math.ceil(Math.max(1, ...data.map((d) => d.scans)) / 20) * 20;
  const sx = (i: number) => L + (i / Math.max(1, data.length - 1)) * (W - L - R);
  const sy = (v: number) => T + (1 - v / max) * (H - T - B);
  const line = data.map((d, i) => `${i ? "L" : "M"}${sx(i).toFixed(1)},${sy(d.scans).toFixed(1)}`).join("");
  const area = `${line}L${sx(data.length - 1)},${sy(0)}L${sx(0)},${sy(0)}Z`;
  const cur = hover != null ? data[hover] : null;
  return (
    <figure className="ic">
      <div className="ic-plot" onMouseLeave={() => setHover(null)}
        onMouseMove={(e) => {
          const r = (e.currentTarget as HTMLDivElement).getBoundingClientRect();
          const x = ((e.clientX - r.left) / r.width) * W;
          setHover(Math.min(data.length - 1, Math.max(0, Math.round(((x - L) / (W - L - R)) * (data.length - 1)))));
        }}>
        <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Scans per minute across the log">
          {[0, max / 2, max].map((v) => (
            <g key={v}>
              <line x1={L} x2={W - R} y1={sy(v)} y2={sy(v)} stroke={GRID} />
              <text x={L - 8} y={sy(v) + 4} fill={MUTE} fontSize={11.5} textAnchor="end" style={{ fontVariantNumeric: "tabular-nums" }}>{v}</text>
            </g>
          ))}
          {data.map((d, i) => i % 5 === 0 && (
            <text key={d.t} x={sx(i)} y={H - 6} fill={MUTE} fontSize={11.5} textAnchor="middle" style={{ fontVariantNumeric: "tabular-nums" }}>{hm(d.t)}</text>
          ))}
          <path d={area} fill={ACC} fillOpacity={0.1} />
          <path d={line} fill="none" stroke={ACC} strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />
          {cur && hover != null && <>
            <line x1={sx(hover)} x2={sx(hover)} y1={T} y2={H - B} stroke={INK2} strokeOpacity={0.4} />
            <circle cx={sx(hover)} cy={sy(cur.scans)} r={4.5} fill={ACC} stroke={SURF} strokeWidth={2} />
          </>}
        </svg>
        {cur && hover != null && <div className="ic-tip" role="status" style={{ left: `${(sx(hover) / W) * 100}%`, top: 0 }}>{hm(cur.t)}: {cur.scans} scans</div>}
      </div>
      <Table head={["Minute", "Scans"]} rows={data.map((d) => [hm(d.t), d.scans])} />
    </figure>
  );
}

function Table({ head, rows }: { head: string[]; rows: (string | number)[][] }) {
  return (
    <details className="ic-table">
      <summary>Show as a table</summary>
      <table>
        <thead><tr>{head.map((h) => <th key={h} scope="col">{h}</th>)}</tr></thead>
        <tbody>{rows.map((r, i) => <tr key={i}>{r.map((c, j) => <td key={j}>{c}</td>)}</tr>)}</tbody>
      </table>
    </details>
  );
}

/** a horizontal bar with a 4 px rounded data end (square at the baseline, and square where it meets the next segment) */
function bar(x: number, y: number, w: number, h: number, round: "left" | "right" | "both"): string {
  const r = Math.min(4, w / 2, h / 2);
  const rr = round === "left" ? 0 : r; // only the outer (data) end is rounded
  const end = round === "left" ? 0 : rr;
  return `M${x},${y}h${w - end}${end ? `a${end},${end} 0 0 1 ${end},${end}` : ""}v${h - 2 * end}${end ? `a${end},${end} 0 0 1 ${-end},${end}` : ""}h${-(w - end)}z`;
}
