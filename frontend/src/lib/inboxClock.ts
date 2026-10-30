/**
 * The exceptions inbox clock (F-style-b review #4), set in Operator and read by the Hub page. Per browser (a demo and
 * replay control, not a record): "log" = the last imported scan + N minutes; "now" = the server clock (live mode).
 */
export type InboxClock = { kind: "log"; minutes: number } | { kind: "now" };
const KEY = "spoor-inbox-clock";

export function readInboxClock(): InboxClock {
  try {
    const v = JSON.parse(localStorage.getItem(KEY) ?? "null");
    if (v?.kind === "now") return { kind: "now" };
    if (v?.kind === "log" && Number.isFinite(v.minutes)) return { kind: "log", minutes: v.minutes };
  } catch { /* storage unavailable */ }
  return { kind: "log", minutes: 0 };
}

export function writeInboxClock(c: InboxClock) {
  try { localStorage.setItem(KEY, JSON.stringify(c)); } catch { /* storage unavailable */ }
}

export const inboxQuery = (c: InboxClock) => (c.kind === "now" ? "now_clock=true" : `after_log_min=${c.minutes}`);
export const inboxClockWords = (c: InboxClock) =>
  c.kind === "now" ? "live: server clock" : c.minutes ? `${c.minutes} min after the last imported scan` : "the last imported scan";
