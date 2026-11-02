"use client";
/**
 * Checkpoint health as the hub's pipeline (Rexton 3 Nov): the stages left to right in the order a parcel meets them,
 * each a node (status, items through, read rate, its problem; the trend is the throughput panel's), joined by arrows that carry the hop between
 * them (the usual time, and the parcels overdue on it). The reject chute hangs off the sorter as a branch; the last
 * column is where parcels leave the floor (cages, the exception store, the dock gates). Phones: the same nodes stacked.
 */
import Link from "next/link";
import { placeName } from "@/lib/places";
import type { Score, ScoreRow } from "./Scorecard";

interface Hop { from: string; to: string; median_s: number; overdue: number; recent: number }
type Tone = "ok" | "warn" | "bad";
const toneOf = (rows: ScoreRow[]): Tone => (rows.some((r) => r.status === "bad") ? "bad" : rows.some((r) => r.status === "warn") ? "warn" : "ok");
const secs = (s: number) => (s < 90 ? `${Math.round(s)} s` : `${(s / 60).toFixed(1)} min`);

function Node({ title, rows, name, small }: { title: string; rows: ScoreRow[]; s?: Score; name: (id: string) => string; small?: boolean }) {
  if (!rows.length) return null;
  const tone = toneOf(rows);
  const through = rows.reduce((a, r) => a + r.reads + r.no_reads, 0);
  const reads = rows.reduce((a, r) => a + r.reads, 0);
  const rate = rows.some((r) => r.read_rate != null) ? Math.min(...rows.map((r) => r.read_rate ?? 1)) : null;
  const prob = rows.flatMap((r) => r.problems)[0];
  const cases = rows.flatMap((r) => r.cases);
  return (
    <div className="pl-node" data-tone={tone} data-small={small ? "" : undefined}>
      <span className="pl-node-h"><i className="db-dot" data-tone={tone} /><span>{title}</span>{rows.length > 2 && <em>{rows.length}</em>}</span>
      <span className="pl-node-v">{through}<small>{reads === 0 ? " unread" : rate != null ? ` · ${(rate * 100).toFixed(1)}% read` : ""}</small></span>
      {(prob || cases[0]) && <span className="pl-node-p">{prob}{cases[0] && <> · <Link href={`/cases/${cases[0]}`}>{name(cases[0])}</Link></>}</span>}
    </div>
  );
}

function Arrow({ hop, unread = 0 }: { hop?: Hop; unread?: number }) {
  const notRead = Math.min(unread, hop?.overdue ?? 0), late = (hop?.overdue ?? 0) - notRead;
  return (
    <div className="pl-arrow" data-warn={late || notRead ? "" : undefined}
      title={hop ? `${hop.from} to ${hop.to}: usually ${secs(hop.median_s)}${notRead ? `; ${notRead} not read at the tunnel` : ""}${late ? `; ${late} overdue` : ""}` : undefined}>
      <span className="pl-arrow-t">{hop ? secs(hop.median_s) : ""}</span>
      <svg viewBox="0 0 40 10" preserveAspectRatio="none" aria-hidden="true"><path d="M0 5H36M32 1.5 36.5 5 32 8.5" /></svg>
      <span className="pl-arrow-b">{[notRead ? `${notRead} not read` : "", late ? `${late} overdue` : ""].filter(Boolean).join(" · ")}</span>
    </div>
  );
}

export function Pipeline({ s, hops, name, unread = 0 }: { s: Score; hops: Hop[]; name: (id: string) => string;
  /** unload-only parcels traced to a tunnel no-read (not late: not read) */
  unread?: number }) {
  const g = (...groups: string[]) => s.rows.filter((r) => groups.includes(r.group));
  const hop = (from: string) => hops.find((h) => h.from === from);
  const single = (rows: ScoreRow[]) => (rows.length === 1 ? placeName(rows[0].id) : "");
  return (
    <div className="pl" role="group" aria-label="The hub's checkpoints, in the order a parcel meets them">
      <Node title="Unloading" rows={g("Unload")} s={s} name={name} />
      <Arrow hop={hop("Unloaded")} unread={unread} />
      <Node title="Scan tunnel" rows={g("Scan tunnel")} s={s} name={name} />
      <Arrow hop={hop("Label read")} />
      <Node title="Sorter induct" rows={g("Sorter")} s={s} name={name} />
      <Arrow hop={hop("On the sorter")} />
      <div className="pl-col">
        <Node title="Chutes" rows={g("Chutes")} s={s} name={name} />
        <div className="pl-branch"><Node title="Reject chute" rows={g("Reject chute")} s={s} name={name} small /></div>
      </div>
      <Arrow hop={hop("Into a chute")} />
      <Node title="Bagging" rows={g("Bagging")} s={s} name={name} />
      <Arrow />
      <div className="pl-col pl-out">
        <Node title="Cages" rows={g("Cages")} s={s} name={name} small />
        <Node title="Store door" rows={g("Exception store")} s={s} name={name} small />
        <Node title="Dock gates" rows={g("Dock gates")} s={s} name={name} small />
      </div>
    </div>
  );
}
