"use client";
/**
 * "The case, in five moments": the S2 moments as an evidence timeline, all five in view (no sideways scrolling).
 * A time rail runs above them: each moment's clock time on it, the gap to the next written between ("+3 s"), all
 * from the footage's own clock. The rail draws itself as the section comes into view and the moments rise in, 60 ms
 * apart. Frames show their first still; only the one under the pointer (or focused) plays (Rexgent's rule: one video
 * decoding at a time, never while the tab is hidden). A click opens the clip in a lightbox (Esc, the backdrop or the
 * close button shut it; focus returns). Phones: the same timeline, vertical, rail on the left.
 */
import { useEffect, useRef, useState } from "react";
import { prefersReducedMotion } from "@/lib/motion";
import { useReveal } from "@/lib/useReveal";
import type { Story, StoryStep } from "./story";

const cam = (c: string) => c.replace("_", " ");
const secs = (hms: string) => {
  const [h, m, s] = hms.split(":").map(Number);
  return h * 3600 + m * 60 + s;
};

function Frame({ m, active }: { m: StoryStep; active: boolean }) {
  const ref = useRef<HTMLVideoElement>(null);
  useEffect(() => {
    const v = ref.current;
    if (!v) return;
    if (active && !document.hidden) {
      v.currentTime = 0;
      v.play().catch(() => {});
    } else v.pause();
  }, [active]);
  return (
    <span className={`lp-mo-frame${active ? " is-playing" : ""}`}>
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={m.poster} alt="" loading="lazy" decoding="async" width={1280} height={720} />
      {active && <video ref={ref} src={m.video} muted loop playsInline preload="auto" aria-hidden="true" />}
      <span className="lp-mo-cam">{cam(m.camera)}</span>
      <span className="lp-mo-play" aria-hidden="true">
        <svg viewBox="0 0 24 24"><path d="M8 5.5v13l11-6.5z" fill="currentColor" /></svg>
      </span>
    </span>
  );
}

export function Showreel({ story }: { story: Story | null }) {
  const ref = useRef<HTMLElement>(null);
  useReveal(ref);
  const [hover, setHover] = useState<number | null>(null);
  const [open, setOpen] = useState<StoryStep | null>(null);
  const [closing, setClosing] = useState(false);
  const opener = useRef<HTMLButtonElement | null>(null);
  const closeBtn = useRef<HTMLButtonElement>(null);
  const reduced = typeof window !== "undefined" && prefersReducedMotion();

  const close = () => {
    setClosing(true);
    window.setTimeout(() => {
      setOpen(null);
      setClosing(false);
      opener.current?.focus();
    }, reduced ? 0 : 140);
  };
  useEffect(() => {
    if (!open) return;
    closeBtn.current?.focus();
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && close();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  const moments = story?.moments ?? [];
  const times = moments.map((m) => m.caption.split(" · ")[0]);
  return (
    <section className="lp-section" id="case" ref={ref} aria-labelledby="lp-case-title">
      <div className="lp-wrap">
        <h2 id="lp-case-title" className="lp-section-title" data-reveal="fade">The case, in five moments</h2>
        <p className="lp-section-lede" data-reveal="fade" style={{ "--d": 120 } as React.CSSProperties}>
          {story?.parcel ? `Parcel ${story.parcel}, as the hub's own cameras saw it.` : "One parcel, as the hub's own cameras saw it."}
        </p>
        <ol className="lp-mo" data-reveal="rail">
          {moments.map((m, i) => {
            const [time, ...rest] = m.caption.split(" · ");
            const gap = i < moments.length - 1 ? secs(times[i + 1]) - secs(time) : null;
            return (
              <li key={`${m.camera}-${i}`} className="lp-mo-item" style={{ "--i": i } as React.CSSProperties}>
                <div className="lp-mo-rail" aria-hidden="true">
                  <span className="lp-mo-dot" />
                  <span className="lp-mo-time">{time}</span>
                  {gap !== null && gap > 0 && <span className="lp-mo-gap">+{gap} s</span>}
                </div>
                <button
                  type="button"
                  className="lp-mo-btn"
                  onPointerEnter={(e) => e.pointerType === "mouse" && !reduced && setHover(i)}
                  onPointerLeave={() => setHover((h) => (h === i ? null : h))}
                  onFocus={() => !reduced && setHover(i)}
                  onBlur={() => setHover((h) => (h === i ? null : h))}
                  onClick={(e) => {
                    opener.current = e.currentTarget;
                    setHover(null);
                    setOpen(m);
                  }}
                  aria-label={`Play ${cam(m.camera)}, ${m.caption}`}
                >
                  <Frame m={m} active={hover === i && !open} />
                </button>
                <p className="lp-mo-cap">
                  <span className="lp-mo-n">{String(i + 1).padStart(2, "0")}</span>
                  {rest.join(" · ") || cam(m.camera)}
                </p>
              </li>
            );
          })}
        </ol>
      </div>
      {open && (
        <div className={`lp-lightbox${closing ? " is-closing" : ""}`} role="dialog" aria-modal="true" aria-label={`${cam(open.camera)}, ${open.caption}`} onClick={close}>
          <button ref={closeBtn} type="button" className="lp-lightbox-close" aria-label="Close" onClick={close}>
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <path d="M6 6l12 12M18 6 6 18" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
            </svg>
          </button>
          <figure className="lp-lightbox-body" onClick={(e) => e.stopPropagation()}>
            <video src={open.video} poster={open.poster} autoPlay={!reduced} muted controls loop playsInline />
            <figcaption>
              <b>{cam(open.camera)}</b> {open.caption}
            </figcaption>
          </figure>
        </div>
      )}
    </section>
  );
}
