"use client";
/**
 * "How a hub tracks a parcel": the six scan checkpoints of the story parcel from the case's own scan log (lib/checkpoints,
 * the same strip the case Answer shows), with the time between scans written on the rail. Under it, the point of the
 * section: what the cameras saw in the long silence between the cage scan and the truck record (the case's moments).
 * Then the scan tunnel's screen for this parcel and the look-alike check (the tunnel's record next to the camera's
 * candidate). Nothing typed by hand: times, sizes, chute, cage and truck come from the case; the moments and the
 * look-alike from the render. Before the case loads, the six places show as a quiet outline with no times.
 *
 * Motion: the rail draws in time order and each scan lands on it; the gaps between scans appear once their stretch is
 * drawn; the camera moments then rise in one by one; in the look-alike card the camera crop wipes in and the "not the
 * same" mark settles last. Ease-out for everything that enters, nothing loops. Reduced motion: plain fades.
 */
import { useRef } from "react";
import { useReveal } from "@/lib/useReveal";
import { buildCheckpoints, CHECKPOINT_LINE } from "@/lib/checkpoints";
import { CheckpointStrip, ScannerScreen } from "@/components/checkpoints/Checkpoints";
import { hms } from "@/lib/words";
import type { Story } from "./story";

const cam = (c: string) => c.replace("_", " ");
const OUTLINE = buildCheckpoints({ scans: [] });

/** the look-alike's frame, cropped round its box (5x the box, at least a fifth of the frame), as a 4:3 window */
function Crop({ src, box }: { src: string; box: [number, number, number, number] }) {
  const w = Math.max((box[2] - box[0]) * 5, 0.2);
  const h = Math.min(w * (16 / 9) * (3 / 4), 1);
  const cx = (box[0] + box[2]) / 2;
  const cy = (box[1] + box[3]) / 2;
  const x0 = Math.min(Math.max(cx - w / 2, 0), 1 - w);
  const y0 = Math.min(Math.max(cy - h / 2, 0), 1 - h);
  return (
    <span className="lp-tr-crop">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={src} alt="" loading="lazy" decoding="async"
        style={{ width: `${100 / w}%`, height: `${100 / h}%`, left: `${(-x0 / w) * 100}%`, top: `${(-y0 / h) * 100}%` }} />
      <span className="lp-tr-cbox" style={{
        left: `${((box[0] - x0) / w) * 100}%`, top: `${((box[1] - y0) / h) * 100}%`,
        width: `${((box[2] - box[0]) / w) * 100}%`, height: `${((box[3] - box[1]) / h) * 100}%`,
      }} />
    </span>
  );
}

export function Tracking({ story }: { story: Story | null }) {
  const ref = useRef<HTMLElement>(null);
  useReveal(ref, story);
  const cps = story?.checkpoints ?? null;
  const tunnel = cps?.find((c) => c.id === "tunnel");
  const box = cps?.find((c) => c.id === "container");
  const truck = cps?.find((c) => c.id === "truck");
  const l = story?.lookalike;
  // the silence: from the last scan that put it somewhere (the cage) to the truck record, what the cameras saw
  const from = box?.t ? hms(box.t) : null;
  const to = truck?.t ? hms(truck.t) : null;
  const saw = from
    ? (story?.moments ?? []).map((m) => ({ m, time: m.caption.split(" · ")[0], words: m.caption.split(" · ").slice(1).join(" · ") }))
        .filter((x) => x.time > from && (!to || x.time < to))
    : [];
  const sc = tunnel?.screen;
  return (
    <section className="lp-section lp-tr" id="scans" ref={ref} aria-labelledby="lp-tr-title">
      <div className="lp-wrap">
        <h2 id="lp-tr-title" className="lp-section-title" data-reveal="fade">How a hub tracks a parcel</h2>
        <p className="lp-section-lede" data-reveal="fade" style={{ "--d": 120 } as React.CSSProperties}>
          Six scans, from the truck coming in to the truck going out.
          {story?.parcel ? ` This is what they recorded for parcel ${story.parcel}.` : ""}
        </p>

        <div className="lp-tr-stage">
          <div className="lp-tr-strip ck-anim" data-reveal="ck">
            <CheckpointStrip cps={cps ?? OUTLINE} gaps pending={!cps} />
          </div>
          {!cps && <p className="lp-tr-wait">Waiting for the case&apos;s scan log.</p>}

          <div className="lp-tr-between">
            <p className="lp-tr-line" data-reveal="fade" style={{ "--d": 300 } as React.CSSProperties}>{CHECKPOINT_LINE}</p>
            {saw.length > 0 && (
              <div className="lp-tr-saw" data-reveal="saw">
                <p className="lp-tr-saw-h">
                  Between the cage scan at {from}{to ? ` and the truck record at ${to}` : ""}, the cameras saw:
                </p>
                <ol>
                  {saw.map(({ m, time, words }, i) => (
                    <li key={`${m.camera}-${time}`} style={{ "--i": i } as React.CSSProperties}>
                      <span className="lp-tr-saw-t">{time}</span>
                      <span className="lp-tr-saw-c">{cam(m.camera)}</span>
                      <span className="lp-tr-saw-w">{words}</span>
                    </li>
                  ))}
                  {truck?.state === "conflict" && to && (
                    <li className="is-bad" style={{ "--i": saw.length } as React.CSSProperties}>
                      <span className="lp-tr-saw-t">{to}</span>
                      <span className="lp-tr-saw-c">Records</span>
                      <span className="lp-tr-saw-w">say it left on truck {truck.detail?.replace(/^Truck /, "")}. No camera saw it there.</span>
                    </li>
                  )}
                </ol>
              </div>
            )}
          </div>
        </div>

        {/* the two cards need the case's tunnel record: they wait for it together, never one alone */}
        {sc && <div className="lp-tr-grid">
          {sc && (
            <article className="lp-tr-card" data-reveal="gate" style={{ "--i": 0 } as React.CSSProperties}>
              <h3>At the scan tunnel</h3>
              <p>Every parcel is photographed, weighed and measured, then sent to a chute.</p>
              <ScannerScreen s={sc} at={tunnel?.t ?? null} />
            </article>
          )}
          {l && sc && (
            <article className="lp-tr-card lp-tr-cmp" data-reveal="cmp" style={{ "--i": 1 } as React.CSSProperties}>
              <h3>Is it the same parcel?</h3>
              <p>A camera finds a carton that looks right. Spoor checks it against the tunnel&apos;s record first.</p>
              <div className="lp-tr-pair">
                <figure className="lp-tr-rec">
                  <span className="lp-tr-rec-body">
                    <span className="lp-tr-rec-k">Tunnel record</span>
                    <span className="lp-tr-rec-big">{sc.length_cm} × {sc.width_cm} × {sc.height_cm} cm</span>
                    <span className="lp-tr-rec-v">{sc.weight_kg?.toFixed(2)} kg · label {sc.barcode ?? "not read"}</span>
                    <span className="lp-tr-rec-note">The tunnel&apos;s photo arrives with the next footage.</span>
                  </span>
                  <figcaption>At the tunnel{tunnel?.t ? ` · ${hms(tunnel.t)}` : ""}</figcaption>
                </figure>
                <span className="lp-tr-ne" role="img" aria-label="not the same">
                  <svg viewBox="0 0 16 16" aria-hidden="true"><path d="M3.5 6h9M3.5 10h9M10.5 3 5.5 13" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" /></svg>
                </span>
                <figure className="lp-tr-cand">
                  <Crop src={l.poster} box={l.box} />
                  <figcaption>On {cam(l.camera)} · {l.clock}</figcaption>
                </figure>
              </div>
              <p className="lp-tr-verdict"><span aria-hidden="true" />Not this parcel. At {l.clock} the real one was {l.realWas}.</p>
            </article>
          )}
        </div>}
      </div>
    </section>
  );
}
