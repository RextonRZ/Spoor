/**
 * The case's answer, in the prototype's shape: a status pill, one sentence, a plain explanation and "How sure" with up
 * to three reasons. One function, so the Answer screen and the landing page's board say exactly the same thing.
 * Everything comes from the case's read models (journey, missing moment, possible places, records conflicts, floor
 * search); in no-key mode it says what is really known.
 */
import { hms, momentLabel, placeOf, shortPlace } from "@/lib/words";

export const low = (t: string) => t.charAt(0).toLowerCase() + t.slice(1); // "Into chute C12" -> "into chute C12"
export const clean = (name: string) => name.replace(/^Z\d+ /, "").replace(/\s*\(.*$/, "");

export interface AnswerInputs {
  ready: boolean;
  last?: { event_kind: string; station_id?: string | null; t: string };
  next: { camera_id: string; predicted_t: string; result?: string | null }[];
  places: { area_id: string; name: string; zone_id?: string | null; possible_share: number }[];
  conflicts: { statement: string }[];
  found: { name: string; by: string; at: string } | null;
  zoneNames: Record<string, string>;
}

export interface Answer {
  pill: [string, string];
  head: string;
  why: string;
  level: "high" | "medium" | "low";
  reasons: { text: string; tone: "ok" | "bad" | "plain" }[];
}

export function caseAnswer({ ready, last, next, places, conflicts, found, zoneNames }: AnswerInputs): Answer {
  const withFootage = next.filter((r) => r.result !== "no_footage");
  const seen = next.filter((r) => r.result === "seen");
  let pill: [string, string] = ["Lost track", "bad"];
  let head = "Checking the records";
  let why = "";
  if (ready && found) {
    pill = ["Found", "ok"];
    head = `Found at ${low(clean(found.name))} at ${hms(found.at)}.`;
    why = `Floor staff (${found.by}) found it there during the search. The last record before that was ${last ? `${low(momentLabel(last.event_kind, last.station_id))} at ${hms(last.t)}` : "none"}.`;
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
  const level = found ? "high" : seen.length ? "medium" : "low";
  const reasons: Answer["reasons"] = [];
  if (last) reasons.push({ text: `Last scan: ${low(momentLabel(last.event_kind, last.station_id))} at ${hms(last.t)}.`, tone: "ok" });
  if (next.length) reasons.push({ text: withFootage.length
    ? `${withFootage.length} of ${next.length} cameras that would show it next have footage, not checked yet.`
    : `None of the ${next.length} cameras that would show it next has footage yet.`, tone: "plain" });
  if (conflicts.length) reasons.push({ text: `The sorter's own times don't fit the belt: ${conflicts[0].statement.replace(/: the records conflict$/, "")}.`, tone: "bad" });
  else if (places.length) reasons.push({ text: `It could be in ${places.length} place${places.length === 1 ? "" : "s"}. Most likely: ${shortPlace(places[0], zoneNames)}.`, tone: "plain" });
  return { pill, head, why, level, reasons };
}
