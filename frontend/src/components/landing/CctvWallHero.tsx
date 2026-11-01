"use client";
/**
 * Hero: every camera of the hub as a slow, faded 3D wall behind the copy, one feed at a time in front of it, and the
 * case worked out on a whiteboard at the end. One timeline (anime.js schedules, WAAPI moves):
 *  1. the wall drifts; the case's scan record is the opening line;
 *  2. a scan sweeps across the wall: feeds that saw the parcel (ground truth) light green, the rest dim "no match";
 *  3. the spotlight rises in front once, then cuts from camera to camera in time order like a monitor switching
 *     feeds (no flying out of the wall: from a dim, tilted slot it read as a glitch). Each feed: the clip, a soft
 *     spotlight on the parcel that follows it (the hands carrying it light up too), a green box on the PARCEL only
 *     (never a person), the case's caption; its card in the wall glows while it is on;
 *  4. the doorway step adds a 2x crop inset and the case's records-vs-cameras line;
 *  5. the detective board: the route sketched in marker over a 3D top-down plan, with notes. Loop.
 * Motion: drift linear, the cut a strong ease-in-out (520 ms), things entering ease-out; transform and opacity only.
 * Pauses with the button, a hidden tab, or the hero off screen. Reduced motion: the still wall with the finished board.
 */
import { useEffect, useMemo, useRef, useState, useSyncExternalStore } from "react";
import { createTimeline, type Timeline } from "animejs";
import { EASE_IN_OUT_CSS, EASE_OUT_CSS, prefersReducedMotion } from "@/lib/motion";
import { BOARD_MS, DetectiveBoard, boardTimeline } from "./DetectiveBoard";
import { clockAt, type Story, type StoryStep } from "./story";

const camIds = Array.from({ length: 19 }, (_, i) => `CAM_${String(i + 1).padStart(2, "0")}`);
const label = (cam: string) => cam.replace("_", " ");
const COLS = 5;
const RISE = 460;
const CUT = 520;
const SWEEP = 2000;
const BOARD = BOARD_MS + 1600; // the sketching, then a moment to read the verdict

function columns() {
  return Array.from({ length: COLS }, (_, k) => {
    const own = camIds.filter((_, i) => i % COLS === k);
    const rest = camIds.filter((_, i) => i % COLS !== k).slice(k * 2, k * 2 + 3);
    return [...own, ...rest];
  });
}

const MOBILE_Q = "(max-width: 760px)";
const onMobileChange = (cb: () => void) => {
  const mq = window.matchMedia(MOBILE_Q);
  mq.addEventListener("change", cb);
  return () => mq.removeEventListener("change", cb);
};
/** null on the server (unknown until the page is in a browser) */
export function useMobile() {
  return useSyncExternalStore<boolean | null>(onMobileChange, () => window.matchMedia(MOBILE_Q).matches, () => null);
}

/** One camera's feed in the spotlight: the clip, the parcel box, and a soft light on the parcel that follows it. */
export function mountFeed(host: HTMLElement, step: StoryStep, fps: number, paused: () => boolean) {
  const el = document.createElement("div");
  el.className = "lp-view";
  el.style.backgroundImage = `url(${step.poster})`;
  const v = document.createElement("video");
  v.className = "lp-clip";
  v.muted = true;
  v.playsInline = true;
  v.preload = "auto";
  v.poster = step.poster;
  v.src = step.video;
  v.setAttribute("aria-hidden", "true");
  const light = document.createElement("div");
  light.className = "lp-light";
  const box = document.createElement("div");
  box.className = "lp-box";
  el.append(v, light, box);
  host.appendChild(el);
  const frames = Object.keys(step.boxes).map(Number).sort((a, b) => a - b);
  let cx = -1;
  let cy = -1;
  let cr = -1;
  let raf = 0;
  const draw = () => {
    const f = step.clip_f[0] + Math.floor(v.currentTime * fps + 1e-3);
    const near = step.boxes[f] ? f : frames.find((k) => Math.abs(k - f) <= 1);
    const b = near !== undefined ? step.boxes[near] : undefined;
    if (b !== undefined) {
      box.style.left = `${b[0] * 100}%`;
      box.style.top = `${b[1] * 100}%`;
      box.style.width = `${(b[2] - b[0]) * 100}%`;
      box.style.height = `${(b[3] - b[1]) * 100}%`;
      box.classList.add("is-on");
      const tx = ((b[0] + b[2]) / 2) * 100;
      const ty = ((b[1] + b[3]) / 2) * 100;
      // the light's size follows the parcel's size on screen: a small, far-off person gets a small, tight light
      const W = el.clientWidth || 640;
      const H = el.clientHeight || 360;
      const tr = Math.max((b[2] - b[0]) * W, (b[3] - b[1]) * H) * 1.6 + 10;
      cx = cx < 0 ? tx : cx + (tx - cx) * 0.25; // eased, so the light glides with the parcel instead of jittering
      cy = cy < 0 ? ty : cy + (ty - cy) * 0.25;
      cr = cr < 0 ? tr : cr + (tr - cr) * 0.2;
      light.style.background = `radial-gradient(circle at ${cx}% ${cy}%, rgba(0,0,0,0) ${cr.toFixed(1)}px, rgba(4,5,7,0.62) ${(cr * 2.6).toFixed(1)}px)`;
      light.classList.add("is-on");
    } else box.classList.remove("is-on");
    raf = requestAnimationFrame(draw);
  };
  if (!paused()) v.play().catch(() => {});
  raf = requestAnimationFrame(draw);
  return {
    el,
    video: v,
    stop() {
      cancelAnimationFrame(raf);
      v.pause();
      v.removeAttribute("src");
      v.load();
    },
  };
}

export function CctvWallHero({ story }: { story: Story }) {
  const mobile = useMobile();
  const reduced = typeof window !== "undefined" && prefersReducedMotion();
  const rootRef = useRef<HTMLDivElement>(null);
  const planeRef = useRef<HTMLDivElement>(null);
  const spotRef = useRef<HTMLDivElement>(null);
  const viewsRef = useRef<HTMLDivElement>(null);
  const insetRef = useRef<HTMLDivElement>(null);
  const boardWrapRef = useRef<HTMLDivElement>(null);
  const boardRef = useRef<SVGSVGElement>(null);
  const [paused, setPaused] = useState(false);
  const pausedRef = useRef(false);
  const apply = useRef<() => void>(() => {});
  const [stepIdx, setStepIdx] = useState(-1);
  const [chip, setChip] = useState<{ cam: string; clock: string; caption: string } | null>(null);
  const [phase, setPhase] = useState<"open" | "sweep" | "step" | "red" | "board">("open");
  const [clock, setClock] = useState(() => clockAt(story.data, story.data.poster_frame));
  const cols = useMemo(() => columns(), []);
  const { data, steps } = story;

  useEffect(() => {
    if (reduced) return;
    let f = data.poster_frame;
    const id = window.setInterval(() => {
      if (pausedRef.current || document.hidden) return;
      f = f + data.fps > data.frames[1] ? data.poster_frame : f + data.fps;
      setClock(clockAt(data, f));
    }, 1000);
    return () => window.clearInterval(id);
  }, [data, reduced]);

  useEffect(() => {
    if (mobile === null || reduced) return;
    const root = rootRef.current!;
    const plane = planeRef.current!;
    const spot = spotRef.current!;
    const views = viewsRef.current!;
    const inset = insetRef.current!;
    const boardWrap = boardWrapRef.current!;
    const cards = Array.from(plane.querySelectorAll<HTMLElement>(".lp-feed-card"));
    let disposed = false;
    let visible = true;
    let feed: ReturnType<typeof mountFeed> | null = null;
    let insetVideo: HTMLVideoElement | null = null;
    let board: Timeline | null = null;
    const timers: number[] = [];
    const later = (fn: () => void, ms: number) => timers.push(window.setTimeout(() => !disposed && fn(), ms));
    const isPaused = () => pausedRef.current || !visible || document.hidden;

    const drift = Array.from(plane.querySelectorAll<HTMLElement>(".lp-feed-col")).map((col, k) =>
      col.animate([{ transform: "translateY(0)" }, { transform: "translateY(-50%)" }], {
        duration: 46000 + k * 5200,
        iterations: Infinity,
        direction: k % 2 ? "reverse" : "normal",
        easing: "linear",
      }),
    );
    let rate = 1;
    let rateRaf = 0;
    const setRate = (to: number, ms: number) => {
      const from = rate;
      const t0 = performance.now();
      cancelAnimationFrame(rateRaf);
      const tick = (now: number) => {
        const u = Math.min(1, (now - t0) / ms);
        rate = from + (to - from) * (1 - Math.pow(1 - u, 3));
        drift.forEach((a) => (a.playbackRate = Math.max(0.0001, rate)));
        if (u < 1) rateRaf = requestAnimationFrame(tick);
      };
      rateRaf = requestAnimationFrame(tick);
    };
    const moves: Animation[] = [];
    const move = (el: Element, frames: Keyframe[], ms: number, easing: string) => {
      const a = el.animate(frames, { duration: ms, easing, fill: "forwards" });
      moves.push(a);
      a.finished.then(() => moves.splice(moves.indexOf(a), 1)).catch(() => {});
      if (isPaused()) a.pause();
      return a;
    };
    const live = (cam: string | null) => cards.forEach((c) => c.classList.toggle("is-live", c.dataset.cam === cam));

    const clearInset = () => {
      if (insetVideo) {
        insetVideo.pause();
        insetVideo.remove();
        insetVideo = null;
      }
      inset.classList.remove("is-on");
    };
    /** cut to this step's camera: the old feed slides out left, the new one in from the right */
    const showStep = (s: StoryStep, i: number, first: boolean) => {
      setStepIdx(i);
      setChip(null);
      clearInset();
      live(s.camera);
      const old = feed;
      const next = mountFeed(views, s, data.fps, isPaused);
      feed = next;
      if (first) {
        move(spot, [{ opacity: 0, transform: "translateY(12px) scale(0.97)" }, { opacity: 1, transform: "none" }], RISE, EASE_OUT_CSS);
      } else {
        move(next.el, [{ opacity: 0, transform: "translateX(7%)" }, { opacity: 1, transform: "none" }], CUT, EASE_IN_OUT_CSS);
      }
      if (old) {
        move(old.el, [{ opacity: 1, transform: "none" }, { opacity: 0, transform: "translateX(-7%)" }], CUT, EASE_IN_OUT_CSS);
        later(() => {
          old.stop();
          old.el.remove();
        }, CUT);
      }
      later(() => {
        setChip({ cam: s.camera, clock: clockAt(data, s.clip_f[0]), caption: s.caption });
        if (s.inset) {
          const v = document.createElement("video");
          v.muted = true;
          v.playsInline = true;
          v.src = s.inset.video;
          v.setAttribute("aria-hidden", "true");
          inset.querySelector(".lp-inset-media")!.appendChild(v);
          insetVideo = v;
          if (!isPaused()) v.play().catch(() => {});
          inset.classList.add("is-on");
        }
      }, first ? RISE : CUT);
    };
    const endSpot = () => {
      clearInset();
      setChip(null);
      live(null);
      move(spot, [{ opacity: 1, transform: "none" }, { opacity: 0, transform: "scale(0.98)" }], 320, EASE_OUT_CSS);
      const f = feed;
      feed = null;
      later(() => {
        f?.stop();
        f?.el.remove();
      }, 330);
    };

    const sweep = plane.querySelector<HTMLElement>(".lp-feed-sweep")!;
    const tl: Timeline = createTimeline({ loop: true, autoplay: false });
    let t = 0;
    tl.call(() => {
      setStepIdx(-1);
      setChip(null);
      setPhase("open");
      cards.forEach((c) => c.classList.remove("is-match", "is-miss", "is-live"));
      spot.style.opacity = "0";
      boardWrap.style.opacity = "0";
      setRate(1, 600);
    }, t);
    t += 2000;
    tl.call(() => {
      setPhase("sweep");
      move(sweep, [{ transform: "translateX(0%)", opacity: 0 }, { opacity: 1, offset: 0.08 }, { opacity: 1, offset: 0.9 },
        { transform: "translateX(100%)", opacity: 0 }], SWEEP, "linear");
    }, t);
    for (let c = 0; c < COLS; c++) {
      tl.call(() => {
        plane.querySelectorAll<HTMLElement>(`.lp-feed-col:nth-child(${c + 1}) .lp-feed-card`).forEach((el) =>
          el.classList.add(story.seen.has(el.dataset.cam!) ? "is-match" : "is-miss"));
      }, t + ((c + 0.6) / COLS) * SWEEP);
    }
    t += SWEEP;
    steps.forEach((s, i) => {
      const hold = ((s.clip_f[1] - s.clip_f[0] + 1) / data.fps) * 1000;
      tl.call(() => {
        setPhase(s.event === "into_blind" ? "red" : "step");
        if (i === 0) setRate(0.12, 600);
        showStep(s, i, i === 0);
      }, t);
      t += (i === 0 ? RISE : CUT) + hold;
    });
    tl.call(() => endSpot(), t);
    t += 340;
    tl.call(() => {
      setPhase("board");
      setStepIdx(steps.length);
      move(boardWrap, [{ opacity: 0, transform: "translateY(14px) scale(0.97)" }, { opacity: 1, transform: "none" }], 560, EASE_OUT_CSS);
      if (boardRef.current) {
        board = boardTimeline(boardRef.current);
        if (!isPaused()) board.play();
      }
    }, t);
    t += BOARD;
    tl.call(() => {
      move(boardWrap, [{ opacity: 1 }, { opacity: 0 }], 300, EASE_OUT_CSS);
    }, t);
    t += 320;
    tl.call(() => {
      board?.revert();
      board = null;
    }, t);

    const io = new IntersectionObserver(([e]) => {
      visible = e.isIntersecting;
      apply.current();
    }, { threshold: 0.1 });
    io.observe(root);
    apply.current = () => {
      if (disposed) return;
      const stop = isPaused();
      root.classList.toggle("is-paused", stop);
      const all = [...drift, ...moves];
      if (stop) {
        tl.pause();
        board?.pause();
        all.forEach((a) => a.pause());
        feed?.video.pause();
        insetVideo?.pause();
      } else {
        tl.play();
        board?.play();
        all.forEach((a) => a.play());
        feed?.video.play().catch(() => {});
        insetVideo?.play().catch(() => {});
      }
    };
    const onVis = () => apply.current();
    document.addEventListener("visibilitychange", onVis);
    apply.current();
    return () => {
      disposed = true;
      io.disconnect();
      document.removeEventListener("visibilitychange", onVis);
      cancelAnimationFrame(rateRaf);
      timers.forEach((id) => window.clearTimeout(id));
      clearInset();
      feed?.stop();
      feed?.el.remove();
      board?.revert();
      tl.revert();
      drift.forEach((a) => a.cancel());
      moves.forEach((a) => a.cancel());
    };
    // built once per layout
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mobile, reduced, story]);

  const toggle = () => {
    pausedRef.current = !pausedRef.current;
    setPaused(pausedRef.current);
    apply.current();
  };

  return (
    <div ref={rootRef} className={`lp-feed-hero${reduced ? " is-static" : ""}`} data-phase={phase}>
      <div className="lp-feed" aria-hidden="true">
        <div ref={planeRef} className="lp-feed-plane">
          {cols.map((col, k) => (
            <div key={k} className="lp-feed-col">
              {[...col, ...col].map((c, i) => (
                <div key={`${c}-${i}`} className="lp-feed-card" data-cam={c}>
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img src={`/landing/posters/${c}.jpg`} alt="" decoding="async" width={640} height={360} />
                  <span className="lp-feed-osd">
                    <b>{label(c)}</b>
                    <span>{clock}</span>
                  </span>
                  <span className="lp-feed-miss">no match</span>
                </div>
              ))}
            </div>
          ))}
          <div className="lp-feed-sweep" />
        </div>
      </div>

      <div className="lp-spot-zone">
        {story.opener && (phase === "open" || phase === "sweep") && !reduced && (
          <p className="lp-topline" aria-hidden="true">{story.opener}</p>
        )}
        <div className="lp-spot-area">
          <div ref={spotRef} className="lp-spot" aria-hidden="true">
            <div ref={viewsRef} className="lp-views" />
            {chip && (
              <div className="lp-osd">
                <b>{label(chip.cam)}</b>
                <span>{chip.clock}</span>
              </div>
            )}
            <div ref={insetRef} className="lp-inset">
              <div className="lp-inset-media" />
              <span>2x crop</span>
            </div>
          </div>
          <div ref={boardWrapRef} className="lp-board" style={reduced ? undefined : { opacity: 0 }}>
            <DetectiveBoard story={story} boardRef={boardRef} />
          </div>
        </div>
        <div className="lp-lines" aria-hidden="true">
          {chip && <p key={chip.caption} className="lp-line lp-line-step">{chip.caption}</p>}
          {story.redLine && (phase === "red" || reduced) && <p className="lp-line lp-line-red">{story.redLine}</p>}
        </div>
        <div className="lp-spot-foot">
          {mobile && !reduced ? (
            <ol className="lp-dots" aria-label="Steps">
              {steps.map((s, i) => (
                <li key={s.camera + i} className={i === stepIdx ? "is-on" : i < stepIdx ? "is-done" : ""}>
                  <span className="sr-only">{label(s.camera)}</span>
                </li>
              ))}
            </ol>
          ) : (
            <span />
          )}
          <span className="lp-synth">Demo footage</span>
          {!reduced && (
            <button
              type="button"
              className="lp-play"
              aria-pressed={paused}
              aria-label={paused ? "Play the camera wall" : "Pause the camera wall"}
              onClick={toggle}
            >
              {paused ? (
                <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M8 5.5v13l11-6.5z" fill="currentColor" /></svg>
              ) : (
                <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 5h3.5v14H7zM13.5 5H17v14h-3.5z" fill="currentColor" /></svg>
              )}
            </button>
          )}
        </div>
      </div>
      <p className="sr-only">
        {story.opener} The cameras that saw parcel {story.parcel}, in time order:{" "}
        {steps.map((s) => `${label(s.camera)}, ${s.caption}`).join("; ")}. {story.redLine}
      </p>
    </div>
  );
}
