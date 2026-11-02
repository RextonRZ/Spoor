/**
 * The case's answer, in the prototype's shape: a status pill, one sentence, a plain explanation and "How sure" with up
 * to three reasons. One function, so the Answer screen and the landing page's board say exactly the same thing.
 * Everything comes from the case's read models (journey, missing moment, possible places, records conflicts, floor
 * search); in no-key mode it says what is really known.
 */
import { hms, momentLabel, placeOf, shortPlace } from "@/lib/words";
import { conflictWords, type Conflict } from "@/lib/conflict";

export const low = (t: string) => t.charAt(0).toLowerCase() + t.slice(1); // "Into chute C12" -> "into chute C12"
export const clean = (name: string) => name.replace(/^Z\d+ /, "").replace(/\s*\(.*$/, "");

export interface AnswerInputs {
  ready: boolean;
  last?: { event_kind: string; station_id?: string | null; t: string };
  next: { camera_id: string; predicted_t: string; result?: string | null }[];
  places: { area_id: string; name: string; zone_id?: string | null; possible_share: number }[];
  conflicts: Conflict[];
  found: { name: string; by: string; at: string } | null;
  /** the investigation's last scan record for a parcel never followed on camera (and whether a camera met it there) */
  lastScan?: LastScan | null;
  zoneNames: Record<string, string>;
}

export interface Answer {
  pill: [string, string];
  head: string;
  why: string;
  level: "high" | "medium" | "low";
  reasons: { text: string; tone: "ok" | "bad" | "plain" }[];
}

export function caseAnswer({ ready, last, next, places, conflicts, found, zoneNames, lastScan }: AnswerInputs): Answer {
  const withFootage = next.filter((r) => r.result !== "no_footage");
  const seen = next.filter((r) => r.result === "seen");
  let pill: [string, string] = ready ? ["Lost track", "bad"] : ["Checking", "plain"]; // never a verdict before the data
  let head = "Checking the records";
  let why = "";
  if (ready && found) {
    pill = ["Found", "ok"];
    head = `Found at ${low(clean(found.name))} at ${hms(found.at)}.`;
    why = `Floor staff (${found.by}) found it there during the search. The last record before that was ${last ? `${low(momentLabel(last.event_kind, last.station_id))} at ${hms(last.t)}` : "none"}.`;
  } else if (ready && lastScan) {
    // located by its last scan record: counted apart from "confirmed on camera" (a labelled handshake met it there)
    const what = low(momentLabel(lastScan.event_kind, lastScan.scan_point_id));
    const cam = lastScan.camera?.replace(/^cam_/, "").replaceAll("_", " ");
    pill = cam ? ["Confirmed on camera", "ok"] : ["Located by scan", "plain"];
    head = `Last scan record: ${what} at ${hms(lastScan.at)}.`;
    why = cam ? `${cam} saw this carton there at that scan. Nothing records it after that.`
      : "Not seen on camera. The scanner put it there; no camera confirmed it, and nothing records it after that.";
  } else if (ready && seen.length) {
    pill = ["Likely location found", "ok"];
    head = `Seen on ${seen[0].camera_id.replace("cam_", "").replace("_", " ")} at ${hms(seen[0].predicted_t)}.`;
    why = "A camera that should show it next did. Watch the proof to see the frame.";
  } else if (ready && last) {
    head = `Lost track after ${placeOf(last.event_kind, last.station_id)} at ${hms(last.t)}.`;
    why = `The last record is ${low(momentLabel(last.event_kind, last.station_id))} at ${hms(last.t)}. ${withFootage.length
      ? "The cameras that would show where it went next have footage that hasn't been checked yet."
      : "None of the cameras that would show where it went next has footage yet, so nothing after that is confirmed."}`;
  } else if (ready) {
    head = "No scans of this parcel at this hub.";
  }
  const level = found ? "high" : seen.length || lastScan?.camera ? "medium" : "low";
  const reasons: Answer["reasons"] = [];
  if (last) reasons.push({ text: `Last scan: ${low(momentLabel(last.event_kind, last.station_id))} at ${hms(last.t)}.`, tone: "ok" });
  if (next.length) reasons.push({ text: withFootage.length
    ? `${withFootage.length} of ${next.length} cameras that would show it next have footage, not checked yet.`
    : `None of the ${next.length} cameras that would show it next has footage yet.`, tone: "plain" });
  if (conflicts.length) reasons.push({ text: conflictWords(conflicts[0]).body, tone: "bad" });
  else if (places.length) reasons.push({ text: `It could be in ${places.length} place${places.length === 1 ? "" : "s"}. Most likely: ${shortPlace(places[0], zoneNames)}.`, tone: "plain" });
  return { pill, head, why, level, reasons };
}

export interface LastScan { event_kind: string; at: string; scan_point_id: string; zone_id: string | null; container: string | null;
  located_by: "scan" | "camera"; camera: string | null }

/** The last investigation's answer (GET /state "answer"): the verifier's facts apart from the agents' own words. */
export interface InsideFacts {
  place: string; door_at: string; camera: string; carried_in_at: string; came_out_empty: string[]; until: string;
  observation_id: string; area_xy: [number, number]; media_id: string; door_xy: [number, number];
  area_polygon: [number, number][]; iso: Record<string, string>; trail_px: number[][]; box_px: number[]; frame_wh_px: number[];
  /** every box SAM drew on that track: [video ms, x1, y1, x2, y2] */
  track_px: number[][]; door_pts_ms: number;
}
export interface InvestigationView {
  status: string;
  objects: { label: string; most_likely: string | null; inside: InsideFacts | null; last_seen: string; left_area: string;
    last_scan?: LastScan | null }[];
  verified: string[];
  hypotheses: { status: string; agent_wording: string; verified: string[]; tested?: { kind: string; check: string; verdict: string }[] }[];
}

/** a hypothesis's status is about its claims, never its wording */
export const HYPOTHESIS_WORDS: Record<string, string> = { supported: "Passed", contradicted: "Ruled out", insufficient_evidence: "Unproven",
  proposed: "Not checked" };
