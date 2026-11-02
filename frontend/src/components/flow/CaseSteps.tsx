"use client";
/**
 * The case header, ops-console style: a back link to the Hub, the parcel (and what the customer said), then the four
 * steps as one connected stepper: Answer, Proof, Go look, Report. A finished step is a green tick with a green line to
 * the next, the current step is filled indigo, the rest are outlined. Each step says in a few words what it is for.
 * (Steps are links, not a wizard: any one can be opened at any time.)
 */
import Link from "next/link";
import "./flow.css";

const STEPS = [
  ["", "Answer", "Where it went"],
  ["/proof", "Proof", "See it on camera"],
  ["/search", "Go look", "Send staff to check"],
  ["/report", "Report", "Close the case"],
] as const;

export function CaseSteps({ caseId, waybill, said, quote, page, here }: { caseId: string; waybill: string; said?: string | null;
  /** the customer's own words, on hover */ quote?: string | null; page?: string; here: 0 | 1 | 2 | 3 }) {
  return (
    <header className="fl-casebar">
      <div className="fl-top">
        <Link href="/hub" className="fl-back">
          <svg viewBox="0 0 16 16" aria-hidden="true"><path d="M10 3.5 5.5 8l4.5 4.5" /></svg>Hub
        </Link>
        <span className="fl-sep" aria-hidden="true">/</span>
        {page ? <Link href={`/cases/${caseId}`} className="fl-wb">{waybill || "Case"}</Link> : <span className="fl-wb fl-wb-now">{waybill || "Case"}</span>}
        {said && <span className="fl-said" title={quote ? `Customer service: “${quote}”` : undefined}>{said}</span>}
        <Link href={`/cases/${caseId}/investigate`} className="fl-run">
          How the agents worked<span aria-hidden="true">→</span>
        </Link>
      </div>
      <nav aria-label="Case steps">
        <ol className="fl-steps">
          {STEPS.map(([path, label, hint], i) => (
            <li key={label} className="fl-step" data-state={i < here ? "done" : i === here ? "now" : "next"}>
              <Link href={`/cases/${caseId}${path}`} aria-current={i === here ? "step" : undefined}>
                <span className="fl-step-n" aria-hidden="true">
                  {i < here ? <svg viewBox="0 0 16 16"><path d="m3.5 8.5 3 3 6-6.5" /></svg> : i + 1}
                </span>
                <span className="fl-step-t"><b>{label}</b><small>{hint}</small></span>
              </Link>
            </li>
          ))}
        </ol>
      </nav>
    </header>
  );
}
