"use client";
import type { ReactNode } from "react";
import type { ApiError } from "@/lib/api";

// --- icons: monochrome ink, 16px, only where they carry meaning ------------------------------------------------
const P = { width: 16, height: 16, viewBox: "0 0 16 16", fill: "none", stroke: "currentColor", strokeWidth: 1.5,
  strokeLinecap: "round" as const, strokeLinejoin: "round" as const, "aria-hidden": true };
export const Icon = {
  cases: () => <svg {...P}><rect x="2" y="3" width="12" height="10" rx="2" /><path d="M2 6.5h12" /></svg>,
  scene: () => <svg {...P}><path d="M8 1.8 14 5v6l-6 3.2L2 11V5z" /><path d="M2 5l6 3.2L14 5M8 8.2v6" /></svg>,
  graph: () => <svg {...P}><circle cx="3.5" cy="8" r="1.8" /><circle cx="12.5" cy="3.8" r="1.8" />
    <circle cx="12.5" cy="12.2" r="1.8" /><path d="M5.2 7.2 10.8 4.6M5.2 8.8l5.6 2.6" /></svg>,
  report: () => <svg {...P}><path d="M4 1.8h5.5L12.5 5v9.2H4z" /><path d="M9.5 1.8V5h3M6 8h4.5M6 10.8h4.5" /></svg>,
  operator: () => <svg {...P}><circle cx="8" cy="8" r="2.2" /><path d="M8 1.5v2M8 12.5v2M1.5 8h2M12.5 8h2M3.4 3.4l1.4 1.4M11.2 11.2l1.4 1.4M3.4 12.6l1.4-1.4M11.2 4.8l1.4-1.4" /></svg>,
  menu: () => <svg {...P}><path d="M2.5 4.5h11M2.5 8h11M2.5 11.5h11" /></svg>,
  collapse: () => <svg {...P}><path d="M10 3.5 5.5 8l4.5 4.5" /></svg>,
  expand: () => <svg {...P}><path d="M6 3.5 10.5 8 6 12.5" /></svg>,
  close: () => <svg {...P}><path d="M4 4l8 8M12 4l-8 8" /></svg>,
  clock: () => <svg {...P}><circle cx="8" cy="8" r="6" /><path d="M8 4.8V8l2.2 1.4" /></svg>,
  camera: () => <svg {...P}><rect x="1.8" y="4.5" width="9" height="7" rx="1.5" /><path d="m10.8 7 3.4-2v6l-3.4-2" /></svg>,
  scan: () => <svg {...P}><path d="M2 5V3h2M12 3h2v2M14 11v2h-2M4 13H2v-2M5 6v4M7.5 6v4M10 6v4" /></svg>,
  warn: () => <svg {...P}><path d="M8 2.2 14.3 13H1.7z" /><path d="M8 6.5v3M8 11.3v.1" /></svg>,
  ext: () => <svg {...P}><path d="M9 2.5h4.5V7M13.5 2.5 7.5 8.5M12 9.5v4H2.5V4h4" /></svg>,
};

export function Loading({ label = "Loading", lines = 3 }: { label?: string; lines?: number }) {
  return (
    <div role="status" aria-live="polite" className="sp-stack sp-gap-s">
      <span className="sp-sr">{label}</span>
      {Array.from({ length: lines }, (_, i) => (
        <div key={i} className="sp-skel" style={{ height: 14, width: `${92 - i * 14}%` }} />
      ))}
    </div>
  );
}

export function ErrorState({ error, onRetry, what }: { error: ApiError | Error; onRetry?: () => void; what: string }) {
  return (
    <div role="alert" className="sp-state sp-state-error">
      <span className="sp-state-title">Could not load {what}</span>
      <span className="sp-muted" style={{ fontSize: 12.5 }}>{error.message}</span>
      {onRetry && (
        <div><button className="sp-btn sp-btn-sm" onClick={onRetry}>Try again</button></div>
      )}
    </div>
  );
}

/** Honest "analysis unavailable" state: the step needs a model the backend has no key for (PRD §24.1). */
export function Unavailable({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="sp-state sp-state-unavailable" data-testid="unavailable">
      <span className="sp-state-title">{title}</span>
      {children && <span className="sp-muted" style={{ fontSize: 12.5 }}>{children}</span>}
    </div>
  );
}

export function Empty({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="sp-state">
      <span className="sp-state-title">{title}</span>
      {children && <span className="sp-muted" style={{ fontSize: 12.5 }}>{children}</span>}
    </div>
  );
}

export function SimulatedChip({ kind = "simulated" }: { kind?: string }) {
  return <span className="sp-chip sp-chip-sim" title="Generated input, labelled end to end">{kind}</span>;
}

/** Evidence legend: colour + line pattern + word, so meaning never depends on colour alone (PRD §18.1). */
export function EvidenceLegend({ compact = false }: { compact?: boolean }) {
  const items = [
    { k: "Seen", d: "inside one camera track", style: { borderTop: "3px solid var(--ev-observed)" } },
    { k: "Inferred", d: "belt route between scans, not seen", style: { borderTop: "3px dotted var(--ev-hypothesis)" } },
    { k: "Gap", d: "unknown, never bridged", style: { height: 10, borderTop: "0", background:
      "repeating-linear-gradient(135deg, var(--ev-unknown) 0 1.5px, transparent 1.5px 4px)", borderRadius: 2 } },
    { k: "Scan", d: "identity read at a read point", style: { width: 9, height: 9, borderTop: "0", background: "var(--ev-scan)",
      transform: "rotate(45deg)", margin: "0 6px 0 7px" } },
  ];
  return (
    <ul className="sp-list" aria-label="Evidence legend" style={{ gap: compact ? 4 : 6 }}>
      {items.map((i) => (
        <li key={i.k} className="sp-row" style={{ fontSize: 12 }}>
          <span className="sp-swatch" style={i.style} aria-hidden />
          <span className="sp-strong" style={{ fontWeight: 600 }}>{i.k}</span>
          {!compact && <span className="sp-muted">{i.d}</span>}
        </li>
      ))}
    </ul>
  );
}

export function ModeChip({ mode }: { mode: string }) {
  const tone = mode === "floor_xy" || mode === "multiview_xyz" ? "sp-chip" : "sp-chip sp-chip-warn";
  return <span className={tone} title="How this position was obtained (PRD §13.5)">mode: {mode}</span>;
}
