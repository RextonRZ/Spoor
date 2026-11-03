"use client";
/**
 * Spoor Floor: the worker's phone app for one search (Rexton 3 Nov; reviewer 03:40 spec). Light, for a bright hall:
 * white surfaces, near-black text, indigo the one action colour, evidence colours only for status. Big targets, one
 * primary action in a fixed bottom bar, a back arrow and "n of 4" on every screen. Screens push in from the right and go
 * back the way they came (spatial consistency); presses answer on pointer-down.
 *
 *   Tasks -> Task (what to look for, where to walk) -> Search (where to look, voice note) -> Scan (barcode) -> Found
 *                                                                  \-> Not here (reason) -> Spoor checks the next place
 *
 * Everything shown comes from the case: the place from the search task, the last-seen frame and the parcel's tunnel photo,
 * size and weight from its scans. Answers are recorded through the same API as before (a statement by floor staff);
 * a voice note is transcribed by Muse Voice Transcribe and only attached when the worker taps "Use this note".
 */
import { useCallback, useEffect, useMemo, useRef, useState, useSyncExternalStore } from "react";
import { flushSync } from "react-dom";
import { api, invalidate, signedUrl, useResource } from "@/lib/api";
import type { Journey, MissingMoment, XY } from "@/lib/journey";
import type { Reel } from "@/components/case/JourneyReel";
import { toWav16k } from "@/lib/wav";
import { HUB } from "@/lib/hub";
import FloorPlan, { centroid, walkRoute } from "@/components/plan/FloorPlan";
import { WalkNav } from "./WalkNav";
import "./floor.css";

interface Place { area_id: string; name: string; zone_id: string | null; centroid_xy: XY; why: string[] }
export interface SearchView {
  found: { area_id: string; name: string; by: string; at: string } | null;
  tasks: { search_task_id: string; created_by: string; created_at: string; places: Place[];
    outcomes: { area_id: string; outcome: "found" | "not_found"; note?: string | null }[] }[];
}
type Screen = "tasks" | "map" | "me" | "task" | "search" | "scan" | "found" | "done" | "next";
type Tab = "tasks" | "map" | "scan" | "me";
/** the tab roots: the tab bar shows on these; a task's own screens push over it and hide it (as iOS does) */
const ROOTS: Screen[] = ["tasks", "map", "me", "done"];
const STEP: Partial<Record<Screen, number>> = { task: 1, search: 2, scan: 3, found: 4 };
const ZONE_WORDS: Record<string, string> = { store: "shelves · floor · cages", staging: "cages · floor around them", work: "benches · floor · bins",
  machine: "under the belt · catch trays", dock: "trailer edge · floor · cages", office: "desk · shelves" };
const hm = (iso: string) => new Date(iso).toLocaleTimeString("en-GB", { timeZone: "Asia/Kuala_Lumpur", hour: "2-digit", minute: "2-digit" });
const buzz = (ms = 12) => { try { navigator.vibrate?.(ms); } catch { /* not on this device */ } };

/** "Exception store (Z11)" -> name + zone; "Z10 Cage staging (...)" -> "Cage staging" */
function placeName(p: Place): string {
  return /^Z\d+ /.test(p.name) ? p.name.replace(/^Z\d+ /, "").replace(/\s*[(,;].*$/, "") : p.name.replace(/\s*\(Z\d+\)$/, "");
}
function zoneOf(p: Place) {
  const id = (p.zone_id ?? "").replace(/^zone_/, "") || p.name.match(/Z\d+/)?.[0] || "";
  return (HUB as unknown as { zones: { id: string; kind: string; polygons: number[][][] }[] }).zones.find((z) => z.id === id);
}

export function FloorApp({ caseId, waybill, waited, framed = true, center }: { caseId: string; waybill: string; waited?: string | null; framed?: boolean; center?: boolean }) {
  const path = `/v1/cases/${caseId}/search-tasks`;
  const view = useResource<SearchView>(path);
  const jr = useResource<Journey>(`/v1/cases/${caseId}/journey`);
  const mr = useResource<MissingMoment>(`/v1/cases/${caseId}/missing-moment`);
  const reel = useResource<Reel>(`/v1/cases/${caseId}/journey-reel`);
  const [chosen, setScreen] = useState<Screen>("tasks");
  const [dir, setDir] = useState<"fwd" | "back" | "tab">("fwd");
  const [scanFromTab, setScanFromTab] = useState(false);
  const [sheet, setSheet] = useState(false);
  const [note, setNote] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const offline = !useSyncExternalStore(onlineSub, () => navigator.onLine, () => true);
  const [replanJob, setReplanJob] = useState<string | null>(null);

  const task = view.data?.tasks.at(-1);
  const done = new Set(task?.outcomes.map((o) => o.area_id) ?? []);
  const places = useMemo(() => (task?.places ?? []).filter((pl, i, all) =>
    all.findIndex((q) => placeName(q).toLowerCase() === placeName(pl).toLowerCase()) === i), [task]);
  const place = places.find((p) => !done.has(p.area_id));
  const scans = jr.data?.objects[0]?.scans ?? [];
  const dims = scans.find((s) => s.dims_mm)?.dims_mm;
  const grams = scans.find((s) => s.weight_g)?.weight_g;
  const lastSeen = reel.data?.chapters.find((c) => c.tone === "noscan") ?? reel.data?.chapters.filter((c) => c.thumb_url && c.tone !== "card").at(-1);
  const lastFrame = mr.data?.objects[0]?.last_confirmed?.frames?.[0];

  // the office (where the supervisor hands out tasks) to the place, along the hub's walkways
  const zone = place ? zoneOf(place) : undefined;
  const you = YOU;
  const route = walkRoute(YOU, place?.centroid_xy ?? YOU);
  const metres = route.reduce((a, p, i) => i ? a + Math.hypot(p[0] - route[i - 1][0], p[1] - route[i - 1][1]) : 0, 0);
  const walkMin = Math.max(1, Math.round(metres / 1.2 / 60)); // a brisk walk, 1.2 m/s
  const here = metres < 8; // the place is where the worker starts (the office): no walk to show
  const walkWords = here ? "Where you are" : `About ${walkMin} min walk`;

  // an answer saved while offline goes out when the phone is back online
  const flush = useCallback(async () => {
    let q: { area_id: string; outcome: string; note?: string; task: string }[] = [];
    try { q = JSON.parse(localStorage.getItem(`floor:${caseId}`) ?? "[]"); } catch { q = []; }
    if (!q.length || !navigator.onLine) return;
    for (const a of q) await api(`${path}/${a.task}/outcome`, { method: "POST", json: { area_id: a.area_id, outcome: a.outcome, note: a.note } }).catch(() => undefined);
    try { localStorage.removeItem(`floor:${caseId}`); } catch { /* storage blocked */ }
    invalidate(path);
  }, [caseId, path]);
  useEffect(() => { if (!offline) void flush(); }, [offline, flush]);
  // a found parcel shows its done screen (also when it was found from another phone)
  const screen: Screen = view.data?.found && chosen !== "found" ? "done" : chosen;

  const [scrolled, setScrolled] = useState(false);
  const go = (s: Screen, d: "fwd" | "back" | "tab" = "fwd") => {
    const apply = () => { setDir(d); setErr(null); setScrolled(false); setScreen(s); };
    // the place name on the task card becomes the task screen's title (a shared element), where the browser can
    const vt = (document as Document & { startViewTransition?: (f: () => void) => unknown }).startViewTransition;
    if (vt && (s === "task" && screen === "tasks" || s === "tasks" && screen === "task") && !matchMedia("(prefers-reduced-motion: reduce)").matches) {
      vt.call(document, () => flushSync(apply));
    } else apply();
  };
  const back = () => go(screen === "task" ? "tasks" : screen === "search" ? "task" : screen === "scan" ? (scanFromTab ? "tasks" : "search") : "tasks", "back");
  const root = ROOTS.includes(screen);
  const swipe = useSwipeBack(!root && screen !== "next" && screen !== "found", back);
  const [nav, setNav] = useState(false);   // walking directions on: the tab bar steps aside, as in a maps app
  const tab: Tab | null = nav && screen === "map" ? null : screen === "done" ? "tasks" : screen === "tasks" || screen === "map" || screen === "me" ? screen : null;
  const onTab = (t: Tab) => {
    buzz(8);
    if (t === "scan") { setScanFromTab(true); go("scan"); return; }
    if (t !== tab) go(t === "tasks" && view.data?.found ? "done" : t, "tab");
  };
  // answers saved on the phone while offline, for the Me tab (Me only opens on a tap, never on the server render)
  let queued = 0;
  if (screen === "me") { try { queued = JSON.parse(localStorage.getItem(`floor:${caseId}`) ?? "[]").length; } catch { queued = 0; } }

  async function answer(outcome: "found" | "not_found", text?: string | null) {
    if (!task || !place) return;
    setBusy(true); setErr(null);
    const body = { area_id: place.area_id, outcome, note: text ?? note ?? undefined };
    if (!navigator.onLine) {
      try {
        const q = JSON.parse(localStorage.getItem(`floor:${caseId}`) ?? "[]");
        localStorage.setItem(`floor:${caseId}`, JSON.stringify([...q, { ...body, task: task.search_task_id }]));
      } catch { /* storage blocked */ }
      setBusy(false);
      go(outcome === "found" ? "done" : "next");
      return;
    }
    try {
      const r = await api<{ replan_job_id?: string }>(`${path}/${task.search_task_id}/outcome`, { method: "POST", json: body });
      if (r.replan_job_id) setReplanJob(r.replan_job_id);
      invalidate(path);
      invalidate(`/v1/cases/${caseId}/possible-locations`);
      buzz(outcome === "found" ? 30 : 12);
      setNote(null);
      go(outcome === "found" ? "done" : "next");
    } catch (e) { setErr(e instanceof Error ? e.message : String(e)); } finally { setBusy(false); }
  }

  const step = STEP[screen];
  const title = screen === "tasks" ? "Your tasks" : screen === "task" ? "Find this parcel" : screen === "search" ? `Check the ${place ? placeName(place) : "place"}`
    : screen === "scan" ? "Scan the label" : screen === "found" ? "It's the parcel" : screen === "next" ? "Thanks, noted" : "Done";

  const body = (
    <div className="fa" data-offline={offline ? "" : undefined}>
      <StatusBar />
      {!root && (
        <header className="fa-bar">
          {screen !== "next"
            ? <button type="button" className="fa-back" onClick={back} aria-label="Back"><svg viewBox="0 0 24 24" aria-hidden><path d="M15 5l-7 7 7 7" /></svg></button>
            : <span />}
          <span className="fa-bar-title" data-shown={scrolled || screen === "scan" || screen === "found" ? "" : undefined}>{screen !== "next" ? title : ""}</span>
          {step ? <span className="fa-steps" aria-label={`Step ${step} of 4`}>{[1, 2, 3, 4].map((i) => <i key={i} data-on={i <= step ? "" : undefined} />)}</span> : <span />}
        </header>
      )}
      {offline && <p className="fa-offline" role="status">Offline. Your answer is saved and goes out when you are back online.</p>}

      <div className="fa-stage" onScrollCapture={(e) => { const y = (e.target as HTMLElement).scrollTop; if ((y > 34) !== scrolled) setScrolled(y > 34); }}
        {...swipe}>
        <div key={screen} className="fa-screen" data-dir={dir}>
          {screen === "tasks" && (
            <div className="fa-pad fa-scroll fa-root">
              <h1 className="fa-root-t">Tasks</h1>
              <p className="fa-lead">{task && place ? "1 search, sent by the hub supervisor" : view.data?.found ? "All done" : "New searches arrive here the moment the supervisor sends one."}</p>
              {task && place ? (
                <button type="button" className="fa-card fa-taskcard" onClick={() => { buzz(); go("task"); }}>
                  <span className="fa-chip" data-tone="urgent">{waited ? `Customer waiting ${waited}` : "Customer waiting"}</span>
                  <span className="fa-card-place fa-vt-place">{placeName(place)}</span>
                  <span className="fa-card-why">{lastSeen && placeName(place).toLowerCase().split(" ").some((w) => lastSeen.title.toLowerCase().includes(w))
                    ? `${lastSeen.title} at ${hm(lastSeen.t)}, not seen coming out` : "Next most likely place, from the cameras"}</span>
                  <span className="fa-card-meta">
                    <span><svg viewBox="0 0 24 24" aria-hidden><path d="M13 4a1.5 1.5 0 1 0 0-.01M10 21l2-6 3 3v5M8 12l3-3 3 2 2 3M11 9l-2 6" /></svg>{walkWords}</span>
                    <span className="fa-mono">…{waybill.slice(-4)}</span>
                  </span>
                  <svg className="fa-card-go" viewBox="0 0 24 24" aria-hidden><path d="M9 5l7 7-7 7" /></svg>
                </button>
              ) : <div className="fa-empty"><span className="fa-empty-ring"><Mark /></span></div>}
              {task && place && <button type="button" className="fa-primary" onClick={() => { buzz(); go("task"); }}>Open the task</button>}
              {task && place && places.length > 1 && (
                <section className="fa-group" aria-label="Where to look, in order">
                  <h2 className="fa-k">Where to look, in order</h2>
                  <ol className="fa-card fa-rows fa-order">
                    {places.map((p, i) => {
                      const st = done.has(p.area_id) ? "ruled" : p.area_id === place.area_id ? "now" : "next";
                      return (
                        <li key={p.area_id} data-state={st}>
                          <span className="fa-order-n">{i + 1}</span>
                          <span className="fa-row-t">{placeName(p)}</span>
                          {st === "now" ? <span className="fa-chip" data-tone="lang">Now</span> : st === "ruled" ? <span className="fa-chip" data-tone="mute">Not here</span> : null}
                        </li>
                      );
                    })}
                  </ol>
                </section>
              )}
              {!!task?.outcomes.length && (
                <section className="fa-group" aria-label="Checked today">
                  <h2 className="fa-k">Checked today</h2>
                  <ul className="fa-card fa-rows">
                    {task.outcomes.map((o, i) => {
                      const pl = task.places.find((x) => x.area_id === o.area_id);
                      return (
                        <li key={i}>
                          <span className="fa-row-t">{pl ? placeName(pl) : "A place"}</span>
                          <span className="fa-chip" data-tone={o.outcome === "found" ? "ok" : "mute"}>{o.outcome === "found" ? "Found" : "Not here"}</span>
                        </li>
                      );
                    })}
                  </ul>
                </section>
              )}
            </div>
          )}

          {screen === "map" && place && (
            <WalkNav walkKey={place.area_id} route={route} dest={placeName(place)} destZone={zone?.id} onSearch={() => go("search")} onNavigating={setNav}
              destPoly={place.area_id === BLIND?.id ? BLIND.polygon : zone?.polygons[0]} />
          )}
          {screen === "map" && !place && (
            <div className="fa-pad fa-scroll fa-root">
              <h1 className="fa-root-t">Map</h1>
              <p className="fa-lead">{place ? here ? `You are at the ${placeName(place).toLowerCase()}` : `The office to the ${placeName(place).toLowerCase()}, about ${walkMin} min` : "The hub floor"}</p>
              <section className="fa-card fa-map fa-map-full" aria-label="Hub floor plan">
                <FloorPlan label={place ? `Hub floor plan, the walk to the ${placeName(place)}` : "Hub floor plan"} highlight={zone?.id}
                  route={place && !here ? route : undefined} you={you} labels="none" labelIds={["Z13", zone?.id ?? "", "Z05"]} labelSize={2.8} dim={!!place} />
              </section>
              <ul className="fa-card fa-rows fa-legend">
                <li><i className="fa-lg-you" aria-hidden />You<span className="fa-row-s">The office</span></li>
                {place && <li><i className="fa-lg-hl" aria-hidden />Search here<span className="fa-row-s">{placeName(place)}</span></li>}
                {place && !here && <li><i className="fa-lg-route" aria-hidden />Walk<span className="fa-row-s">{Math.round(metres)} m along the walkways</span></li>}
              </ul>
              {task && place && <button type="button" className="fa-primary" onClick={() => { buzz(); go("task"); }}>Open the task</button>}
            </div>
          )}

          {screen === "me" && (
            <div className="fa-pad fa-scroll fa-root">
              <h1 className="fa-root-t">Me</h1>
              <section className="fa-card fa-me">
                <span className="fa-avatar" aria-hidden>FS</span>
                <span><b>Floor staff</b><small>Klang Valley hub</small></span>
              </section>
              <ul className="fa-card fa-rows">
                <li><span className="fa-row-t">Connection</span><span className="fa-row-v" data-tone={offline ? "bad" : "ok"}>{offline ? "Offline" : "Online"}</span></li>
                <li><span className="fa-row-t">Position</span><span className="fa-row-v">Last scan · the office</span></li>
                <li><span className="fa-row-t">Answers waiting to send</span><span className="fa-row-v">{queued}</span></li>
                <li><span className="fa-row-t">Places checked today</span><span className="fa-row-v">{task?.outcomes.length ?? 0}</span></li>
                <li><span className="fa-row-t">Voice notes</span><span className="fa-row-v">English or Malay</span></li>
              </ul>
              <p className="fa-fine">Your answers go to the hub supervisor as your statement. Nothing goes to the customer from this app.</p>
            </div>
          )}

          {screen === "task" && place && (
            <div className="fa-pad fa-scroll">
              <div className="fa-large"><span className="fa-k">Find this parcel</span><h1 className="fa-large-t fa-vt-place">{placeName(place)}</h1></div>
              <figure className="fa-hero">
                {lastSeen?.thumb_url
                  // eslint-disable-next-line @next/next/no-img-element -- a signed frame from the case's journey video
                  ? <img src={signedUrl(lastSeen.thumb_url)} alt="The last camera frame of the parcel, outlined by SAM" />
                  : lastFrame
                    // eslint-disable-next-line @next/next/no-img-element -- a signed CCTV frame from the API
                    ? <img src={signedUrl(lastFrame.frame_url)} alt="The last camera frame of the parcel" /> : <span className="fa-hero-none" />}
                <figcaption>Last seen {lastSeen ? hm(lastSeen.t) : ""} · {lastSeen?.title.toLowerCase() ?? "on camera"}</figcaption>
              </figure>
              <section className="fa-card fa-look" aria-label="What to look for">
                {/* eslint-disable-next-line @next/next/no-img-element -- the tunnel reader's own photo of this parcel */}
                <img className="fa-look-pic" src={`/scanner/${waybill}.jpg`} alt="The parcel, photographed by the scan tunnel" onError={(e) => { e.currentTarget.style.visibility = "hidden"; }} />
                <div className="fa-look-txt">
                  <span className="fa-k">Look for</span>
                  <span className="fa-wb">{waybill.slice(0, -4)}<b>{waybill.slice(-4)}</b></span>
                  <span className="fa-look-sz">{dims ? `${dims.map((d) => Math.round(d / 10)).join(" × ")} cm` : "Size not measured"}{grams ? ` · ${(grams / 1000).toFixed(1)} kg` : ""}</span>
                  <span className="fa-look-sub">Brown carton, label photo from the scan tunnel</span>
                </div>
              </section>
              {/* where to walk: the Map tab gives the directions (a plan squeezed into this card was too small to read) */}
              <button type="button" className="fa-card fa-walkcard" onClick={() => { buzz(); go("map", "tab"); }} disabled={here}>
                <span className="fa-walk-ic" aria-hidden><svg viewBox="0 0 24 24"><path d="M13 4a1.5 1.5 0 1 0 0-.01M10 21l2-6 3 3v5M8 12l3-3 3 2 2 3M11 9l-2 6" /></svg></span>
                <span className="fa-walk-t">
                  <b>{here ? "You are here" : `About ${walkMin} min walk`}</b>
                  <small>{here ? `Search the ${placeName(place).toLowerCase()}` : `${Math.round(metres / 5) * 5} m from the office`}</small>
                </span>
                {!here && <span className="fa-walk-go">Directions</span>}
              </button>
            </div>
          )}

          {screen === "search" && place && (
            <div className="fa-pad fa-scroll">
              <div className="fa-large"><span className="fa-k">Step 2 of 4</span><h1 className="fa-large-t">Where to look</h1></div>
              <ol className="fa-places">
                {places.map((p, i) => {
                  const state = done.has(p.area_id) ? "ruled" : p.area_id === place.area_id ? "now" : "next";
                  return (
                    <li key={p.area_id} data-state={state}>
                      <span className="fa-pn">{state === "ruled" ? "–" : i + 1}</span>
                      <span className="fa-pt">
                        <b>{placeName(p)}</b>
                        {state === "now" ? <Checklist kind={zoneOf(p)?.kind} /> : <small>{state === "ruled" ? "Checked, not here" : "Next, if not here"}</small>}
                      </span>
                      {state === "now" && <span className="fa-pv"><VoiceHold caseId={caseId} taskId={task!.search_task_id} areaId={place.area_id} used={note} onUse={setNote} /></span>}
                    </li>
                  );
                })}
              </ol>
            </div>
          )}

          {screen === "scan" && (
            <Scanner waybill={waybill} onMatch={() => { buzz(30); go("found"); }} />
          )}

          {screen === "found" && place && (
            <div className="fa-pad fa-scroll fa-center">
              <span className="fa-tick" aria-hidden><svg viewBox="0 0 52 52"><circle cx="26" cy="26" r="24" /><path d="M15 27l7 7 15-16" /></svg></span>
              <h1 className="fa-h1">Number matched</h1>
              <p className="fa-wb fa-wb-big">{waybill.slice(0, -4)}<b>{waybill.slice(-4)}</b></p>
              <p className="fa-lead">Bring it to the exception bench and leave it with the supervisor.</p>
              <Photo />
              <VoiceHold caseId={caseId} taskId={task!.search_task_id} areaId={place.area_id} used={note} onUse={setNote} compact />
            </div>
          )}

          {screen === "next" && (
            <NextPlace job={replanJob} more={!!place} onNext={() => go(place ? "task" : "tasks")} placeName={place ? placeName(place) : null} />
          )}

          {screen === "done" && (
            <div className="fa-pad fa-center">
              <span className="fa-tick" aria-hidden><svg viewBox="0 0 52 52"><circle cx="26" cy="26" r="24" /><path d="M15 27l7 7 15-16" /></svg></span>
              <h1 className="fa-h1">Thank you</h1>
              <p className="fa-lead">{view.data?.found ? `Found at the ${view.data.found.name.replace(/\s*\(Z\d+\)$/, "")}, ${hm(view.data.found.at)}. The case is updated and the report is ready for the supervisor.` : "Saved. It goes to the supervisor as soon as you are back online."}</p>
            </div>
          )}
        </div>
      </div>

      {err && <p className="fa-err" role="alert">{err}</p>}
      {(screen === "task" || screen === "search" || screen === "found") && place && (
        <footer className="fa-dock">
          {screen === "task" && <button type="button" className="fa-primary" onPointerDown={() => buzz()} onClick={() => go("search")}>Start search</button>}
          {screen === "search" && (
            <div className="fa-two">
              {/* the two answers, side by side; "It's here" counts only once the label's number matches */}
              <button type="button" className="fa-secondary fa-ans" onClick={() => setSheet(true)}>
                <span><b>Not here</b><small>Say why</small></span>
              </button>
              <button type="button" className="fa-primary fa-ans" onPointerDown={() => buzz()} onClick={() => { setScanFromTab(false); go("scan"); }}>
                <svg viewBox="0 0 24 24" aria-hidden><path d="M4 8V5a1 1 0 0 1 1-1h3M16 4h3a1 1 0 0 1 1 1v3M20 16v3a1 1 0 0 1-1 1h-3M8 20H5a1 1 0 0 1-1-1v-3M7 9v6M10 9v6M13 9v6M16 9v6" /></svg>
                <span><b>It&apos;s here</b><small>Scan the label</small></span>
              </button>
            </div>
          )}
          {screen === "found" && <button type="button" className="fa-primary fa-primary-ok" disabled={busy} onClick={() => answer("found")}>{busy ? "Saving" : "Done, it's found"}</button>}
        </footer>
      )}
      <TabBar tab={tab} onTab={onTab} badge={task && place && !view.data?.found ? 1 : 0} scanOff={!task || !place} />
      <ReasonSheet open={sheet} onClose={() => setSheet(false)} busy={busy} onSend={(r) => { setSheet(false); void answer("not_found", [r, note].filter(Boolean).join(" · ")); }} />
    </div>
  );
  if (!framed) return body;
  return (
    <FitPhone center={center}>
      <span className="fa-island" aria-hidden />
      {body}
      <span className="fa-home" aria-hidden />
    </FitPhone>
  );
}

/** Full screen on a computer, the drawn phone fits the window (Rexton 3 Nov). It keeps its 390 px layout and scales
 *  down, never under 0.8 so the text stays readable; a shorter window gets a shorter phone instead. On the Go look page
 *  it stays true size and the page scrolls (Rexton: a squeezed phone looks wrong). */
function FitPhone({ center, children }: { center?: boolean; children: React.ReactNode }) {
  const ref = useRef<HTMLDivElement>(null);
  const [f, setF] = useState({ z: 1, h: 844 });
  useEffect(() => {
    if (!center) return;
    const fit = () => {
      const avail = window.innerHeight - 48;
      const z = Math.max(0.8, Math.min(1, avail / 844));
      setF({ z, h: Math.round(Math.max(560, Math.min(844, avail / z))) });
    };
    fit(); window.addEventListener("resize", fit);
    return () => window.removeEventListener("resize", fit);
  }, [center]);
  return (
    <div ref={ref} style={{ width: 390 * f.z, height: f.h * f.z, flex: "none" }}>
      <div className="fa-phone" style={{ height: f.h, transform: f.z < 1 ? `scale(${f.z})` : undefined, transformOrigin: "0 0" }}>{children}</div>
    </div>
  );
}

/** iOS-style floating tab bar: a glass capsule, an indicator that slides to the tab (transform only), icons that dip on
 *  press. Hidden (slides down) while a task's own screens are open. Tabs switch with a short fade, no slide: they are
 *  siblings, and a worker switches them many times a shift. */
const TABS: { id: Tab; label: string; d: string }[] = [
  { id: "tasks", label: "Tasks", d: "M9 6h11M9 12h11M9 18h11M4 6l1 1 2-2M4 12l1 1 2-2M4 18l1 1 2-2" },
  { id: "map", label: "Map", d: "M9 4 3 6v14l6-2 6 2 6-2V4l-6 2-6-2zM9 4v14M15 6v14" },
  { id: "scan", label: "Scan", d: "M4 8V5a1 1 0 0 1 1-1h3M16 4h3a1 1 0 0 1 1 1v3M20 16v3a1 1 0 0 1-1 1h-3M8 20H5a1 1 0 0 1-1-1v-3M7 9v6M10 9v6M13 9v6M16 9v6" },
  { id: "me", label: "Me", d: "M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM4.5 20a7.5 7.5 0 0 1 15 0" },
];
function TabBar({ tab, onTab, badge, scanOff }: { tab: Tab | null; onTab: (t: Tab) => void; badge: number; scanOff: boolean }) {
  const i = Math.max(0, TABS.findIndex((t) => t.id === tab));
  return (
    <nav className="fa-tabs" data-hidden={tab ? undefined : ""} aria-label="Spoor Floor" inert={!tab}>
      <span className="fa-tabs-ind" style={{ transform: `translateX(${i * 100}%)` }} aria-hidden />
      {TABS.map((t) => (
        <button key={t.id} type="button" className="fa-tab" aria-current={tab === t.id ? "page" : undefined} disabled={t.id === "scan" && scanOff} onClick={() => onTab(t.id)}>
          <svg viewBox="0 0 24 24" aria-hidden><path d={t.d} /></svg>
          <span>{t.label}</span>
          {t.id === "tasks" && badge > 0 && <i className="fa-badge" aria-label={`${badge} new`}>{badge}</i>}
        </button>
      ))}
    </nav>
  );
}

/** the office (where the supervisor hands out tasks): the worker starts there */
const OFFICE = (HUB as unknown as { zones: { id: string; polygons: number[][][] }[] }).zones.find((z) => z.id === "Z13");
const YOU: XY = OFFICE ? centroid(OFFICE.polygons[0]) : [57, 3];
/** the blind corner of the Exception store (behind its sack racks): its own shape, smaller than the whole store */
const BLIND = (HUB as unknown as { blind_corner?: { id: string; polygon: number[][] } }).blind_corner;
function onlineSub(f: () => void) {
  window.addEventListener("online", f); window.addEventListener("offline", f);
  return () => { window.removeEventListener("online", f); window.removeEventListener("offline", f); };
}

/** Swipe from the left edge to go back: the screen follows the finger 1:1 and either finishes going back or springs home
 *  (by distance or by the flick's speed), as on iOS. */
function useSwipeBack(enabled: boolean, onBack: () => void) {
  const ref = useRef<{ x: number; t: number; el: HTMLElement } | null>(null);
  return {
    onPointerDown: (e: React.PointerEvent<HTMLDivElement>) => {
      const r = e.currentTarget.getBoundingClientRect();
      if (!enabled || e.clientX - r.left > 24) return;
      const el = e.currentTarget.querySelector<HTMLElement>(".fa-screen");
      if (!el) return;
      e.currentTarget.setPointerCapture(e.pointerId);
      ref.current = { x: e.clientX, t: performance.now(), el };
      el.style.transition = "none"; el.style.animation = "none";
    },
    onPointerMove: (e: React.PointerEvent<HTMLDivElement>) => {
      const start = ref.current;
      if (!start) return;
      const dx = Math.max(0, e.clientX - start.x);
      start.el.style.transform = `translateX(${dx}px)`;
      start.el.style.boxShadow = "-12px 0 30px rgba(15,18,34,0.12)";
    },
    onPointerUp: (e: React.PointerEvent<HTMLDivElement>) => {
      const start = ref.current;
      if (!start) return;
      const { el } = start, dx = e.clientX - start.x, v = dx / Math.max(1, performance.now() - start.t);
      const w = e.currentTarget.getBoundingClientRect().width;
      ref.current = null;
      el.style.transition = "transform 320ms cubic-bezier(0.32, 0.72, 0, 1)";
      if (dx > w * 0.35 || v > 0.5) { el.style.transform = `translateX(${w}px)`; window.setTimeout(onBack, 200); }
      else { el.style.transform = ""; el.style.boxShadow = ""; }
    },
  };
}

function Mark() {
  // Rexton's exact mark, the same file the loader uses (never a redrawn stand-in)
  // eslint-disable-next-line @next/next/no-img-element
  return <img className="fa-mark" src="/brand/spoor-mark.png" alt="" aria-hidden="true" width={288} height={306} />;
}

function StatusBar() {
  // the hub's clock, not this computer's: the scan log's latest time, ticking on from when the app opened
  const sites = useResource<{ site_id: string }[]>("/v1/sites");
  const log = useResource<{ as_of: string | null }>(sites.data?.[0] ? `/v1/sites/${sites.data[0].site_id}/exceptions?limit=50` : null);
  const [t, setT] = useState("");
  useEffect(() => {
    const base = log.data?.as_of ? Date.parse(log.data.as_of) : null, t0 = Date.now();
    const f = () => setT(new Date(base !== null ? base + (Date.now() - t0) : Date.now()).toLocaleTimeString("en-GB",
      { timeZone: "Asia/Kuala_Lumpur", hour: "2-digit", minute: "2-digit" }));
    f(); const i = window.setInterval(f, 15000); return () => window.clearInterval(i);
  }, [log.data?.as_of]);
  return (
    <div className="fa-status" aria-hidden>
      <span>{t}</span>
      <span className="fa-status-r">
        <svg viewBox="0 0 18 12"><rect x="0" y="8" width="3" height="4" rx="1" /><rect x="5" y="5" width="3" height="7" rx="1" /><rect x="10" y="2.5" width="3" height="9.5" rx="1" /><rect x="15" y="0" width="3" height="12" rx="1" /></svg>
        <svg viewBox="0 0 26 12"><rect x="0.5" y="0.5" width="22" height="11" rx="3" fill="none" stroke="currentColor" /><rect x="2.5" y="2.5" width="15" height="7" rx="1.5" /><rect x="23.5" y="4" width="2" height="4" rx="1" /></svg>
      </span>
    </div>
  );
}

/** Where to look in that kind of place, ticked off as the worker goes (on the phone only: it guides, it is not a record). */
function Checklist({ kind }: { kind?: string }) {
  const items = (ZONE_WORDS[kind ?? ""] ?? "shelves · floor · bins").split(" · ");
  const [on, setOn] = useState<string[]>([]);
  return (
    <span className="fa-check" role="group" aria-label="Where to look">
      {items.map((it) => (
        <button key={it} type="button" aria-pressed={on.includes(it)} onClick={() => { buzz(8); setOn((o) => o.includes(it) ? o.filter((x) => x !== it) : [...o, it]); }}>
          <svg viewBox="0 0 16 16" aria-hidden><path d="m3.5 8.5 3 3 6-6.5" /></svg>{it[0].toUpperCase() + it.slice(1)}
        </button>
      ))}
    </span>
  );
}

/** Scan the label: the phone's camera reads the barcode where the browser can (BarcodeDetector), or the worker types the
 *  last four digits. Only this parcel's number counts as a match; another parcel's says so. */
function Scanner({ waybill, onMatch }: { waybill: string; onMatch: () => void }) {
  const vid = useRef<HTMLVideoElement>(null);
  const [cam, setCam] = useState<"off" | "on" | "none">("off");
  const [typed, setTyped] = useState("");
  const [typing, setTyping] = useState(false);
  const [miss, setMiss] = useState<string | null>(null);
  const matchRef = useRef(onMatch);
  useEffect(() => { matchRef.current = onMatch; });
  useEffect(() => {
    let stream: MediaStream | null = null, live = true, raf = 0;
    const Det = (window as unknown as { BarcodeDetector?: new (o: object) => { detect: (v: HTMLVideoElement) => Promise<{ rawValue: string }[]> } }).BarcodeDetector;
    (async () => {
      try {
        if (!navigator.mediaDevices?.getUserMedia) throw new Error("no camera");
        stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" } });
        if (!live || !vid.current) return;
        vid.current.srcObject = stream; await vid.current.play(); setCam("on");
        if (!Det) return;
        const det = new Det({ formats: ["code_128", "qr_code", "ean_13", "code_39"] });
        const tick = async () => {
          if (!live || !vid.current) return;
          const r = await det.detect(vid.current).catch(() => []);
          const hit = r.map((x) => x.rawValue).find(Boolean);
          if (hit) { if (hit.includes(waybill)) { matchRef.current(); return; } setMiss(hit); }
          raf = window.setTimeout(tick, 250);
        };
        void tick();
      } catch { if (live) setCam("none"); }
    })();
    return () => { live = false; window.clearTimeout(raf); stream?.getTracks().forEach((t) => t.stop()); };
  }, [waybill]);
  const check = (v: string) => {
    setTyped(v);
    if (v.length === 4) { if (waybill.endsWith(v)) onMatch(); else { setMiss(`…${v}`); buzz(40); } }
  };
  return (
    <div className="fa-scan">
      <div className="fa-viewfinder" data-cam={cam}>
        <video ref={vid} muted playsInline />
        <span className="fa-frame" aria-hidden><i /><i /><i /><i /><span className="fa-laser" /></span>
        {cam === "none" && (
          // eslint-disable-next-line @next/next/no-img-element -- the parcel's own label, from the tunnel's photo: what to point at
          <img className="fa-vf-label" src={`/scanner/${waybill}.jpg`} alt="" aria-hidden />
        )}
        <span className="fa-vf-hint">{cam === "none" ? "No camera on this device: type the last 4 digits below" : "Point at the barcode on the label"}</span>
      </div>
      {miss && <p className="fa-miss" role="status">That label is {miss}, another parcel. Keep looking for …{waybill.slice(-4)}.</p>}
      {typing || cam === "none" ? (
        <label className="fa-type">
          <span className="fa-k">Last 4 digits of the label</span>
          <input inputMode="numeric" pattern="[0-9]*" maxLength={4} autoFocus value={typed} onChange={(e) => check(e.target.value.replace(/\D/g, ""))}
            aria-describedby="fa-type-h" />
          <span id="fa-type-h" className="fa-type-h">Looking for …{waybill.slice(-4)}</span>
        </label>
      ) : <button type="button" className="fa-link" onClick={() => setTyping(true)}>Type the number instead</button>}
    </div>
  );
}

function Photo() {
  const [url, setUrl] = useState<string | null>(null);
  return (
    <label className="fa-photo">
      <input type="file" accept="image/*" capture="environment" onChange={(e) => { const f = e.target.files?.[0]; if (f) setUrl(URL.createObjectURL(f)); }} />
      {/* eslint-disable-next-line @next/next/no-img-element -- the worker's own photo, on the phone */}
      {url ? <img src={url} alt="Your photo of the parcel" /> : <><svg viewBox="0 0 24 24" aria-hidden><path d="M4 8h3l2-3h6l2 3h3v11H4z" /><circle cx="12" cy="13" r="3.5" /></svg>Add a photo</>}
    </label>
  );
}

/** Hold to talk: a live waveform and timer while held; on release Muse Voice Transcribe writes it out, the worker can edit
 *  it, and it is attached to the answer only on "Use this note". Malay or English (the language is shown). */
function VoiceHold({ caseId, taskId, areaId, used, onUse, compact = false }: { caseId: string; taskId: string; areaId: string;
  used: string | null; onUse: (t: string | null) => void; compact?: boolean }) {
  const voice = useResource<{ available: boolean }>(`/v1/cases/${caseId}/voice`);
  const [state, setState] = useState<"idle" | "rec" | "send" | "text">("idle");
  const [text, setText] = useState("");
  const [secs, setSecs] = useState(0);
  const [bars, setBars] = useState<number[]>(Array(24).fill(0.08));
  const rec = useRef<MediaRecorder | null>(null);
  const t0 = useRef(0);
  const ok = voice.data?.available ?? false;
  const lang = /\b(tak|tiada|ada|dah|sudah|kotak|rak|sini|saya|barang|dalam|lantai|bawah|jumpa|belum|tengok)\b/i.test(text) ? "Malay" : "English";
  async function down(e: React.PointerEvent) {
    if (!ok || state === "rec" || state === "send") return;
    e.currentTarget.setPointerCapture(e.pointerId);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const ctx = new AudioContext(); const an = ctx.createAnalyser(); an.fftSize = 64;
      ctx.createMediaStreamSource(stream).connect(an);
      const buf = new Uint8Array(an.frequencyBinCount);
      const chunks: Blob[] = [];
      const r = new MediaRecorder(stream);
      r.ondataavailable = (ev) => chunks.push(ev.data);
      let raf = 0;
      const draw = () => {
        an.getByteFrequencyData(buf);
        setBars(Array.from({ length: 24 }, (_, i) => Math.max(0.08, buf[i % buf.length] / 255)));
        setSecs((performance.now() - t0.current) / 1000);
        raf = requestAnimationFrame(draw);
      };
      r.onstop = async () => {
        cancelAnimationFrame(raf); stream.getTracks().forEach((t) => t.stop()); void ctx.close();
        setState("send");
        const fd = new FormData();
        fd.append("file", await toWav16k(new Blob(chunks, { type: r.mimeType })), "note.wav");
        fd.append("kind", "search_note"); fd.append("search_task_id", taskId); fd.append("area_id", areaId);
        try {
          const out = await api<{ transcript: string }>(`/v1/cases/${caseId}/voice`, { method: "POST", body: fd });
          setText(out.transcript || ""); setState("text"); invalidate(`/v1/cases/${caseId}/voice`);
        } catch { setState("idle"); }
      };
      rec.current = r; t0.current = performance.now(); r.start(); setState("rec"); buzz(8); draw();
    } catch { setState("idle"); }
  }
  const up = () => { if (state === "rec") { buzz(8); rec.current?.stop(); } };
  if (used) {
    return (
      <div className="fa-note-used">
        <span className="fa-k">Voice note attached</span>
        <p>“{used}”</p>
        <button type="button" className="fa-link" onClick={() => { onUse(null); setState("idle"); }}>Remove</button>
      </div>
    );
  }
  return (
    <div className="fa-voice" data-compact={compact ? "" : undefined} data-state={state}>
      {state === "text" ? (
        <div className="fa-note">
          <div className="fa-note-head"><span className="fa-k">Your note</span><span className="fa-chip" data-tone="lang">{lang}</span></div>
          <textarea value={text} onChange={(e) => setText(e.target.value)} rows={3} aria-label="Your note, edit if needed" />
          <div className="fa-two">
            <button type="button" className="fa-secondary" onClick={() => { setText(""); setState("idle"); }}>Record again</button>
            <button type="button" className="fa-primary" disabled={!text.trim()} onClick={() => { buzz(); onUse(text.trim()); }}>Use this note</button>
          </div>
        </div>
      ) : (
        <>
          <button type="button" className="fa-mic" disabled={!ok || state === "send"} onPointerDown={down} onPointerUp={up} onPointerCancel={up}
            aria-label={state === "rec" ? "Recording, let go to stop" : "Hold to record a voice note"}>
            <svg viewBox="0 0 24 24" aria-hidden><rect x="9" y="3" width="6" height="11" rx="3" /><path d="M5.5 11a6.5 6.5 0 0 0 13 0M12 17.5V21" /></svg>
          </button>
          <div className="fa-voice-side">
            {state === "rec" ? (
              <>
                <span className="fa-wave" aria-hidden>{bars.map((b, i) => <i key={i} style={{ transform: `scaleY(${b})` }} />)}</span>
                <span className="fa-timer">{Math.floor(secs / 60)}:{String(Math.floor(secs % 60)).padStart(2, "0")} · let go to stop</span>
              </>
            ) : state === "send" ? <span className="fa-voice-t">Writing it out…</span> : (
              <>
                <span className="fa-voice-t">{ok ? "Hold to talk" : "Voice notes are off on this hub"}</span>
                <span className="fa-voice-s">{ok ? "Malay or English. Nothing is sent until you tap Use." : "Ask the supervisor to switch them on"}</span>
              </>
            )}
          </div>
        </>
      )}
    </div>
  );
}

/** Not here: why, in one tap. A bottom sheet that rises from the bar it was opened from and can be dragged down. */
function ReasonSheet({ open, onClose, onSend, busy }: { open: boolean; onClose: () => void; onSend: (r: string) => void; busy: boolean }) {
  const reasons = ["Checked shelves, floor and cages", "Store locked, could not get in", "Found a different parcel", "Area blocked by a forklift or pallets"];
  const [pick, setPick] = useState<string | null>(null);
  const [dy, setDy] = useState(0);
  const drag = useRef<{ y: number; t: number; last: number } | null>(null);
  const close = () => { setPick(null); setDy(0); onClose(); };
  return (
    <div className="fa-sheet-wrap" data-open={open ? "" : undefined} aria-hidden={!open} inert={!open}>
      <button type="button" className="fa-scrim" aria-label="Close" onClick={close} tabIndex={-1} />
      <div className="fa-sheet" role="dialog" aria-label="Why not here" style={dy ? { transform: `translateY(${dy}px)`, transition: "none" } : undefined}>
        <div className="fa-grab" onPointerDown={(e) => { e.currentTarget.setPointerCapture(e.pointerId); drag.current = { y: e.clientY, t: performance.now(), last: e.clientY }; }}
          onPointerMove={(e) => { if (!drag.current) return; const d = e.clientY - drag.current.y; setDy(d > 0 ? d : d / 4); drag.current.last = e.clientY; }}
          onPointerUp={(e) => {
            if (!drag.current) return;
            const v = (e.clientY - drag.current.y) / Math.max(1, performance.now() - drag.current.t);
            drag.current = null;
            if (dy > 120 || v > 0.6) close(); else setDy(0);
          }}><i /></div>
        <h2 className="fa-h2">Not here. What did you find?</h2>
        <div className="fa-reasons" role="radiogroup">
          {reasons.map((r) => (
            <button key={r} type="button" role="radio" aria-checked={pick === r} onClick={() => { buzz(8); setPick(r); }}>
              <span className="fa-radio" aria-hidden />{r}
            </button>
          ))}
        </div>
        <button type="button" className="fa-primary" disabled={!pick || busy} onClick={() => { if (pick) { setPick(null); onSend(pick); } }}>{busy ? "Sending" : "Send, check the next place"}</button>
      </div>
    </div>
  );
}

/** After a miss: Spoor (Muse Wonder) re-plans with the check in its evidence, then the next place. */
function NextPlace({ job, more, onNext, placeName: next }: { job: string | null; more: boolean; onNext: () => void; placeName: string | null }) {
  const [state, setState] = useState<"plan" | "ready">(job ? "plan" : "ready");
  useEffect(() => {
    if (!job) return;
    let live = true;
    const tick = async () => {
      const j = await api<{ status: string }>(`/v1/jobs/${job}`).catch(() => ({ status: "failed" }));
      if (!live) return;
      if (["done", "succeeded", "failed", "error"].includes(j.status)) { setState("ready"); return; }
      window.setTimeout(tick, 1500);
    };
    void tick();
    return () => { live = false; };
  }, [job]);
  return (
    <div className="fa-pad fa-center">
      {state === "plan" ? <span className="fa-orbit" aria-hidden><i /><i /><i /></span>
        : <span className="fa-tick" aria-hidden><svg viewBox="0 0 52 52"><circle cx="26" cy="26" r="24" /><path d="M15 27l7 7 15-16" /></svg></span>}
      <h1 className="fa-h1">{state === "plan" ? "Spoor is checking the next place" : more ? "Next place ready" : "Every place checked"}</h1>
      <p className="fa-lead">{state === "plan" ? "Your answer is in the case. The cameras are being checked again with it." : more ? `Next: the ${next}.` : "The supervisor has your answers and will decide what's next."}</p>
      {state === "ready" && more && <button type="button" className="fa-primary fa-inline" onClick={onNext}>Open the next place</button>}
    </div>
  );
}
