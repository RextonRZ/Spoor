/**
 * Forensic journey read models (backend QUEUE I2 /journey and I3 /missing-moment) and the plain words the case summary
 * (H14) builds from them. The backend types every segment; this file only words it. Nothing here invents evidence:
 * when the backend says unknown, the words say unknown.
 */
import { describeScan, type ScanLike } from "./scans";
import { camId } from "./hub";
import { fmtDate, fmtTime, TZ_LABEL } from "./time";

export type XY = [number, number];

export interface JourneyScan extends ScanLike {
  scan_event_id: string;
  t: string;
  xy: XY | null;
  on_conveyor: string | null;
  zone_id: string | null;
  device_kind: string;
  clock: { synchronized: boolean; uncertainty_ms: number | null; late_upload: boolean; clock_domain_id: string | null };
  clock_domain: string | null;
  weight_g: number | null;
  dims_mm: [number, number, number] | null;
  /** the chute the sorter assigned at the scan tunnel (DWS), and the container a container scan put it in */
  sort_destination_assigned?: string | null;
  sort_destination_actual?: string | null;
  container?: string | null;
  raw_description?: string | null;
  read_outcome?: string;
  source_type?: string;
}

export interface ObservedSegment {
  kind: "observed";
  start: string;
  end: string;
  camera_id: string;
  track_id: string;
  points: { t: string; observation_id: string; xy: XY | null; zone_id?: string | null }[];
  evidence_ids: string[];
}

export interface InferredSegment {
  kind: "inferred_along_conveyor";
  start: string;
  end: string;
  from: string;
  to: string;
  evidence_ids: string[];
  route: string[];
  path_m: XY[];
  length_m: number;
  belt_time_s: number;
  recorded_gap_s: number;
  slack_s: number;
  timing: "consistent" | "longer_than_belt" | "not_checkable";
  clock_note: string;
  note: string;
}

export interface GapSegment {
  kind: "gap";
  start: string;
  end: string;
  reason: "unobserved" | "no_belt_route" | "faster_than_belt" | "after_last_confirmed";
  note: string;
  covering_camera_ids: string[];
  after: string | null;
  before: string | null;
  evidence_ids: string[];
}

export type Segment = ObservedSegment | InferredSegment | GapSegment;

export interface LastConfirmed {
  kind: "scan" | "observation";
  evidence_id: string;
  t: string;
  xy: XY | null;
  camera_id: string | null;
  on_conveyor: string | null;
  station_id: string | null;
  event_kind: string | null;
}

export interface JourneyObject {
  object_instance_id: string;
  label: string;
  identity_keys: string[];
  scans: JourneyScan[];
  segments: Segment[];
  observed_segments: number;
  last_confirmed: LastConfirmed | null;
}

export interface Journey {
  case_id: string;
  plan_id: string | null;
  contract: string;
  needs: string[];
  objects: JourneyObject[];
}

export interface FrameRef {
  camera_id: string;
  media_id: string;
  frame_index: number;
  frame_url: string;
  sha256: string;
  time_uncertainty_ms?: number;
  role?: "last_sighting" | "context_at_scan_time";
}

export type ExpectedResult = "seen" | "not_seen" | "unresolved_candidates" | "not_analysed" | "no_footage";

export interface ExpectedNext {
  camera_id: string;
  camera_name: string;
  role: "watching_last_point" | "belt_next" | "on_foot_next";
  window: { start: string; end: string };
  predicted_t: string;
  how: string;
  expected_xy: XY;
  expected_region_px: [number, number, number, number] | null;
  region_basis_wh_px: [number, number] | null;
  region_note: string;
  frame: FrameRef | null;
  result: ExpectedResult;
  needs?: string;
  candidate_track_ids?: string[];
  negative_observation?: { window: { start: string; end: string }; frame_indices: number[]; basis: string };
}

export interface MissingObject {
  object_instance_id: string;
  label?: string;
  last_confirmed: (LastConfirmed & { frames?: FrameRef[] }) | null;
  expected_next: ExpectedNext[];
  note?: string;
}

export interface MissingMoment {
  case_id: string;
  plan_id: string | null;
  objects: MissingObject[];
  needs: string[];
}

export const RESULT_WORDS: Record<ExpectedResult, string> = {
  seen: "seen",
  not_seen: "not seen",
  unresolved_candidates: "something tracked, identity open",
  not_analysed: "not analysed yet",
  no_footage: "no footage",
};

export const ROLE_WORDS: Record<ExpectedNext["role"], string> = {
  watching_last_point: "watching the last point",
  belt_next: "next on the belt",
  on_foot_next: "next on foot",
};

export const cam = (id: string | null | undefined) => camId.toHub(id);

/** Cameras in play (indigo in 2D and 3D): the ones the investigator lit plus the ones due next that have footage. */
export const inPlayCameras = (lit: string[], mm: MissingObject | undefined) =>
  [...new Set([...lit, ...(mm?.expected_next ?? []).filter((r) => r.result !== "no_footage").map((r) => cam(r.camera_id))])];
/** "14:32:31.8 MYT": tenths of a second, like the scan log (ms = false drops the fraction). */
export const clock = (iso: string, ms = false) => `${ms ? fmtTime(iso, true).slice(0, -2) : fmtTime(iso, false)} ${TZ_LABEL}`;

/** Status chip of a case summary. Never "stolen": a status says where the evidence stands, not who did what. */
export type CaseStatus = "found" | "located" | "unknown";

export function caseStatus(j: JourneyObject | undefined): CaseStatus {
  // Found = a recorded floor search found it (I7); Located = the computed possible area collapsed to one place (I4).
  // Neither exists yet for any case, so every case is honestly "unknown" until those records exist.
  void j;
  return "unknown";
}

/** "sorter divert to C04 at 14:32:31.8 MYT" for the last confirmed point. */
export function lastConfirmedWords(j: JourneyObject): string | null {
  const last = j.last_confirmed;
  if (!last) return null;
  if (last.kind === "scan") {
    const s = j.scans.find((x) => x.scan_event_id === last.evidence_id);
    return s ? `${describeScan(s).title} at ${clock(last.t, true)}` : `a scan at ${clock(last.t, true)}`;
  }
  return `seen on ${cam(last.camera_id)} at ${clock(last.t, true)}`;
}

/** The one-sentence answer, built only from typed evidence. */
export function answerSentence(j: JourneyObject | undefined, mm: MissingObject | undefined): string {
  if (!j || !j.last_confirmed) return "Nothing about this consignment has been confirmed yet: no scan and no camera sighting.";
  const lc = lastConfirmedWords(j)!;
  const next = mm?.expected_next ?? [];
  const pending = next.filter((r) => r.result === "not_analysed");
  const notSeen = next.filter((r) => r.result === "not_seen");
  let after = "Where it went next is not shown by any evidence yet.";
  if (notSeen.length) after = `It did not reach ${listCams(notSeen)} when expected.`;
  else if (pending.length) after = `Where it went next is not shown yet: the ${pending.length === 1 ? "camera" : "cameras"} ` +
    `watching that moment (${listCams(pending)}) ${pending.length === 1 ? "has" : "have"} not been analysed.`;
  return `Last confirmed: ${lc}. ${after}`;
}

export function listCams(rows: { camera_id: string }[]): string {
  const ids = rows.map((r) => cam(r.camera_id));
  return ids.length <= 2 ? ids.join(" and ") : `${ids.slice(0, -1).join(", ")} and ${ids[ids.length - 1]}`;
}

/** "3 scans, all consistent with the belt route on the same sorter clock" style confidence words. */
export function confidenceWords(j: JourneyObject | undefined): string[] {
  if (!j) return [];
  const inferred = j.segments.filter((s): s is InferredSegment => s.kind === "inferred_along_conveyor");
  const conflicts = j.segments.filter((s): s is GapSegment => s.kind === "gap" && s.reason === "faster_than_belt");
  const out = [`${j.scans.length} scan${j.scans.length === 1 ? "" : "s"} of this waybill.`];
  if (inferred.length) {
    const ok = inferred.filter((s) => s.timing === "consistent").length;
    out.push(`${ok} of ${inferred.length} belt stretches between scans match the belt speed` +
      `${ok ? ` (${inferred.find((s) => s.timing === "consistent")?.clock_note})` : ""}.`);
  }
  if (conflicts.length) out.push(`${conflicts.length} pair${conflicts.length === 1 ? "" : "s"} of scans are faster than the belt allows: the records disagree.`);
  out.push(j.observed_segments ? `${j.observed_segments} camera track${j.observed_segments === 1 ? "" : "s"} confirmed.`
    : "No camera track confirmed yet: the footage has not been analysed.");
  return out;
}

/** The next action, in a supervisor's words, from the missing moment. */
export function nextAction(mm: MissingObject | undefined): { text: string; detail: string } | null {
  const rows = mm?.expected_next ?? [];
  const todo = rows.filter((r) => r.result === "not_analysed");
  if (todo.length) {
    const w = todo[0].window;
    return { text: `Review ${listCams(todo)} from ${clock(w.start, true).replace(" MYT", "")} to ${clock(w.end, true)}`,
      detail: "The cameras watching the last confirmed moment. Automatic tracking needs object tracking (SAM)." };
  }
  const open = rows.filter((r) => r.result === "unresolved_candidates");
  if (open.length) return { text: `Decide which track on ${listCams(open)} is this parcel`, detail: "Something was tracked where it should be." };
  return null;
}

export function openFor(createdAt: string, now = Date.now()): string {
  const h = Math.max(0, (now - Date.parse(createdAt)) / 3.6e6);
  if (h < 1) return `${Math.round(h * 60)} min`;
  if (h < 48) return `${h.toFixed(h < 10 ? 1 : 0)} h`;
  return `${Math.round(h / 24)} days`;
}

export const openedOn = (iso: string) => `${fmtDate(iso)}, ${fmtTime(iso, false)} ${TZ_LABEL}`;

/** Where the replay marker sits at time t, and on what evidence. Never a position inside a gap. */
export interface MarkerAt {
  xy: XY | null;
  kind: "observed" | "inferred" | "scan" | "unknown" | "before";
  label: string;
  since?: string; // for unknown: the time the trail ended
}

function along(path: XY[], f: number): XY {
  const segs = path.slice(1).map((p, i) => Math.hypot(p[0] - path[i][0], p[1] - path[i][1]));
  const total = segs.reduce((a, b) => a + b, 0);
  let d = Math.max(0, Math.min(1, f)) * total;
  for (let i = 0; i < segs.length; i++) {
    if (d <= segs[i] || i === segs.length - 1) {
      const k = segs[i] ? Math.min(1, d / segs[i]) : 0;
      return [path[i][0] + k * (path[i + 1][0] - path[i][0]), path[i][1] + k * (path[i + 1][1] - path[i][1])];
    }
    d -= segs[i];
  }
  return path[path.length - 1];
}

export function markerAt(j: JourneyObject | undefined, t: number): MarkerAt {
  if (!j || !j.scans.length && !j.observed_segments) return { xy: null, kind: "unknown", label: "no evidence yet" };
  const first = Math.min(...j.segments.map((s) => Date.parse(s.start)), ...j.scans.map((s) => Date.parse(s.t)));
  if (t < first) return { xy: null, kind: "before", label: "before the first evidence" };
  const near = j.scans.find((s) => s.xy && Math.abs(Date.parse(s.t) - t) < 250);
  if (near) return { xy: near.xy, kind: "scan", label: `scan at ${clock(near.t, true)}` };
  for (const s of j.segments) {
    const a = Date.parse(s.start);
    const b = Date.parse(s.end);
    if (t < a || t > b) continue;
    if (s.kind === "observed") {
      const pts = s.points.filter((p) => p.xy);
      const p = pts.reduce((best, x) => Math.abs(Date.parse(x.t) - t) < Math.abs(Date.parse(best.t) - t) ? x : best, pts[0]);
      if (p) return { xy: p.xy, kind: "observed", label: `seen on ${cam(s.camera_id)}` };
    }
    if (s.kind === "inferred_along_conveyor" && s.path_m.length > 1) {
      return { xy: along(s.path_m, b > a ? (t - a) / (b - a) : 1), kind: "inferred",
        label: "inferred position on the belt route (not seen)" };
    }
    if (s.kind === "gap") return { xy: null, kind: "unknown", label: "unknown: no evidence here", since: s.start };
  }
  const last = j.last_confirmed;
  return last && t > Date.parse(last.t) ? { xy: null, kind: "unknown", label: "unknown after the last confirmed point", since: last.t }
    : { xy: null, kind: "unknown", label: "unknown" };
}

/** Short headline + one sub-line (review F-style #9): "Last confirmed at chute C04 · 14:32:31.8 MYT". */
export function answerParts(j: JourneyObject | undefined, mm: MissingObject | undefined): { head: string; sub: string } {
  if (!j || !j.last_confirmed) return { head: "Nothing confirmed yet", sub: "No scan and no camera sighting of this consignment." };
  const last = j.last_confirmed;
  const s = last.kind === "scan" ? j.scans.find((x) => x.scan_event_id === last.evidence_id) : undefined;
  const chute = s?.sort_destination_actual ?? s?.station_id?.match(/^SP-DIV-(\w+)/)?.[1];
  const where = last.kind === "observation" ? `on ${cam(last.camera_id)}`
    : chute ? `at chute ${chute}` : s ? `at ${describeScan(s).title.replace(/ at .*$/, "")}` : "at a scan";
  const head = `Last confirmed ${where} · ${clock(last.t, true)}`;
  const next = mm?.expected_next ?? [];
  const pending = next.filter((r) => r.result === "not_analysed");
  const notSeen = next.filter((r) => r.result === "not_seen");
  const sub = notSeen.length ? `It did not reach ${listCams(notSeen)} when expected.`
    : pending.length ? `Where it went next isn't shown yet: ${listCams(pending)} ${pending.length === 1 ? "hasn't" : "haven't"} been analysed.`
    : "Where it went next isn't shown by any evidence yet.";
  return { head, sub };
}

/** The unknowns in 2-3 plain sentences (review F-style #6: one set of words on every screen). */
export function unknownSentences(j: JourneyObject | undefined, mm: MissingObject | undefined, sam: boolean): string[] {
  if (!j) return [];
  const out: string[] = [];
  if (j.last_confirmed) out.push(`Nothing confirms where it went after ${clock(j.last_confirmed.t, true)}.`);
  if (!j.observed_segments) out.push(sam ? "No camera track is linked to it yet." : "The footage has not been analysed: tracking needs SAM.");
  if (j.scans.length && j.scans.every((s) => !s.clock.synchronized)) out.push("Scan times are the scanners' own clocks, not yet synchronized with the cameras.");
  void mm;
  return out.slice(0, 3);
}

export interface PossibleStep { t: string; seconds_after: number; area_m2: number; polygons: XY[][]; removed_by_cameras: string[];
  identity_open_on: string[] }
export interface PossiblePlace { area_id: string; name: string; kind: string; zone_id: string | null; possible_share: number;
  reach_m: number | null; covered_by: string[]; evidence_for: string[]; evidence_against: string[]; centroid_xy: XY;
  last_confirmed_here: boolean }
export interface Possible { case_id: string; label: string; objects: { object_instance_id: string; steps: PossibleStep[];
  places: PossiblePlace[]; note: string | null; from?: { t: string } }[] }

/** The cloud at time t: the last step at or before t (none before the trail ends). */
export function cloudAt(p: Possible["objects"][number] | undefined, t: number | null): PossibleStep | null {
  if (!p || t === null || !p.from || t < Date.parse(p.from.t)) return null;
  const done = p.steps.filter((s) => Date.parse(s.t) <= t);
  return done.length ? done[done.length - 1] : null;
}
