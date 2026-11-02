"use client";
/**
 * Investigating, ported from review/refs/flow/Investigate.dc.html (owner 09:22; agent_showcase_0925). Every node, chip,
 * log line and meter value comes from the run's typed steps (POST /v1/cases/{id}/run, streamed; GET replays the last
 * run). Model steps that are not configured say so in the log; nothing here is scripted.
 */
import Link from "next/link";
import { use, useCallback, useEffect, useRef, useState } from "react";
import { API_BASE, api, invalidate, useResource } from "@/lib/api";
import { HUB, camId } from "@/lib/hub";
import type { MissingMoment, XY } from "@/lib/journey";
import HubPlan from "@/components/plan/HubPlan";
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

interface Beat { key: string; text: string; model: string; seq: number }
const first = (t: string) => t.split(/(?<=\.)\s/)[0].replace(/\.$/, "");
const unparen = (t: string) => t.replace(/\s*\([^)]*\)/g, "").replace(/\.$/, "");

/** The run as a short storyline for a supervisor: one plain line per stage, each from the run's own steps (their
 *  words and receipts), in the order they happened; a stage appears once its first step has. The full log stays below. */
function storyline(steps: Step[], crew: RunView["crew"]): Beat[] {
  const model = (role: string) => crew.find((c) => c.role === role)?.model.replace(/\s*·.*$/, "") ?? "";
  const done = (tool: string) => steps.filter((s) => s.tool === tool && s.status === "done");
  const out: Beat[] = [];
  const add = (key: string, s: Step | undefined, text: string, role = s?.role ?? "") => { if (s) out.push({ key, text, model: model(role), seq: s.seq }); };
  const read = done("read_scans")[0];
  add("read", read, read ? unparen(read.text).replace(/\. Last: (.*)$/, " (last: $1)").replace(/^Read /, "Read the ") : "");
  const tri = done("triage_clips")[0];
  const share = (tri?.receipt?.output as { sent_share?: number } | undefined)?.sent_share;
  add("triage", tri, share != null ? `Skipped ${Math.round((1 - share) * 100)}% of the footage; only moments with parcel handling went to the cloud` : tri ? first(tri.text) : "");
  const plan = done("plan")[0], pick = done("pick_cameras")[0];
  add("plan", plan, plan ? `${plan.text.split(":")[0]}${pick ? `. ${unparen(pick.text)}` : ""}` : "");
  const doors = done("door_crossings"), tracked = done("sam_track");
  const door = doors.at(-1)?.text.match(/^(.+?): (.+?) at its door/);
  add("track", tracked[0], door ? `Tracked who went in and out: ${door[2]} at the ${door[1]} door` : tracked[0] ? unparen(tracked[0].text) : "", "tracker");
  const carrier = done("carrier_check")[0], looked = done("observe_clip");
  // Spark's own words on the clip (kept on the step), first clause only: never a paraphrase of what it did not say
  const said = looked.map((x) => (x.receipt?.output as { said?: string | null } | undefined)?.said).find(Boolean);
  const quote = said ? ` Spark on the clip: “${said.split(/[;.]\s/)[0].replace(/\.$/, "")}”` : "";
  add("carrier", carrier ?? looked[0], carrier ? `${unparen(carrier.text)}.${quote || (looked.length ? ` ${looked.length === 1 ? "A clip" : `${looked.length} clips`} checked` : "")}`
    : looked[0] ? `${unparen(looked[0].text).replace(/Muse \w+ /, "")}.${quote}` : "", "analyst");
  const ideas = done("propose");
  const tests = steps.filter((s) => s.role === "verifier" && s.seq > (ideas[0]?.seq ?? Infinity) && /^(Passed|Unproven|Rejected)/.test(s.text));
  const passed = tests.filter((s) => s.text.startsWith("Passed")).length;
  const why = tests.find((s) => !s.text.startsWith("Passed"))?.text.match(/\(([^)]*)\)/)?.[1];
  add("ideas", tests[0], `Tested ${tests.length} idea${tests.length === 1 ? "" : "s"}: ${passed} passed, ${tests.length - passed} not proven${why ? ` (${why})` : ""}`, "verifier");
  const ask = done("ask_a_person")[0] ?? done("create_search_task")[0];
  add("ask", ask, ask ? unparen(ask.text) : "");
  return out.sort((x, y) => x.seq - y.seq);
}

export default function InvestigatePage({ params }: { params: Promise<{ caseId: string }> }) {
  const { caseId } = use(params);
  const state = useResource<CaseState>(`/v1/cases/${caseId}/state`);
  const stored = useResource<RunView>(`/v1/cases/${caseId}/run`);
  const mm = useResource<MissingMoment>(`/v1/cases/${caseId}/missing-moment`);
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
    replay(stored.data.steps as Ev[]);
    return () => { if (timer.current) window.clearInterval(timer.current); started.current = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- once, when the stored run is known
  }, [stored.data]);

  useEffect(() => { replayRef.current = replay; });
  function replay(evs: Ev[]) {
    if (timer.current) window.clearInterval(timer.current);
    const end: End | null = evs.some((e) => e.type === "run_end") ? null : (() => {
      const last = [...evs].reverse().find((e) => e.type === "run_step") as Step | undefined;
      return last ? { type: "run_end", t_s: last.t_s, cost_usd: last.cost_usd, cameras_checked: last.cameras_checked,
        text: `Took ${last.t_s} s and US$${last.cost_usd.toFixed(2)}. 19 wide cameras on site, ${last.cameras_checked} examined closely.` } : null;
    })();
    const all = end ? [...evs, end] : evs;
    setEvents(all);
    setShown(0);
    let i = 0;
    timer.current = window.setInterval(() => {
      i += 1;
      setShown(i);
      if (i >= all.length && timer.current) window.clearInterval(timer.current);
    }, 650);
  }

  const crew = stored.data?.crew ?? [];
  const optional = new Set(stored.data?.optional_tools ?? []);
  const columns = stored.data?.columns ?? {};
  const vis = events.slice(0, shown);
  const steps = vis.filter((e): e is Step => e.type === "run_step");
  const end = vis.find((e): e is End => e.type === "run_end");
  const cur = steps.at(-1);
  // Glimmer's on-site sweep looks at every camera; the agents then examine a few closely
  const swept = end?.swept ?? steps.find((s) => s.tool === "triage_clips" && s.status === "done")?.receipt?.output?.cameras ?? 0;
  const done = !!end;
  const story = storyline(steps, stored.data?.crew ?? []);

  // node states: the latest word on each node wins; the node being checked right now is "checking"
  const nodes = new Map<string, Node>();
  for (const e of vis) if ((e.type === "run_step" || e.type === "node") && e.node) nodes.set(e.node.key, e.node);
  if (!done && cur?.node && (cur.tool === "observe_clip" || cur.tool === "sam_track") && live) nodes.set(cur.node.key, { ...cur.node, state: "checking", label: "Checking…" });
  const cols = ["last", ...Object.keys(columns).filter((c) => c !== "last")].map((c) => ({ key: c, label: columns[c] ?? c,
    nodes: [...nodes.values()].filter((n) => n.column === c) })).filter((c) => c.key === "last" || c.nodes.length);
  const seen = steps.filter((s) => s.node?.state === "seen" && s.tool !== "read_scans").length;
  const lastScan = steps.find((s) => s.tool === "read_scans");
  const title = !done ? "Investigating…" : end?.headline ? end.headline : seen > 0 ? "Found where it went." : `Lost track after ${lastScan?.node?.place.replace("scan ", "").slice(0, 5) ?? "the last scan"}.`;
  const waybill = state.data?.case.target_description.split(" ").at(-1) ?? "";
  const tag = cur ? (cur.tool === "observe_clip" && cur.node ? `Checking ${cur.node.name}` : TAG[cur.tool] ?? cur.tool) : "Starting";
  const camPos = cur?.camera_id ? HUB.cameras.find((c) => c.id === camId.toHub(cur.camera_id!))?.position_m : undefined;
  const heroPin: XY | null = camPos ? [camPos[0], camPos[1]] : mm.data?.objects[0]?.last_confirmed?.xy ?? null;

  return (
    <div className="iv">
      <div className="iv-head">
        <div>
          <p className="iv-crumb"><Link href="/hub">Hub</Link> <span aria-hidden="true">›</span> {waybill}</p>
          <h1 className="iv-title">{title}</h1>
        </div>
        <div aria-label="Live meter" className="iv-meter">
          <span><strong>US${(end?.cost_usd ?? cur?.cost_usd ?? 0).toFixed(2)}</strong> <span>spent</span></span>
          {swept > 0 && <span><strong>{swept}</strong> <span>wide cameras swept</span></span>}
          <span><strong>{end?.cameras_checked ?? cur?.cameras_checked ?? 0}</strong> <span>{swept > 0 ? "examined closely" : "of 19 wide cameras examined"}</span></span>
          <span><strong>{secs(end?.t_s ?? cur?.t_s ?? 0)} s</strong></span>
          <button type="button" onClick={() => (events.length && !live ? replay(events) : undefined)} disabled={live || !events.length}>Replay</button>
        </div>
      </div>

      <div className="iv-main">
        <section className="iv-left">
          <div className="iv-card iv-map">
            <div className="iv-card-head">
              <h2>Search map</h2>
              <span>The lead picks where to look next. Cameras that show nothing are ruled out.</span>
            </div>
            <div className="iv-cols">
              {cols.map((c) => (
                <div key={c.key} className="iv-col">
                  <span className="iv-col-label">{c.label}</span>
                  {c.nodes.length ? c.nodes.map((n) => (
                    <div key={n.key} className="iv-node" data-state={n.state}>
                      <span className="iv-node-name">{n.name}</span>
                      <span className="iv-node-place">{n.place}</span>
                      <span className="iv-node-status">{n.label}</span>
                    </div>
                  )) : <div className="iv-node" data-state="hidden" aria-hidden="true"><span className="iv-node-name">…</span><span className="iv-node-place">not chosen yet</span></div>}
                </div>
              ))}
            </div>
          </div>

          <div className="iv-card iv-log">
            <h2>What the crew did</h2>
            {story.length > 0 && (
              <ol className="iv-story" aria-label="The run, step by step">
                {story.map((b, i) => (
                  <li key={b.key} className="iv-story-row" data-now={!done && i === story.length - 1 ? "" : undefined}>
                    <span className="iv-story-text">{b.text}</span>
                    <span className="iv-story-model">{b.model}</span>
                  </li>
                ))}
              </ol>
            )}
            {steps.length > 0 && (
            <details className="iv-every">
              <summary>Show every step <span>{steps.length}</span></summary>
            {steps.map((s) => (
              <div key={s.seq} className="iv-log-row" data-status={s.status}>
                <span className="iv-log-t" title="Time since the run started">{runTime(s.t_s)}</span>
                <span className="iv-log-who">{s.who.replace(/s$/, "")}</span>
                <span className="iv-log-text">{s.text}</span>
              </div>
            ))}
            </details>
            )}
            {!steps.length && <p className="iv-log-wait" role={failed ? "alert" : undefined}>{failed ? `The run could not start: ${failed}` : stored.loading ? "Loading the last run" : "Starting the crew"}</p>}
          </div>

          <div className="iv-foot">
            {done && <Link className="iv-btn-primary" href={`/cases/${caseId}`}>See the answer</Link>}
            <span>{done ? end!.text : "No one needs to click anything until the answer is ready."}</span>
          </div>
        </section>

        <aside className="iv-right">
          <div className="iv-hero">
            {/* no frame for this step: the plan, pinned at the camera being checked or where the parcel stopped (review F-046 #2) */}
            {heroPin && <HubPlan label={`${tag}: on the floor plan`} focus={{ xy: heroPin, radius_m: 10, tone: "bad" }} legend={false} fit="contain" minHeight={0} quiet />}
          </div>
          <p className="iv-hero-tag">{tag}</p>

          <div className="iv-card iv-crew">
            <h2>The investigation crew</h2>
            {crew.map((c) => {
              const mine = steps.filter((s) => s.role === c.role);
              const active = !done && cur?.role === c.role;
              return (
                <div key={c.role} className="iv-crew-row" data-active={active ? "" : undefined}>
                  <div className="iv-crew-top"><span className="iv-crew-who">{c.who}</span><span className="iv-crew-model">{c.model}</span></div>
                  <div className="iv-tools">
                    {c.tools.map((t) => {
                      const ran = mine.filter((s) => s.tool === t);
                      const st = ran.some((s) => s.status === "done" || s.status === "rejected") ? "done"
                        : optional.has(t) ? "optional" : ran.some((s) => s.status === "unavailable") ? "off" : "waiting";
                      const n = ran.filter((s) => s.status === "done").length;
                      return (
                        <span key={t} className="iv-tool" data-state={st} title={st === "off" ? ran.find((s) => s.status === "unavailable")?.text : undefined}>
                          {TOOL_WORDS[t] ?? t.replace(/_/g, " ")}{n > 1 ? ` ×${n}` : ""}
                        </span>
                      );
                    })}
                  </div>
                </div>
              );
            })}
            <p className="iv-crew-note">Steps in grey only run when needed.</p>
          </div>
        </aside>
      </div>
    </div>
  );
}
