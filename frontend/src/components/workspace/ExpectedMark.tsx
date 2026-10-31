"use client";
/**
 * Where the parcel should appear on a frame (design_sprint §G, Rexton 08:49: "why is the box circling air?").
 * Before analysis there is nothing to box: a named pin marks the spot ("Should pass here 14:32:31–34 · not checked
 * yet"). Only a typed result draws a box: red dashed for "not seen here". A sighting is drawn by the parcel's own track
 * box, so "seen" adds nothing here.
 */
import { clock, type ExpectedNext } from "@/lib/journey";

type Px = [number, number, number, number];

export function ExpectedMark({ row, compact = false }: { row: { result: ExpectedNext["result"] | null; window?: ExpectedNext["window"];
  expected_region_px: Px | null; region_basis_wh_px: [number, number] | null }; compact?: boolean }) {
  const r = row.expected_region_px;
  const b = row.region_basis_wh_px;
  if (!r || !b || row.result === "seen" || row.result === "no_footage") return null;
  const t = (iso: string) => clock(iso, false).replace(" MYT", "");
  const w = row.window;
  const span = w ? ` ${t(w.start)}–${t(w.end).slice(-2)}` : "";
  if (row.result === "not_seen") {
    return <span className="xm-box" title={w ? `Not seen here between ${t(w.start)} and ${t(w.end)}` : "Not seen here"}
      style={{ left: `${(r[0] / b[0]) * 100}%`, top: `${(r[1] / b[1]) * 100}%`, width: `${((r[2] - r[0]) / b[0]) * 100}%`,
        height: `${((r[3] - r[1]) / b[1]) * 100}%` }} />;
  }
  const x = ((r[0] + r[2]) / 2 / b[0]) * 100;
  const y = ((r[1] + r[3]) / 2 / b[1]) * 100;
  return (
    <span className="xm-pin" data-below={y < 22 ? "" : undefined} data-side={x > 66 ? "left" : x < 34 ? "right" : undefined}
      style={{ left: `${x}%`, top: `${y}%` }}>
      <span className="xm-dot" aria-hidden />
      {!compact && <span className="xm-label">Should pass here{span}<span className="xm-sub"> · not checked yet</span></span>}
    </span>
  );
}
