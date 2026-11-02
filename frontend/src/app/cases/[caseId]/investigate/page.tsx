"use client";
/**
 * Investigating, ported from review/refs/flow/Investigate.dc.html (owner 09:22; agent_showcase_0925). Every node, chip,
 * log line and meter value comes from the run's typed steps (POST /v1/cases/{id}/run, streamed; GET replays the last
 * run). Model steps that are not configured say so in the log; nothing here is scripted.
 * Rexton, 3 Nov: show which agent did what and where. "Who did what" is one lane per agent with a dot per step in the
 * order they ran (a thin line passes the baton between them), under a numbered summary whose numbers sit above the dots; "Where they looked" letters every place the steps
 * touched on the plan. Picking a step lights its places; picking a place picks its first step.
 */
import Link from "next/link";
import { use, useCallback, useEffect, useRef, useState } from "react";
import { API_BASE, api, invalidate, signedUrl, useResource } from "@/lib/api";
import { HUB, camId } from "@/lib/hub";
import type { Journey, XY } from "@/lib/journey";
import type { Chapter, Reel } from "@/components/case/JourneyReel";
import "./investigate.css";

interface Node { key: string; column: string; name: string; place: string; state: string; label: string }
interface Step { type: "run_step"; seq: number; t_s: number; clock?: string; role: string; who: string; model: string; tool: string; status: string;
  text: string; node: Node | null; camera_id: string | null; cost_usd: number; cameras_checked: number;
  receipt?: { output?: { cameras?: number } } | null }
interface End { type: "run_end"; t_s: number; cost_usd: number; cameras_checked: number; text: string; headline?: string | null; swept?: number }
type Ev = Step | End | { type: "node"; node: Node };
interface RunView { steps: (Step | Ev)[]; crew: { role: string; who: string; model: string; tools: string[] }[]; optional_tools: string[];
  columns: Record<string, string> }
interface CaseState { case: { case_id: string; target_description: string } }

const TAG: Record<string, string> = { read_scans: "Scan records", triage_clips: "Triage on site", plan: "Planning", pick_cameras: "Planning",
  re_plan: "Re-planning", sam_track: "Tracking the box", verify: "Verified", reject: "Rejected", create_search_task: "Search task",
  ask_a_person: "Asking a person", draft_report: "Report", scan_history: "Reading the scans", footage_for: "Finding footage",
  door_crossings: "Watching the door", carrier_check: "Who carried it", propose: "Ideas", verify_claim: "Testing an idea" };
/** what each tool did, in plain verbs (the tool ids stay in the receipts, not on screen) */
const TOOL_WORDS: Record<string, string> = { read_scans: "Read the scans", plan: "Planned the search", pick_cameras: "Picked cameras",
  re_plan: "Re-planned", triage_clips: "Triaged the footage", scan_history: "Read the scan history", footage_for: "Found the footage",
  door_crossings: "Checked the door", carrier_check: "Checked who carried it", observe_clip: "Watched a clip",
  sam_track: "Tracked with SAM 3.1", propose: "Proposed ideas", verify_claim: "Tested ideas", verify: "Verified", reject: "Rejected",
  create_search_task: "Set a search task", ask_a_person: "Asked a person", draft_report: "Drafted the report" };
const secs = (t: number) => (t < 10 ? t.toFixed(1) : String(Math.round(t)));

/** the run's own elapsed time (+m:ss), so it is never read as the hub clock of the footage */
const runTime = (t: number) => `+${Math.floor(t / 60)}:${String(Math.floor(t % 60)).padStart(2, "0")}`;

const CLOSE: Record<string, string> = { UNLOAD: "Unload", TUNNEL: "Tunnel", CAGE_W: "Cage", CAGE_E: "Cage", STORE: "Store door", DOCK: "Dock", CHUTE: "Chute" };

interface Beat { key: string; q: string; text: string; model: string; seq: number }
const first = (t: string) => t.split(/(?<=\.)\s/)[0].replace(/\.$/, "");
const unparen = (t: string) => t.replace(/\s*\([^)]*\)/g, "").replace(/\.$/, "");

/** The run as a short storyline for a supervisor: one plain line per stage, each from the run's own steps (their
 *  words and receipts), in the order they happened; a stage appears once its first step has. The full log stays below. */
function storyline(steps: Step[], crew: RunView["crew"]): Beat[] {
  const model = (role: string) => crew.find((c) => c.role === role)?.model.replace(/\s*·.*$/, "") ?? "";
  const done = (tool: string) => steps.filter((s) => s.tool === tool && s.status === "done");
  const out: Beat[] = [];
  const add = (key: string, s: Step | undefined, q: string, text: string, role = s?.role ?? "") => { if (s && text) out.push({ key, q, text, model: model(role), seq: s.seq }); };
  // a detective's questions, each answered from the run's own steps and receipts (Rexton 3 Nov: a judge must follow it)
  const cap = (t: string) => t.charAt(0).toUpperCase() + t.slice(1);
  const read = done("read_scans")[0];
  const rm = read?.text.match(/^Read (\d+) scans\. Last: (.+?) at (\d\d:\d\d)/);
  add("read", read, "Last scan?", rm ? `${cap(rm[2])} at ${rm[3]}` : read ? unparen(read.text) : "");
  const tri = done("triage_clips")[0];
  const share = (tri?.receipt?.output as { sent_share?: number } | undefined)?.sent_share;
  add("triage", tri, "Which footage?", share != null ? `Only the ${Math.round(share * 100)}% where parcels are being handled` : tri ? first(tri.text) : "");
  const plan = done("plan")[0], pick = done("pick_cameras")[0];
  const cams = pick?.text.match(/:\s*(.+?)\.?$/)?.[1].replace(/CHK (\w+)/g, (_, k: string) => `the ${(CLOSE[k] ?? k).toLowerCase()} camera`)
    .replace(/, ([^,]+)$/, " and $1");
  add("plan", pick ?? plan, "Where to look?", cams ?? (plan ? first(plan.text) : ""));
  // what the cameras showed: the verifier's own finding (in at, not seen out), else the door count
  const found = steps.find((s) => s.role === "verifier" && s.text.startsWith("Verified"));
  const fm = found?.text.match(/carried in at (\d\d:\d\d)(?::\d\d)?, not seen coming out/);
  const door = done("door_crossings").at(-1)?.text.match(/^(.+?)(?: \(Z\d+\))?: (.+?) at its door/);
  const where = found?.text.match(/door of the (.+?)(?: \(Z\d+\))? at/)?.[1] ?? door?.[1];
  // (placed at the tracking that saw it, so the story reads cameras first; the words are the verifier's finding)
  if (fm) add("seen", done("sam_track").at(-1) ?? found, "What did the cameras show?", `Carried into the ${where} at ${fm[1]}, not seen coming out`);
  else add("seen", done("sam_track")[0], "What did the cameras show?", door ? `${cap(door[2])} at the ${door[1]} door` : "", "tracker");
  const ideas = done("propose");
  const tests = steps.filter((s) => s.role === "verifier" && s.seq > (ideas[0]?.seq ?? Infinity) && /^(Passed|Unproven|Rejected)/.test(s.text));
  const held = tests.filter((s) => s.text.startsWith("Passed")).map((s) => s.text.match(/\(tested: ([^)]*)\)/)?.[1]).filter(Boolean);
  add("ideas", tests[0], "Any other explanation?", tests.length ? `Tested ${tests.length}; ${held.length ? `only “it ${held[0]}” held` : "none held"}` : "", "verifier");
  const ask = done("ask_a_person")[0] ?? done("create_search_task")[0];
  const am = ask?.text.match(/^No camera sees inside (?:the )?(.+?)(?: \(Z\d+\))?, so a person is asked to look/);
  add("ask", ask, "What now?", am ? `No camera inside the ${am[1]}: a person goes to look` : ask ? unparen(ask.text) : "");
  return out.sort((x, y) => x.seq - y.seq);
}

export default function InvestigatePage({ params }: { params: Promise<{ caseId: string }> }) {
  const { caseId } = use(params);
  const state = useResource<CaseState>(`/v1/cases/${caseId}/state`);
  const stored = useResource<RunView>(`/v1/cases/${caseId}/run`);
  const jr = useResource<Journey>(`/v1/cases/${caseId}/journey`);
  const reel = useResource<Reel>(`/v1/cases/${caseId}/journey-reel`);
  const [hoverPlace, setHoverPlace] = useState<string | null>(null);
  const [picked, setPicked] = useState<number | null>(null); // a step picked in "Who did what" (or by its place)
  const [peek, setPeek] = useState<number | null>(null); // a step under the pointer
  const [events, setEvents] = useState<Ev[]>([]);
  const [shown, setShown] = useState(0); // how many events are revealed (live: all; replay: stepping)
  const [live, setLive] = useState(false);
  const started = useRef(false);
  const [failed, setFailed] = useState<string | null>(null);
  const replayRef = useRef<(evs: Ev[]) => void>(() => {});
  const timer = useRef<number | null>(null);

  const start = useCallback(async () => {
    setEvents([]);
    setShown(0);
    setLive(true);
    let job_id: string;
    try {
      ({ job_id } = await api<{ job_id: string }>(`/v1/cases/${caseId}/run`, { method: "POST" }));
    } catch (e) {
      setLive(false);
      setFailed(e instanceof Error ? e.message : String(e));
      return;
    }
    let got = 0;
    const es = new EventSource(`${API_BASE}/v1/jobs/${job_id}/events`);
    // when the stream ends, or drops before any step arrived, read the stored run and replay it (never stay blank)
    const finish = async () => {
      es.close();
      setLive(false);
      if (got > 0) { invalidate(`/v1/cases/${caseId}/run`); return; }
      const run = await api<RunView>(`/v1/cases/${caseId}/run`).catch(() => null);
      if (run?.steps.length) replayRef.current(run.steps as Ev[]);
    };
    es.onmessage = (m) => {
      const ev = JSON.parse(m.data) as Ev & { message?: string };
      if (ev.type !== "run_step" && ev.type !== "run_end" && ev.type !== "node") return;
      got += 1;
      setEvents((xs) => { const next = [...xs, ev]; setShown(next.length); return next; });
    };
    es.addEventListener("end", () => void finish());
    es.onerror = () => void finish();
  }, [caseId]);

  // first visit: the last run if there is one (replayed), otherwise start a run now. The replay's timer belongs to
  // this effect (StrictMode runs effects twice in development: the cleanup must not leave a dead timer behind).
  useEffect(() => {
    if (!stored.data || started.current) return;
    started.current = true;
    // eslint-disable-next-line react-hooks/set-state-in-effect -- the one-time kickoff: no stored run yet, start one
    if (!stored.data.steps.length) { void start(); return; }
    replay(stored.data.steps as Ev[], true);
    return () => { if (timer.current) window.clearInterval(timer.current); started.current = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- once, when the stored run is known
  }, [stored.data]);

  useEffect(() => { replayRef.current = replay; });
  function replay(evs: Ev[], whole = false) {
    if (timer.current) window.clearInterval(timer.current);
    const end: End | null = evs.some((e) => e.type === "run_end") ? null : (() => {
      const last = [...evs].reverse().find((e) => e.type === "run_step") as Step | undefined;
      return last ? { type: "run_end", t_s: last.t_s, cost_usd: last.cost_usd, cameras_checked: last.cameras_checked,
        text: `Took ${last.t_s} s and US$${last.cost_usd.toFixed(2)}. 19 wide cameras on site, ${last.cameras_checked} examined closely.` } : null;
    })();
    const all = end ? [...evs, end] : evs;
    setEvents(all);
    if (whole) { setShown(all.length); return; }
    setShown(0);
    let i = 0;
    timer.current = window.setInterval(() => {
      i += 1;
      setShown(i);
      if (i >= all.length && timer.current) window.clearInterval(timer.current);
    }, 650);
  }

  const crew = stored.data?.crew ?? [];
  const vis = events.slice(0, shown);
  const steps = vis.filter((e): e is Step => e.type === "run_step");
  const end = vis.find((e): e is End => e.type === "run_end");
  const cur = steps.at(-1);
  // Glimmer's on-site sweep looks at every camera; the agents then examine a few closely
  const swept = end?.swept ?? steps.find((s) => s.tool === "triage_clips" && s.status === "done")?.receipt?.output?.cameras ?? 0;
  const done = !!end;
  const story = storyline(steps, stored.data?.crew ?? []);
  const seen = steps.filter((s) => s.node?.state === "seen" && s.tool !== "read_scans").length;
  const lastScanStep = steps.find((s) => s.tool === "read_scans");
  const title = !done ? "Investigating…" : end?.headline ? end.headline : seen > 0 ? "Found where it went." : `Lost track after ${lastScanStep?.node?.place.replace("scan ", "").slice(0, 5) ?? "the last scan"}.`;
  const waybill = state.data?.case.target_description.split(" ").at(-1) ?? "";

  // ---- where: every place the crew worked, numbered in the order they first touched it (from the steps themselves)
  const lastXy = jr.data?.objects[0]?.scans.filter((s) => s.xy).at(-1)?.xy ?? null;
  const zoneTag = [end?.headline ?? "", ...steps.map((s) => s.text)].join(" ").match(/\((Z\d+)\)/)?.[1] ?? null;
  const zone = zoneTag ? HUB.zones.find((z) => z.id === zoneTag) : undefined;
  const zoneXy: XY | null = zone?.polygons[0]?.length
    ? [zone.polygons[0].reduce((a, p) => a + p[0], 0) / zone.polygons[0].length, zone.polygons[0].reduce((a, p) => a + p[1], 0) / zone.polygons[0].length] : null;
  const zoneName = zone ? `${zone.name} (${zone.id})` : "";
  const placesOf = (s: Step): string[] => {
    if (s.tool === "read_scans" || s.tool === "scan_history") return lastXy ? ["last"] : [];
    if (s.tool === "pick_cameras" || s.tool === "plan") return ((s.receipt?.output as { cameras?: string[] } | undefined)?.cameras ?? []).map((c) => `cam:${camId.toHub(c)}`);
    const out = s.camera_id ? [`cam:${camId.toHub(s.camera_id)}`] : s.node?.key.startsWith("cam_") ? [`cam:${camId.toHub(s.node.key)}`] : [];
    if (zoneXy && (s.role === "reporter" || (s.role === "verifier" && s.text.startsWith("Verified")))) out.push("zone");
    return out;
  };
  const places: Place[] = [];
  const addPlace = (key: string) => {
    if (places.some((p) => p.key === key)) return;
    if (key === "last" && lastXy) places.push({ key, xy: lastXy, label: `Last scan: ${(lastScanStep?.node?.name ?? "scan point").toLowerCase()}`, tone: "scan" });
    else if (key === "zone" && zoneXy) places.push({ key, xy: zoneXy, label: zoneName, tone: "bad" });
    else if (key.startsWith("cam:")) {
      const c = HUB.cameras.find((x) => x.id === key.slice(4));
      if (c) places.push({ key, xy: [c.position_m[0], c.position_m[1]], label: camWords(c.id), tone: "seen" });
    }
  };
  steps.forEach((s) => placesOf(s).forEach(addPlace));
  const nOf = (key: string) => String.fromCharCode(65 + places.findIndex((p) => p.key === key));
  const chapters = reel.data?.chapters ?? [];
  const frameOf = (key: string): Chapter | undefined => key === "last" ? chapters.find((c) => c.last_scan)
    : key === "zone" ? chapters.find((c) => c.tone === "seen" && c.camera === "CHK_STORE") ?? chapters.find((c) => c.tone === "noscan")
    : key === "cam:CHK_STORE" ? chapters.find((c) => c.tone === "noscan" && c.camera === "CHK_STORE") ?? chapters.find((c) => c.camera === "CHK_STORE")
    : chapters.find((c) => c.camera === key.slice(4));
  const hm = (iso: string) => new Date(iso).toLocaleTimeString("en-GB", { timeZone: "Asia/Kuala_Lumpur", hour12: false });

  // the step being looked at: the one picked, else the one hovered, else the one running now
  const focus = steps.find((s) => s.seq === (peek ?? picked)) ?? (!done ? cur : undefined) ?? null;
  const focusPlaces = focus ? placesOf(focus) : [];
  const pickPlace = (key: string) => { const s = steps.find((x) => placesOf(x).includes(key)); if (s) setPicked(s.seq); };

  const ideas = steps.flatMap((s, i) => {
    if (s.tool !== "propose") return [];
    const v = steps.slice(i + 1).find((x) => x.role === "verifier");
    const quote = s.text.match(/“([^”]+)”/)?.[1] ?? s.text.replace(/^Idea:\s*/, "");
    const passed = !!v && /^Passed/.test(v.text);
    const inner = v?.text.match(/\(([^)]*)\)/)?.[1];
    const tested = !!inner?.startsWith("tested: "), why = inner?.replace(/^tested: /, "");
    return [{ seq: s.seq, quote, passed, tested, verdict: v ? (passed ? "Passed" : /^Rejected/.test(v.text) ? "Rejected" : "Not proven") : "Waiting", why }];
  });
  const beatAt = new Map(story.map((b, i) => [b.seq, i + 1]));

  // ---- who did what: one lane per agent, one dot per step in the order they ran, a thin line passing the baton
  const lanes = crew.filter((c) => steps.some((s) => s.role === c.role) || !done);
  const laneOf = (role: string) => lanes.findIndex((c) => c.role === role);
  const N = Math.max(steps.length, 1);
  const x = (i: number) => ((i + 0.5) / N) * 100;
  const LANE = 34;
  const pts = steps.map((s, i) => [x(i), laneOf(s.role) * LANE + LANE / 2] as const);
  const baton = pts.map(([px, py], i) => {
    if (i === 0) return `M${px},${py}`;
    const [qx, qy] = pts[i - 1], m = (qx + px) / 2;
    return `C${m},${qy} ${m},${py} ${px},${py}`;
  }).join(" ");

  return (
    <div className="iv">
      <div className="iv-head">
        <div>
          <p className="iv-crumb"><Link href="/hub">Hub</Link> <span aria-hidden="true">›</span> {waybill}</p>
          <h1 className="iv-title">{title}</h1>
        </div>
        <div aria-label="Live meter" className="iv-meter">
          <span title={end?.text}><strong>US${(end?.cost_usd ?? cur?.cost_usd ?? 0).toFixed(2)}</strong> <span>spent</span></span>
          {swept > 0 && <span><strong>{swept}</strong> <span>wide cameras swept</span></span>}
          <span><strong>{end?.cameras_checked ?? cur?.cameras_checked ?? 0}</strong> <span>{swept > 0 ? "examined closely" : "of 19 wide cameras examined"}</span></span>
          <span><strong>{secs(end?.t_s ?? cur?.t_s ?? 0)} s</strong></span>
          <button type="button" onClick={() => { setPicked(null); if (events.length && !live) replay(events); }} disabled={live || !events.length}>Replay</button>
        </div>
      </div>

      <div className="iv-main">
        <section className="iv-left">
          <div className="iv-card iv-log">
            <h2>In short</h2>
            {story.length > 0 ? (
              <ol className="iv-story" aria-label="The run in short">
                {story.map((b, i) => {
                  const st = steps.find((x) => x.seq === b.seq);
                  return (
                    <li key={b.key} className="iv-story-row" data-now={!done && i === story.length - 1 ? "" : undefined}>
                      <button type="button" className="iv-story-btn" onClick={() => setPicked(b.seq)} aria-pressed={focus?.seq === b.seq}>
                        <span className="iv-story-n">{i + 1}</span>
                        <span className="iv-story-q">{b.q}</span>
                        <span className="iv-story-text">{b.text}</span>
                        <span className="iv-story-meta">
                          {st && <span className="iv-chip" data-fam={fam(st.model)}>{st.who}</span>}
                        </span>
                      </button>
                    </li>
                  );
                })}
              </ol>
            ) : <p className="iv-log-wait" role={failed ? "alert" : undefined}>{failed ? `The run could not start: ${failed}` : stored.loading ? "Loading the last run" : "Starting the crew"}</p>}
          </div>

          <div className="iv-card iv-relay-card">
            <div className="iv-card-head">
              <h2>Every step, by agent</h2>
              <span>Pick a dot</span>
            </div>
            {steps.length > 0 ? (
              <div className="iv-relay" onMouseLeave={() => setPeek(null)}>
                <ul className="iv-lanes-who" aria-hidden="true" style={{ paddingTop: 22 }}>
                  {lanes.map((c) => (
                    <li key={c.role} style={{ height: LANE }} data-fam={fam(c.model)} data-active={!done && cur?.role === c.role ? "" : undefined}>
                      <span className="iv-who">{c.who}</span>
                      <span className="iv-model">{c.model.replace(/\s*·.*$/, "")}</span>
                    </li>
                  ))}
                </ul>
                <div className="iv-lanes-scroll">
                  <div className="iv-lanes" style={{ height: lanes.length * LANE, minWidth: N * 22, marginTop: 22 }}>
                    {lanes.map((c, r) => <span key={c.role} className="iv-lane-line" style={{ top: r * LANE + LANE / 2 }} />)}
                    <svg className="iv-baton" viewBox={`0 0 100 ${lanes.length * LANE}`} preserveAspectRatio="none" aria-hidden="true">
                      <path d={baton} fill="none" vectorEffect="non-scaling-stroke" />
                    </svg>
                    {steps.map((s, i) => beatAt.has(s.seq) && (
                      <span key={`b${s.seq}`} className="iv-beat" style={{ left: `${x(i)}%` }} aria-hidden="true">{beatAt.get(s.seq)}</span>
                    ))}
                    <ol className="iv-dots" aria-label="Every step, in order">
                      {steps.map((s, i) => {
                        const hollow = s.status !== "done" || /^(Unproven|Rejected)/.test(s.text);
                        const lane = crew.find((c) => c.role === s.role);
                        return (
                          <li key={s.seq} style={{ left: `${x(i)}%`, top: laneOf(s.role) * LANE + LANE / 2 }}>
                            <button type="button" className="iv-dot" data-fam={fam(s.model)} data-hollow={hollow ? "" : undefined}
                              data-on={focus?.seq === s.seq ? "" : undefined} aria-pressed={picked === s.seq}
                              data-dim={hoverPlace && !placesOf(s).includes(hoverPlace) ? "" : undefined}
                              aria-label={`Step ${i + 1}, ${runTime(s.t_s)}, ${lane?.who ?? s.who}: ${s.text}`}
                              onMouseEnter={() => setPeek(s.seq)} onFocus={() => setPeek(s.seq)} onBlur={() => setPeek(null)}
                              onClick={() => setPicked((p) => (p === s.seq ? null : s.seq))} />
                          </li>
                        );
                      })}
                    </ol>
                  </div>
                </div>
              </div>
            ) : null}

            {focus && (
              <div className="iv-focus" data-fam={fam(focus.model)} aria-live="polite" data-pic={focusPlaces[0] && frameOf(focusPlaces[0])?.thumb_url ? "" : undefined}>
                {focusPlaces[0] && frameOf(focusPlaces[0])?.thumb_url && (
                  // eslint-disable-next-line @next/next/no-img-element -- a signed frame of the journey video, from the API
                  <img className="iv-focus-pic" src={signedUrl(frameOf(focusPlaces[0])!.thumb_url!)} alt="" />
                )}
                <div className="iv-focus-top">
                  <span className="iv-focus-t">{runTime(focus.t_s)}</span>
                  <span className="iv-focus-who">{focus.who}</span>
                  <span className="iv-focus-model">{focus.model}</span>
                  <span className="iv-focus-tool">{TOOL_WORDS[focus.tool] ?? TAG[focus.tool] ?? focus.tool}</span>
                </div>
                <p className="iv-focus-text">{focus.text.replace(/\s*\([a-z]+_v\d+\)/g, "")}</p>
                {focusPlaces.length > 0 && (
                  <p className="iv-focus-at">
                    {focusPlaces.map((k) => <span key={k} className="iv-at"><b>{nOf(k)}</b>{places.find((p) => p.key === k)?.label}</span>)}
                  </p>
                )}
              </div>
            )}
          </div>

          {ideas.length > 0 && (
            <div className="iv-card iv-ideas">
              <div className="iv-card-head"><h2>Ideas they tested</h2><span>Not evidence</span></div>
              <ol className="iv-idea-list">
                {ideas.map((d) => (
                  <li key={d.seq}>
                    <button type="button" className="iv-idea" onClick={() => setPicked((p) => (p === d.seq ? null : d.seq))} aria-pressed={picked === d.seq}
                      aria-expanded={picked === d.seq}>
                      <span className="iv-verdict" data-ok={d.passed ? "" : undefined}>{d.verdict}</span>
                      <q>{d.quote}</q>
                      {d.why && picked === d.seq && <small>{d.tested ? "Tested" : "Why"}: {d.why}</small>}
                    </button>
                  </li>
                ))}
              </ol>
            </div>
          )}

          <div className="iv-foot">
            {done && <Link className="iv-btn-primary" href={`/cases/${caseId}`}>See the answer</Link>}
            {!done && <span>No one needs to click anything until the answer is ready.</span>}
          </div>
        </section>

        <aside className="iv-right">
          <div className="iv-card iv-where">
            <div className="iv-card-head"><h2>Where they looked</h2></div>
            <ol className="iv-places">
              {places.map((p) => {
                const who = crew.filter((c) => steps.some((s) => s.role === c.role && placesOf(s).includes(p.key)));
                const fr = frameOf(p.key);
                return (
                  <li key={p.key}>
                    <button type="button" className="iv-place" data-tone={p.tone} data-on={focusPlaces.includes(p.key) ? "" : undefined} onClick={() => pickPlace(p.key)}
                      onMouseEnter={() => setHoverPlace(p.key)} onMouseLeave={() => setHoverPlace(null)} onFocus={() => setHoverPlace(p.key)} onBlur={() => setHoverPlace(null)}>
                      <span className="iv-place-pic">
                        {/* eslint-disable-next-line @next/next/no-img-element -- a signed frame of the journey video, from the API */}
                        {fr?.thumb_url ? <img src={signedUrl(fr.thumb_url)} alt="" /> : <span className="iv-place-none" />}
                        <span className="iv-place-n">{nOf(p.key)}</span>
                      </span>
                      <span className="iv-place-body">
                        <span className="iv-place-name">{p.label}</span>
                        {fr && <span className="iv-place-fr" title={fr.title}>{hm(fr.t)}</span>}
                        <span className="iv-place-who" aria-label={`Worked here: ${who.map((c) => c.who).join(", ")}`}>
                          {who.map((c) => <span key={c.role} className="iv-pip" data-fam={fam(c.model)} title={`${c.who} · ${c.model}`} />)}
                        </span>
                      </span>
                    </button>
                  </li>
                );
              })}
            </ol>
          </div>
        </aside>
      </div>
    </div>
  );
}

interface Place { key: string; xy: XY; label: string; tone: "scan" | "seen" | "bad" }

/** the model behind an agent, as one of five colours (its name is always written beside it) */
function fam(model: string): string {
  return /Wonder/.test(model) ? "wonder" : /Glimmer/.test(model) ? "glimmer" : /Spark/.test(model) ? "spark" : /SAM/.test(model) ? "sam" : "rules";
}

const camWords = (id: string) => id.startsWith("CHK_") ? `${CLOSE[id.slice(4)] ?? id.slice(4)} close-up camera` : id.replace("_", " ");
