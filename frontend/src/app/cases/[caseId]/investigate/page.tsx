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
  text: string; node: Node | null; camera_id: string | null; cost_usd: number; cameras_checked: number }
interface End { type: "run_end"; t_s: number; cost_usd: number; cameras_checked: number; text: string }
type Ev = Step | End | { type: "node"; node: Node };
interface RunView { steps: (Step | Ev)[]; crew: { role: string; who: string; model: string; tools: string[] }[]; optional_tools: string[];
  columns: Record<string, string> }
interface CaseState { case: { case_id: string; target_description: string } }

const TAG: Record<string, string> = { read_scans: "Scan records", triage_clips: "Triage on site", plan: "Planning", pick_cameras: "Planning",
  re_plan: "Re-planning", sam_track: "Tracking the box", verify: "Verified", reject: "Rejected", create_search_task: "Search task",
  ask_a_person: "Asking a person", draft_report: "Report" };
const secs = (t: number) => (t < 10 ? t.toFixed(1) : String(Math.round(t)));
const WHO_COLOR: Record<string, string> = { lead: "#A5B4FC", triage: "#A5B4FC", analyst: "#93C5FD", verifier: "#FCD34D", tracker: "#86EFAC", reporter: "#C9CCD3" };

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
        text: `Took ${last.t_s} s and US$${last.cost_usd.toFixed(2)}. ${last.cameras_checked} cameras checked of 19.` } : null;
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
  const done = !!end;

  // node states: the latest word on each node wins; the node being checked right now is "checking"
  const nodes = new Map<string, Node>();
  for (const e of vis) if ((e.type === "run_step" || e.type === "node") && e.node) nodes.set(e.node.key, e.node);
  if (!done && cur?.node && cur.tool === "observe_clip" && live) nodes.set(cur.node.key, { ...cur.node, state: "checking", label: "Checking…" });
  const cols = ["last", ...Object.keys(columns).filter((c) => c !== "last")].map((c) => ({ key: c, label: columns[c] ?? c,
    nodes: [...nodes.values()].filter((n) => n.column === c) })).filter((c) => c.key === "last" || c.nodes.length);
  const seen = steps.filter((s) => s.node?.state === "seen" && s.tool !== "read_scans").length;
  const lastScan = steps.find((s) => s.tool === "read_scans");
  const title = !done ? "Investigating…" : seen > 0 ? "Found where it went." : `Lost track after ${lastScan?.node?.place.replace("scan ", "").slice(0, 5) ?? "the last scan"}.`;
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
          <span><strong>{end?.cameras_checked ?? cur?.cameras_checked ?? 0}</strong> <span>of 19 cameras checked</span></span>
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
            {steps.map((s) => (
              <div key={s.seq} className="iv-log-row" data-status={s.status}>
                <span className="iv-log-t">{s.clock ?? `+${s.t_s}s`}</span>
                <span className="iv-log-who" style={{ color: WHO_COLOR[s.role] ?? "#C9CCD3" }}>{s.who.replace(/s$/, "")}</span>
                <span className="iv-log-text">{s.text}</span>
              </div>
            ))}
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
            {heroPin && <HubPlan label={`${tag}: on the floor plan`} focus={{ xy: heroPin, radius_m: 10, tone: "bad" }} legend={false} fit="contain" minHeight={0} />}
            <span className="iv-hero-tag">{tag}</span>
          </div>

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
                          {st === "done" ? "✓ " : ""}{t}{n > 1 ? ` ×${n}` : ""}
                        </span>
                      );
                    })}
                  </div>
                </div>
              );
            })}
            <p className="iv-crew-note">Dashed steps only run when needed.</p>
          </div>
        </aside>
      </div>
    </div>
  );
}
