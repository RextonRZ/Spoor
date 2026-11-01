/**
 * A records conflict (GET /conflicts) in plain words, by its kind. "custody": the records put the parcel in a container
 * (a cage, a bag) while a camera saw it somewhere else; "timing" (and older kinds): the sorter's own times don't fit
 * the belt. One function for the Answer, Proof and Report, so they always say the same thing.
 */
import { hms } from "./words";
import { ZONE_NAMES } from "./zones";

export interface Conflict {
  kind?: string;
  divergence_t: string;
  statement: string;
  claim?: { t?: string; zone_id?: string | null; words?: string; evidence_ids?: string[] };
  observation?: { t?: string; camera_id?: string; zone_id?: string | null };
}

const place = (zone?: string | null) => (zone ? (ZONE_NAMES[zone.replace(/^zone_/, "")] ?? zone).replace(/^Z\d+ /, "") : "another place");
const cam = (c?: string) => (c ?? "").replace(/^cam_/, "").replace("_", " ");

export function conflictWords(c: Conflict): { short: string; headline: string; body: string } {
  if (c.kind === "custody") {
    const box = c.claim?.words?.match(/^(\S+) container/)?.[1] ?? "a container";
    const where = place(c.observation?.zone_id);
    return {
      short: `records say it was in ${box}; ${cam(c.observation?.camera_id)} saw it at the ${where.toLowerCase()}`,
      headline: `The records say it was in ${box}. The cameras saw it at the ${where.toLowerCase()}.`,
      body: `It was scanned into ${box} at ${c.claim?.t ? hms(c.claim.t) : "an earlier time"}, but ${cam(c.observation?.camera_id)} saw it at the `
        + `${where.toLowerCase()} at ${hms(c.divergence_t)}, outside the cage.`,
    };
  }
  return {
    short: "the sorter's times don't fit the belt",
    headline: "The sorter's times don't fit the belt.",
    body: `${c.statement.replace(/: the records conflict$/, "")}. One of these records is wrong, or the parcel didn't travel on the belt.`,
  };
}
