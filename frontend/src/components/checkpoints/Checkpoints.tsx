"use client";
/**
 * The six scan checkpoints as one strip (lib/checkpoints), plus the scan tunnel's "scanner screen": the card a DWS
 * monitor shows for one parcel (photo, size, weight, masked barcode, the chute it was sent to, Read OK). Used by the
 * landing page and the case Answer, so both say the same thing.
 *
 * Motion (only where it explains): the rail draws left to right in time order and each step lands on it, 70 ms apart;
 * a missing step arrives dashed and stays quiet; a red step arrives last. Reduced motion: no movement, a plain fade.
 */
import Link from "next/link";
import { useState } from "react";
import { hms } from "@/lib/words";
import type { Checkpoint, ScannerScreen as Screen } from "@/lib/checkpoints";
import "./checkpoints.css";

/** "36 s", "10 min", "1 h 4 min": the time between two scans, written on the rail between them */
export function gapWords(a: string, b: string): string {
  const s = Math.max(0, Math.round((Date.parse(b) - Date.parse(a)) / 1000));
  if (s < 90) return `${s} s`;
  const m = Math.round(s / 60);
  return m < 60 ? `${m} min` : `${Math.floor(m / 60)} h ${m % 60} min`;
}

export function CheckpointStrip({ cps, compact = false, gaps = false, pending = false, vertical = false, where = false }: {
  cps: Checkpoint[]; compact?: boolean; gaps?: boolean; vertical?: boolean;
  /** each step that has a scanner links to it on the hub map (/hub?place=...), so a newcomer sees where it is */
  where?: boolean;
  /** no case yet: the six places only, no times and no "no scan here" (nothing is known) */
  pending?: boolean;
}) {
  return (
    <ol className={`ck${compact ? " ck-compact" : ""}${pending ? " ck-pending" : ""}${vertical ? " ck-vertical" : ""}`} aria-label="Scan checkpoints, in order">
      {cps.map((c, i) => {
        const nx = cps[i + 1];
        const gap = gaps && !pending && c.t && nx?.t ? gapWords(c.t, nx.t) : null;
        return (
        <li key={c.id} className="ck-step" data-state={pending ? "pending" : c.state} data-next={pending ? "pending" : nx?.state} style={{ "--i": i } as React.CSSProperties}>
          {gap && <span className="ck-gap">{gap}</span>}
          <span className="ck-node" aria-hidden="true">
            {pending ? i + 1 : c.state === "conflict" || c.state === "unscanned" ? "!" : c.state === "missing" ? "" : "✓"}
          </span>
          <span className="ck-label">{where && !pending && c.point
            ? <Link className="ck-label-link" href={`/hub?place=${encodeURIComponent(c.point)}`} title="Where is this? Opens it on the hub map">{c.label}</Link>
            : <>{pending && <b className="ck-n">{i + 1}</b>}{c.label}</>}</span>
          {pending ? null : c.state === "missing" || c.state === "unscanned" ? (
            <span className="ck-none">{c.none}</span>
          ) : (
            <span className="ck-time">{c.t ? hms(c.t) : ""}</span>
          )}
          {c.state === "conflict" ? (
            <span className="ck-red">
              <span>{c.records}</span>
              <span>{c.cameras}</span>
            </span>
          ) : (
            c.detail && <span className="ck-detail">{c.detail}</span>
          )}
          {c.cameras && c.state === "unscanned" && <span className="ck-red"><span>{c.cameras.replace(/^Cameras: carried in at /, "Cameras saw it carried in at ")}</span></span>}
          {c.cameras && c.state === "scanned" && <span className="ck-how">{c.cameras}</span>}
          {!compact && <span className="ck-how">{c.how}</span>}
        </li>
        );
      })}
    </ol>
  );
}

const num = (v: number | null, d = 1) => (v == null ? "n/a" : v.toFixed(d));

/** The scan tunnel's screen for one parcel, laid out like a real DWS monitor. */
export function ScannerScreen({ s, at, line = "Line A", photo: given }: { s: Screen; at: string | null; line?: string; photo?: string | null }) {
  // the tunnel record names its own photo (scanner_photo, e.g. "scanner/CTX….jpg", served from public/scanner)
  const [broken, setBroken] = useState(false);
  const photo = broken ? null : given ?? (s.photo ? `/${s.photo.replace(/^\/+/, "")}` : null);
  const rows: [string, string][] = [
    ["Width", `${num(s.width_cm)} cm`],
    ["Length", `${num(s.length_cm)} cm`],
    ["Height", `${num(s.height_cm)} cm`],
    ["Weight", `${num(s.weight_kg, 2)} kg`],
    ["Barcode", s.barcode ?? "not read"],
  ];
  return (
    <figure className="dws" aria-label="Scan tunnel screen for this parcel">
      <div className="dws-top">
        <span>Scan tunnel · {line}</span>
        <span className="dws-clock">{at ? hms(at) : ""}</span>
      </div>
      <div className="dws-body">
        <div className="dws-photo">
          {photo ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={photo} alt="The scan tunnel's photo of this parcel" onError={() => setBroken(true)} />
          ) : (
            <span className="dws-photo-none">
              <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 8h3l2-2.5h6L17 8h3v11H4zM12 17a4 4 0 1 0 0-8 4 4 0 0 0 0 8Z" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" /></svg>
              Tunnel photo comes with the next footage
            </span>
          )}
        </div>
        <dl className="dws-data">
          {rows.map(([k, v]) => (
            <div key={k}><dt>{k}</dt><dd>{v}</dd></div>
          ))}
          <div className="dws-chute"><dt>Assigned</dt><dd>→ Chute {s.chute ?? "n/a"}</dd></div>
        </dl>
      </div>
      <figcaption className={`dws-status${s.read_ok ? "" : " is-bad"}`}>
        <span className="dws-led" aria-hidden="true" />
        {s.read_ok ? "Read OK" : "No read"}
      </figcaption>
    </figure>
  );
}
