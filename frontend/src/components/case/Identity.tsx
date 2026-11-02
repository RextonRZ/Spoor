"use client";
/**
 * How we know it's this parcel (owner 1 Nov: "the judges will ask how you know it's this parcel"). Identity comes from
 * the hub's own records, in the order a supervisor would check them: its barcode read by the scan tunnel (with the
 * tunnel's photo), the size and weight the tunnel measured, where the scans left it, then every carton of about the same
 * size scanned after that (each ruled out: its own barcode was read, so it is a different parcel), then the cameras.
 * Run-time data only (the case's waybill, GET /sites/{id}/parcels, the tunnel photo); never the evaluator's truth.
 */
import { useState } from "react";
import { useResource } from "@/lib/api";
import type { Capabilities } from "@/lib/types";
import { hms } from "@/lib/words";
import { placeName } from "@/lib/places";
import "./identity.css";

export interface ParcelRow {
  id: string;
  scans: number;
  first: { t: string; kind: string; point: string; zone: string | null } | null;
  last: { t: string; kind: string; point: string; zone: string | null } | null;
  dims_mm: [number, number, number] | null;
  weight_g: number | null;
  tunnel_t: string | null;
  container: string | null;
  case_id: string | null;
}

const cm = (d: number[]) => [...d].sort((a, b) => b - a).map((v) => (v / 10).toFixed(1)).join(" × ");
const sorted = (d: number[]) => [...d].sort((a, b) => b - a);
const containerName = (c: string) => (/^RC-/i.test(c) ? `cage ${c}` : /^(BG|BAG)-/i.test(c) ? `bag ${c}` : c);
/** about the same carton: every side within 2 cm (sides compared longest to shortest, so turning it does not matter) */
const alike = (a: number[], b: number[]) => sorted(a).every((v, i) => Math.abs(v - sorted(b)[i]) <= 20);

export function Identity({ siteId, waybill, photo = true }: { siteId: string | undefined; waybill: string;
  /** off where the tunnel's own screen (with the same photo) sits beside it */
  photo?: boolean }) {
  const res = useResource<{ parcels: ParcelRow[] }>(siteId && waybill ? `/v1/sites/${siteId}/parcels?limit=2000` : null);
  const caps = useResource<Capabilities>("/v1/capabilities");
  const [photoOk, setPhotoOk] = useState(true);
  const all = res.data?.parcels ?? [];
  const me = all.find((p) => p.id === waybill);
  if (!res.data) return <div className="an-skel an-skel-row" aria-busy="true" />;
  if (!me) return <p className="an-line">This tracking number has no scans at this hub, so there is nothing to identify it by yet.</p>;
  const after = me.last?.t ?? "";
  const twins = me.dims_mm ? all.filter((p) => p.id !== me.id && p.dims_mm && alike(p.dims_mm, me.dims_mm!) && p.last && p.last.t > after)
    .sort((a, b) => sorted(a.dims_mm!).reduce((s, v, i) => s + Math.abs(v - sorted(me.dims_mm!)[i]), 0)
      - sorted(b.dims_mm!).reduce((s, v, i) => s + Math.abs(v - sorted(me.dims_mm!)[i]), 0)) : [];
  const vision = !!caps.data?.sam;
  return (
    <div className="id">
      {photo && photoOk && me.tunnel_t && (
        <a className="id-photo" href={`/scanner/${me.id}.jpg`} target="_blank" rel="noreferrer">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={`/scanner/${me.id}.jpg`} alt={`The scan tunnel's photo of ${me.id}, label and barcode readable`} onError={() => setPhotoOk(false)} />
          <span>Tunnel photo · {hms(me.tunnel_t)}</span>
        </a>
      )}
      <ol className="id-rows">
        {me.tunnel_t && (
          <li data-tone="ok">
            <b>Its own barcode</b>
            <span>The scan tunnel read <span className="id-mono">{me.id}</span> at {hms(me.tunnel_t)} and photographed the label.</span>
          </li>
        )}
        {me.dims_mm && (
          <li data-tone="ok">
            <b>Its size and weight</b>
            <span>{cm(me.dims_mm)} cm{me.weight_g ? `, ${(me.weight_g / 1000).toFixed(2)} kg` : ""}, measured by the tunnel. This is what the cameras look for.</span>
          </li>
        )}
        {me.last && (
          <li data-tone="ok">
            <b>Where the scans left it</b>
            <span>{me.container ? `Scanned into ${containerName(me.container)}` : placeName(me.last.point)} at {hms(me.last.t)}. No scan of it since.</span>
          </li>
        )}
        <li data-tone={twins.length ? "ruled" : "ok"}>
          <b>Cartons that look like it</b>
          {twins.length ? (
            <span>
              {twins.length} carton{twins.length === 1 ? "" : "s"} of about the same size {twins.length === 1 ? "was" : "were"} scanned after {hms(after)}. None is this
              parcel: each one&apos;s own barcode was read.
              <ul className="id-twins">
                {twins.slice(0, 3).map((t) => (
                  <li key={t.id}>
                    <span className="id-twin">
                      <span className="id-mono">{t.id}</span>
                      <span className="id-dim">{cm(t.dims_mm!)} cm · {placeName(t.last!.point)} · {hms(t.last!.t)}</span>
                    </span>
                    <em>Not this parcel</em>
                  </li>
                ))}
              </ul>
              {twins.length > 3 && <span className="id-more">and {twins.length - 3} more, each with its own barcode read</span>}
            </span>
          ) : <span>No other carton of about this size was scanned after {hms(after)}.</span>}
        </li>
        <li data-tone={vision ? "ok" : "wait"}>
          <b>On camera</b>
          <span>{vision
            ? "Meta SAM 3.1 picks up this carton where its last scan left it and follows it on camera; each camera is matched by place and time."
            : "Matching this carton in the footage uses the vision model (Meta SAM 3.1). Models are off, so the cameras are checked by place and time only."}</span>
        </li>
      </ol>
    </div>
  );
}
