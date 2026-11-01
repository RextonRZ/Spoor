"use client";
/**
 * The landing page at "/" (before the app). Structure and motion system after Reelism's landing (mask-line headline,
 * data-reveal, pointer-follow highlight on the primary button, grain, skip link); video
 * handling and the showreel + lightbox after Rexgent's. Spoor's own palette, copy and data. No em dashes in copy.
 */
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { prefersReducedMotion } from "@/lib/motion";
import { useReveal } from "@/lib/useReveal";
import { CctvWallHero } from "./CctvWallHero";
import { Showreel } from "./Showreel";
import { loadStory, type Story } from "./story";
import { Investigation } from "./Investigation";
import { Tracking } from "./Tracking";
import "./landing.css";

/** Primary buttons carry a highlight that follows the pointer inside them (fine pointers only, see the CSS). */
function usePointerHighlight() {
  useEffect(() => {
    const onMove = (e: PointerEvent) => {
      const btn = (e.target as Element | null)?.closest?.(".lp-btn-primary") as HTMLElement | null;
      if (!btn) return;
      const r = btn.getBoundingClientRect();
      btn.style.setProperty("--mx", `${e.clientX - r.left}px`);
      btn.style.setProperty("--my", `${e.clientY - r.top}px`);
    };
    document.addEventListener("pointermove", onMove, { passive: true });
    return () => document.removeEventListener("pointermove", onMove);
  }, []);
}

function Arrow() {
  return (
    <svg className="lp-btn-arrow" viewBox="0 0 16 16" aria-hidden="true">
      <path d="M3 8h9.5M8.5 3.5 13 8l-4.5 4.5" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

const SECTIONS = [
  { id: "how", label: "How it works" },
  { id: "case", label: "The case" },
  { id: "trust", label: "Trust" },
];

/** Transparent over the hero, a translucent bar once the page moves; the section in view is marked. */
function Header() {
  const [scrolled, setScrolled] = useState(false);
  const [current, setCurrent] = useState<string | null>(null);
  useEffect(() => {
    const els = SECTIONS.map((s) => document.getElementById(s.id)).filter(Boolean) as HTMLElement[];
    // the section whose top has passed 45% of the screen (none while the hero fills it)
    const onScroll = () => {
      setScrolled(window.scrollY > 8);
      const line = window.innerHeight * 0.45;
      let id: string | null = null;
      for (const el of els) if (el.getBoundingClientRect().top <= line && el.getBoundingClientRect().bottom > 0) id = el.id;
      setCurrent(id);
    };
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll);
    return () => {
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", onScroll);
    };
  }, []);
  return (
    <header className={`lp-header${scrolled ? " is-scrolled" : ""}`}>
      <div className="lp-wrap lp-header-row">
        <Link href="/" className="lp-brand" aria-label="Spoor home">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src="/brand/spoor-logo-dark.png" alt="Spoor" width={93} height={30} />
        </Link>
        <nav className="lp-nav" aria-label="Page sections">
          {SECTIONS.map((s) => (
            <a key={s.id} href={`#${s.id}`} aria-current={current === s.id ? "true" : undefined}>{s.label}</a>
          ))}
        </nav>
        <Link href="/hub" className="lp-btn lp-btn-primary lp-btn-sm lp-header-cta">
          Open the demo hub
          <Arrow />
        </Link>
      </div>
    </header>
  );
}

function Hero({ story }: { story: Story | null }) {
  const ref = useRef<HTMLElement>(null);
  useReveal(ref);
  return (
    <section className="lp-hero" ref={ref} aria-labelledby="lp-hero-title">
      <div className="lp-wrap lp-hero-grid">
        <div className="lp-hero-copy">
          <h1 id="lp-hero-title" className="lp-hero-title" data-reveal="mask">
            <span className="lp-mask-line" style={{ "--i": 0 } as React.CSSProperties}>
              <span>Every parcel</span>
            </span>
            <span className="lp-mask-line lp-mask-line--deep" style={{ "--i": 1 } as React.CSSProperties}>
              <span>
                leaves a trail.
              </span>
            </span>
          </h1>
          <p className="lp-hero-lede" data-reveal="fade" style={{ "--d": 420 } as React.CSSProperties}>
            Spoor reads your hub&apos;s CCTV and scan records, finds where a missing parcel went, and hands you the clip that
            proves it.
          </p>
          <div className="lp-hero-ctas" data-reveal="fade" style={{ "--d": 560 } as React.CSSProperties}>
            <Link className="lp-btn lp-btn-primary" href="/hub">
              Open the demo hub
              <Arrow />
            </Link>
            <a className="lp-text-link" href="#case">Watch the case</a>
          </div>
        </div>
        <div className="lp-hero-visual">
          {story ? <CctvWallHero story={story} /> : <div className="lp-spot-area lp-spot-wait" aria-hidden="true" />}
        </div>
      </div>
    </section>
  );
}

/** One real crop per rule, from the S2 render itself (CCTV frames and the hub model), with the page's own caption chip.
 *  No drawn icons: each picture is the rule as it looks in the footage. */
const SHOTS = {
  people: { src: "/landing/gate_parcel.jpg", chip: "CAM 13 · only the parcel gets a box", tone: "green" },
  synthetic: { src: "/landing/gate_synthetic.jpg", chip: "CAM 07", tag: "Synthetic", tone: "plain" },
  hub: { src: "/landing/gate_hub.jpg", chip: "Same hub as the videos", tone: "plain" },
  floor: { src: "/landing/gate_floor.jpg", chip: "Go look: exception store", tone: "accent" },
} as const;

function GateShot({ kind }: { kind: keyof typeof SHOTS }) {
  const s = SHOTS[kind];
  return (
    <span className={`lp-gate-shot is-${s.tone}`}>
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={s.src} alt="" loading="lazy" decoding="async" width={480} height={320} />
      <span className="lp-gate-chip">{s.chip}</span>
      {"tag" in s && <span className="lp-gate-tag">{s.tag}</span>}
    </span>
  );
}

const GATES = [
  { art: "people", title: "Tracks parcels, not people", body: "It follows boxes and bags. It never looks at faces, and staff IDs stay hidden." },
  { art: "synthetic", title: "Made-up hub, clearly marked", body: "We built this hub in 3D and filmed it ourselves, because real hub CCTV is private. Every video is marked \"SYNTHETIC\"." },
  { art: "hub", title: "See the whole hub in 3D", body: "Every camera, belt and chute in one view, so you can see the parcel's path." },
  { art: "floor", title: "A person checks before it's closed", body: "Spoor sends a staff member to the spot on their phone. They look, then report what they found." },
] as const;

function Gates() {
  const ref = useRef<HTMLElement>(null);
  useReveal(ref);
  return (
    <section className="lp-section" ref={ref} aria-labelledby="lp-gates-title" id="trust">
      <div className="lp-wrap lp-gates">
        <div className="lp-gates-intro">
          <h2 id="lp-gates-title" className="lp-section-title" data-reveal="fade">Built to be trusted</h2>
          <p className="lp-section-lede" data-reveal="fade" style={{ "--d": 120 } as React.CSSProperties}>
            Four promises, and you can check each one.
          </p>
        </div>
        <ul className="lp-gate-list">
          {GATES.map((g, i) => (
            <li key={g.title} className="lp-gate" data-reveal="gate" style={{ "--i": i } as React.CSSProperties}>
              <GateShot kind={g.art} />
              <div>
                <h3>{g.title}</h3>
                <p>{g.body}</p>
              </div>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}

/** The closing: the call to action over the hub's own 3D model, an angled view of the working floor (a Blender render of
 *  the S2 scene, frame 300 of run 7, picked for its clean poses). The picture drifts very slowly (transform only,
 *  ease-in-out because it reverses), only while the section is on screen and never under reduced motion. */
function Closing() {
  const ref = useRef<HTMLElement>(null);
  const img = useRef<HTMLImageElement>(null);
  useReveal(ref);
  useEffect(() => {
    const el = img.current;
    const sec = ref.current;
    if (!el || !sec || prefersReducedMotion()) return;
    const drift = el.animate(
      [{ transform: "scale(1.06) translate3d(1.2%, 0.6%, 0)" }, { transform: "scale(1.14) translate3d(-1.8%, -1%, 0)" }],
      { duration: 38000, direction: "alternate", iterations: Infinity, easing: "cubic-bezier(0.77, 0, 0.175, 1)", fill: "both" },
    );
    drift.pause();
    const io = new IntersectionObserver(([e]) => (e.isIntersecting && !document.hidden ? drift.play() : drift.pause()), { threshold: 0.05 });
    io.observe(sec);
    const vis = () => (document.hidden ? drift.pause() : sec.getBoundingClientRect().top < window.innerHeight && drift.play());
    document.addEventListener("visibilitychange", vis);
    return () => {
      io.disconnect();
      document.removeEventListener("visibilitychange", vis);
      drift.cancel();
    };
  }, []);
  return (
    <section className="lp-section lp-closing" ref={ref} aria-labelledby="lp-close-title">
      <div className="lp-close-bg" aria-hidden="true" data-reveal="fade">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          ref={img}
          src="/landing/hub-backdrop.jpg"
          srcSet="/landing/hub-backdrop-sm.jpg 1200w, /landing/hub-backdrop.jpg 2400w"
          sizes="100vw"
          alt=""
          loading="lazy"
          decoding="async"
          width={2400}
          height={1350}
        />
        <span className="lp-close-scrim" />
        <span className="lp-close-tag">Demo hub, built in Blender</span>
      </div>
      <div className="lp-wrap lp-close-body">
        <h2 id="lp-close-title" className="lp-section-title lp-close-title" data-reveal="words" aria-label="Lost parcels, found with proof.">
          {"Lost parcels, found with proof.".split(" ").map((w, i) => (
            <span key={i} className="lp-w" aria-hidden="true" style={{ "--i": i } as React.CSSProperties}>
              <span>{w}</span>
            </span>
          ))}
        </h2>
        <div className="lp-close-cta" data-reveal="fade" style={{ "--d": 520 } as React.CSSProperties}>
          <Link className="lp-cta" href="/hub">
            <span>Follow the parcel</span>
            <span className="lp-cta-go" aria-hidden="true"><Arrow /></span>
          </Link>
          <p>No sign-in. A fictional hub, rendered in Blender.</p>
        </div>
      </div>
    </section>
  );
}

export function Landing() {
  usePointerHighlight();
  const [story, setStory] = useState<Story | null>(null);
  useEffect(() => {
    let live = true;
    loadStory().then((s) => live && setStory(s)).catch(() => {});
    return () => {
      live = false;
    };
  }, []);
  return (
    <div className="lp">
      <a className="lp-skip" href="#main">Skip to content</a>
      <Header />
      <main id="main">
        <Hero story={story} />
        <Tracking story={story} />
        <Investigation story={story} />
        <Showreel story={story} />
        <Gates />
        <Closing />
      </main>
      <footer className="lp-footer">
        <div className="lp-wrap">
          Built with Meta Muse, SAM 3.1 and Llama open weights · Demo footage made in Blender · © 2026 Spoor
        </div>
      </footer>
      <div className="lp-grain" aria-hidden="true" />
    </div>
  );
}
