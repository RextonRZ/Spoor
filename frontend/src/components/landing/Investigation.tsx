"use client";
/**
 * "How Spoor investigates": the four steps as a pinned scroll showcase. The section is a tall track; inside it a
 * stage stays on screen while the page scrolls, and each quarter of the track hands over to the next step: the big
 * number rolls up to the next one, the words follow, and the next step's picture wipes up over the last (scrolling
 * back runs it in reverse). Four tabs show where you are and jump to a step.
 *
 * Every picture is the case's own material, never a mock-up of the app: the lead's camera plan (the hub's 19 camera
 * posters, the ones the case expects to see the parcel next marked), the first camera's clip with the parcel's box
 * (Blender ground truth), the look-alike the verifier rejects, and the answer with its proof clip.
 *
 * Phones and narrow windows: no pinning, the steps simply stack, each with its picture. Reduced motion: the steps
 * still change as you scroll, by a short crossfade only.
 */
import { useEffect, useRef, useState } from "react";
import { prefersReducedMotion } from "@/lib/motion";
import { useReveal } from "@/lib/useReveal";
import { mountFeed } from "./CctvWallHero";
import type { Story } from "./story";

const STEPS = [
  {
    n: "01",
    tab: "Plan",
    title: "A lead plans the search",
    body: "It reads the scan records, sees where the parcel was last scanned and which cameras could have seen it next.",
  },
  {
    n: "02",
    tab: "Check",
    title: "Analysts check the cameras",
    body: "Each one opens real footage at the right minute, with real tools: frame search, tracking, the hub's floor plan.",
  },
  {
    n: "03",
    tab: "Verify",
    title: "A verifier says no",
    body: "A look-alike carton is easy to take for the parcel. The verifier checks it against the parcel's own trail, rejects it, and the lead plans again.",
  },
  {
    n: "04",
    tab: "Answer",
    title: "You get the answer with proof",
    body: "Where it went, the clip that shows it, and what to check on the floor. Every claim links to its evidence.",
  },
];

const cam = (c: string) => c.replace("_", " ");
const boxStyle = (b: [number, number, number, number]) => ({
  left: `${b[0] * 100}%`,
  top: `${b[1] * 100}%`,
  width: `${(b[2] - b[0]) * 100}%`,
  height: `${(b[3] - b[1]) * 100}%`,
});

function PlanPanel({ story }: { story: Story | null }) {
  const cams = story?.data.cameras.map((c) => c.id) ?? [];
  const next = new Set(story?.nextCams ?? []);
  return (
    <div className="lp-show-card lp-show-plan">
      <div className="lp-show-plan-head">
        <span className="lp-show-label">Scan records</span>
        <p>{story?.lastScan ? story.lastScan.words : story?.opener ?? "The parcel's scans at this hub."}</p>
        <span className="lp-show-plan-sub">
          {next.size ? `${next.size} of ${cams.length} cameras could see it next` : `${cams.length || 19} wide cameras on the floor plan`}
        </span>
      </div>
      <ul className="lp-show-cams">
        {cams.map((c, i) => (
          <li key={c} className={next.has(c) ? "is-next" : ""} style={{ "--i": i } as React.CSSProperties}>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={`/landing/posters/${c}.jpg`} alt="" loading="lazy" decoding="async" width={320} height={180} />
            <span>{cam(c)}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function CheckPanel({ story, on }: { story: Story | null; on: boolean }) {
  const host = useRef<HTMLDivElement>(null);
  const step = story?.steps[0];
  useEffect(() => {
    if (!on || !step || !story || !host.current) return;
    const reduced = prefersReducedMotion();
    const feed = mountFeed(host.current, step, story.data.fps, () => reduced || document.hidden);
    feed.video.loop = true;
    // one video decoding at a time, never while the tab is hidden
    const vis = () => (document.hidden ? feed.video.pause() : !reduced && feed.video.play().catch(() => {}));
    document.addEventListener("visibilitychange", vis);
    return () => {
      document.removeEventListener("visibilitychange", vis);
      feed.stop();
      feed.el.remove();
    };
  }, [on, step, story]);
  const [time, ...words] = step?.caption.split(" · ") ?? [];
  return (
    <div className="lp-show-card lp-show-media">
      <div className="lp-show-feed" ref={host} style={step ? { backgroundImage: `url(${step.poster})` } : undefined} />
      {step && (
        <div className="lp-show-chip">
          <b>{cam(step.camera)}</b>
          <span>{time}</span>
          {words.length > 0 && <span className="lp-show-chip-w">{words.join(" · ")}</span>}
        </div>
      )}
    </div>
  );
}

function VerifyPanel({ story }: { story: Story | null }) {
  const l = story?.lookalike;
  if (!l) return <div className="lp-show-card lp-show-empty">The look-alike appears once the footage loads.</div>;
  return (
    <div className="lp-show-card lp-show-media">
      <div className="lp-show-feed" style={{ backgroundImage: `url(${l.poster})` }}>
        <span className="lp-show-lbox" style={boxStyle(l.box)} />
      </div>
      <span className="lp-show-stamp">Rejected</span>
      <div className="lp-show-chip">
        <b>{cam(l.camera)}</b>
        <span>{l.clock}</span>
        <span className="lp-show-chip-w">a look-alike. The real one was {l.realWas}.</span>
      </div>
    </div>
  );
}

function AnswerPanel({ story }: { story: Story | null }) {
  const v = story?.verdict;
  const proof = story?.steps.find((s) => s.event === "into_blind") ?? story?.steps[story.steps.length - 1];
  if (!v) return <div className="lp-show-card lp-show-empty">The answer appears once the case loads.</div>;
  return (
    <div className="lp-show-card lp-show-answer">
      <span className={`lp-show-pill is-${v.pill[1]}`}>{v.source === "agent" ? `Spoor's answer · ${v.pill[0]}` : v.pill[0]}</span>
      <p className="lp-show-head">{v.head}</p>
      <ul className="lp-show-why">
        {v.reasons.map((r, k) => (
          <li key={k} className={`is-${r.tone}`} style={{ "--i": k } as React.CSSProperties}>{r.text}</li>
        ))}
      </ul>
      {proof && (
        <figure className="lp-show-proof">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={proof.poster} alt="" loading="lazy" decoding="async" width={1280} height={720} />
          <figcaption>
            <span className="lp-show-label">Proof</span> {cam(proof.camera)} · {proof.caption}
          </figcaption>
        </figure>
      )}
    </div>
  );
}

export function Investigation({ story }: { story: Story | null }) {
  const ref = useRef<HTMLElement>(null);
  const track = useRef<HTMLDivElement>(null);
  const fills = useRef<(HTMLSpanElement | null)[]>([]);
  const [active, setActive] = useState(0);
  useReveal(ref);

  useEffect(() => {
    const el = track.current;
    if (!el) return;
    const n = STEPS.length;
    let raf = 0;
    const update = () => {
      raf = 0;
      const r = el.getBoundingClientRect();
      const total = Math.max(1, r.height - window.innerHeight);
      const p = Math.min(1, Math.max(0, -r.top / total));
      fills.current.forEach((f, i) => f && (f.style.transform = `scaleX(${Math.min(1, Math.max(0, p * n - i))})`));
      setActive(Math.min(n - 1, Math.floor(p * n)));
    };
    const onScroll = () => {
      if (!raf) raf = requestAnimationFrame(update);
    };
    update();
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll);
    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", onScroll);
    };
  }, []);

  // a tab jumps to the start of its step
  const go = (i: number) => {
    const el = track.current;
    if (!el) return;
    const top = el.getBoundingClientRect().top + window.scrollY;
    const total = el.offsetHeight - window.innerHeight;
    window.scrollTo({ top: top + (total * i) / STEPS.length + 2, behavior: prefersReducedMotion() ? "auto" : "smooth" });
  };

  // step 03's sentence comes from the footage: where the real parcel was when the look-alike was on camera
  const l = story?.lookalike;
  const body = (i: number) =>
    i === 2 && l
      ? `A look-alike carton showed up on ${cam(l.camera)} while the real one was ${l.realWas}. The verifier rejects it and the lead plans again.`
      : STEPS[i].body;
  const pos = (i: number) => (i === active ? "on" : i < active ? "before" : "after");
  const panels = [
    <PlanPanel key="plan" story={story} />,
    <CheckPanel key="check" story={story} on={active === 1} />,
    <VerifyPanel key="verify" story={story} />,
    <AnswerPanel key="answer" story={story} />,
  ];
  return (
    <section className="lp-section lp-show" id="how" ref={ref} aria-labelledby="lp-pipe-title">
      <div className="lp-show-track" ref={track} style={{ "--n": STEPS.length } as React.CSSProperties}>
        <div className="lp-show-sticky">
          <div className="lp-wrap lp-show-grid">
            <header className="lp-show-intro">
              <h2 id="lp-pipe-title" className="lp-section-title" data-reveal="fade">How Spoor investigates</h2>
              <p className="lp-section-lede" data-reveal="fade" style={{ "--d": 120 } as React.CSSProperties}>
                A small crew of agents does what a supervisor would do with an afternoon and nineteen camera feeds.
              </p>
              <div className="lp-show-tabs" data-reveal="fade" style={{ "--d": 200 } as React.CSSProperties}>
                {STEPS.map((s, i) => (
                  <button key={s.n} type="button" className="lp-show-tab" aria-current={i === active ? "step" : undefined} onClick={() => go(i)}>
                    <span className="lp-show-tab-bar"><span ref={(e) => { fills.current[i] = e; }} /></span>
                    <span className="lp-show-tab-n">{s.n}</span> {s.tab}
                  </button>
                ))}
              </div>
            </header>
            <ol className="lp-show-list">
              {STEPS.map((s, i) => (
                <li key={s.n} className="lp-show-item" data-pos={pos(i)}>
                  <div className="lp-show-text">
                    <span className="lp-show-num" aria-hidden="true"><span>{s.n}</span></span>
                    <h3>{s.title}</h3>
                    <p>{body(i)}</p>
                  </div>
                  <div className="lp-show-panel">{panels[i]}</div>
                </li>
              ))}
            </ol>
          </div>
        </div>
      </div>
    </section>
  );
}
