/**
 * Supervisor words for scan facts (design_sprint §D): short sentences, the place and the minute, no device jargon.
 * The same sentence appears on the Hub, the Answer and the Report. Evidence details keep the exact records.
 */
import { clock } from "./journey";

/** "14:33" (MYT is implied on screen; the full time stays in Evidence details). */
export const hhmm = (iso: string) => clock(iso, false).slice(0, 5);

const chuteOf = (point: string | null | undefined) => point?.match(/C\d{2}/)?.[0] ?? null;

/** What the last scan says, as one sentence: "Went into chute C07 at 14:29." */
export function lastScanSentence(kind: string, point: string | null | undefined, at: string): string {
  const t = hhmm(at);
  switch (kind) {
    case "tunnel_read": return `Read at the scan tunnel at ${t}.`;
    case "tunnel_no_read": return `Passed the scan tunnel unread at ${t}.`;
    case "inducted": case "induct_to_carrier": return `Loaded onto the sorter at ${t}.`;
    case "recirculated": return `Went round the sorter again at ${t}.`;
    case "divert_confirmed": case "divert_confirm": return `Went into chute ${chuteOf(point) ?? ""} at ${t}.`.replace("chute  at", "a chute at");
    case "exception_diverted": return `Sent to the reject chute at ${t}.`;
    case "bagged": case "bag_scan": return `Bagged at ${t}.`;
    case "container_add": return `Put in a cage at ${t}.`;
    case "container_loaded": case "departed_facility": return `Left on a truck at ${t}.`;
    case "arrived_facility": return `Arrived at the hub at ${t}.`;
    default: return `Last scanned at ${t}.`;
  }
}

/** What should have happened next and didn't: "No bag scan since." */
export function missingNextSentence(kind: string): string {
  switch (kind) {
    case "tunnel_read": case "tunnel_no_read": return "Never loaded onto the sorter.";
    case "inducted": case "induct_to_carrier": case "recirculated": return "Never sorted into a chute.";
    case "divert_confirmed": case "divert_confirm": return "No bag scan since.";
    case "exception_diverted": return "Not handled at the exception bench since.";
    case "bagged": case "bag_scan": case "container_add": return "Not loaded onto a truck since.";
    case "arrived_facility": return "Never read at the scan tunnel.";
    default: return "No scan since.";
  }
}

/** "18 min", "2.4 h" */
export const minutes = (s: number) => (s < 5400 ? `${Math.max(1, Math.round(s / 60))} min` : `${(s / 3600).toFixed(1)} h`);

/** A scan as a short moment label for the Answer timeline: "Into chute C12". */
export function momentLabel(kind: string, point: string | null | undefined): string {
  const chute = point?.match(/C\d{2}/)?.[0];
  switch (kind) {
    case "tunnel_read": return "Label read at the tunnel";
    case "tunnel_no_read": return "Passed the tunnel unread";
    case "inducted": case "induct_to_carrier": return "On the sorter";
    case "recirculated": return "Round the sorter again";
    case "divert_confirmed": case "divert_confirm": return chute ? `Into chute ${chute}` : "Into a chute";
    case "exception_diverted": return "Into the reject chute";
    case "bagged": case "bag_scan": return "Bagged";
    case "container_add": return "Into a cage";
    case "container_loaded": case "departed_facility": return "Onto a truck";
    case "arrived_facility": return "Unloaded";
    default: return "Scanned";
  }
}

/** "chute C12" / "the scan tunnel": where a scan happened, for sentences. */
export function placeOf(kind: string, point: string | null | undefined): string {
  const chute = point?.match(/C\d{2}/)?.[0];
  switch (kind) {
    case "tunnel_read": case "tunnel_no_read": return "the scan tunnel";
    case "inducted": case "induct_to_carrier": case "recirculated": return "the sorter";
    case "divert_confirmed": case "divert_confirm": return chute ? `chute ${chute}` : "a chute";
    case "exception_diverted": return "the reject chute";
    case "container_add": return "a cage";
    case "container_loaded": case "departed_facility": return "the dock";
    case "arrived_facility": return "the unloading door";
    default: return point ?? "the last scanner";
  }
}

/** "14:32:38" in Malaysia Time. */
export const hms = (iso: string) => new Date(iso).toLocaleTimeString("en-GB", { timeZone: "Asia/Kuala_Lumpur", hour12: false });

/** A possible place in a few words: the zone's short name ("exception store"), or "blind corner, exception store". */
export function shortPlace(p: { area_id: string; name: string; zone_id?: string | null }, zoneNames: Record<string, string>): string {
  const zone = p.zone_id ? zoneNames[p.zone_id.replace(/^zone_/, "")] : undefined;
  const base = zone ?? p.name.replace(/^Z\d+ /, "").replace(/\s*[(,;].*$/, "");
  const lower = base.charAt(0).toLowerCase() + base.slice(1);
  return p.area_id.startsWith("BLIND") ? `blind corner, ${lower}` : lower;
}
