/** Time display. Canonical time is the backend's normalized UTC; the hub is in Malaysia, so labels show MYT. */
const TZ = "Asia/Kuala_Lumpur";

const hms = new Intl.DateTimeFormat("en-GB", {
  timeZone: TZ, hour: "2-digit", minute: "2-digit", second: "2-digit", hourCycle: "h23",
});
const dmy = new Intl.DateTimeFormat("en-GB", { timeZone: TZ, day: "2-digit", month: "short", year: "numeric" });

export function fmtTime(iso: string | number | null | undefined, withMs = true): string {
  if (iso === null || iso === undefined) return "time unknown";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "time unknown";
  const ms = String(d.getUTCMilliseconds()).padStart(3, "0");
  return withMs ? `${hms.format(d)}.${ms}` : hms.format(d);
}

export function fmtDate(iso: string | number | null | undefined): string {
  if (iso === null || iso === undefined) return "date unknown";
  return dmy.format(new Date(iso));
}

export function fmtDuration(ms: number): string {
  const s = Math.abs(ms) / 1000;
  if (s < 1) return `${Math.round(Math.abs(ms))} ms`;
  if (s < 60) return `${s.toFixed(s < 10 ? 1 : 0)} s`;
  const m = Math.floor(s / 60);
  return `${m} min ${Math.round(s - m * 60)} s`;
}

export function fmtUncertainty(ms: number | null | undefined): string {
  if (ms === null || ms === undefined) return "clock not synchronized";
  return `± ${fmtDuration(ms)}`;
}

export const toMs = (iso: string) => Date.parse(iso);

export const TZ_LABEL = "MYT";
